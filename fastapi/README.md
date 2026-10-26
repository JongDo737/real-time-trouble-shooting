# 통번역 · RAG 서비스 (fastapi)

지부-본사 실시간 통번역(`/translate`)과 장비 오류 해결방법 검색(`/rag-query`) 서비스입니다.
API 명세는 `docs/api2.md` (백엔드 연동용), 상세 설계는 `docs/api.md`를 봅니다.

현재 상태: `/health`, `/translate`, `/rag-query`(하이브리드 검색 + 평가 + 재시도 + 답변 생성) 구현됨.
`/rag-query`는 파이프라인이 만든 FAISS 인덱스가 있어야 동작합니다 (아래 "RAG 인덱스" 참고).

## 1. 준비 (Python 3.11)

```bash
cd fastapi
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. 설정

설정은 `fastapi/`가 아니라 **프로젝트 루트의 `.env`**(`../.env`)에서 읽습니다. 루트에 `.env`가 없으면 만들고, 다른 서비스(MariaDB 등)와 같은 파일을 씁니다. (`.env`는 git에 올라가지 않습니다)

이 서비스에서 꼭 채워야 하는 값은 `OPENAI_API_KEY`(OpenAI API 키) 하나입니다. 나머지는 기본값이 있습니다.

번역 모델은 `TRANSLATE_MODEL`(기본 `gpt-4o`)로 바꿀 수 있습니다.

호출 제한 시간: 번역은 `LLM_TIMEOUT_SECONDS`(기본 10초), RAG는 호출 한 번당 `RAG_LLM_TIMEOUT_SECONDS`(기본 20초)와 질문 하나의 전체 상한 `RAG_DEADLINE_SECONDS`(기본 20초)를 따로 씁니다. `.env`에 값이 있으면 코드 기본값보다 `.env`가 우선합니다.

## 3. 실행

```bash
uvicorn app.main:app --port 8001 --reload
```

- Swagger: http://localhost:8001/docs
- 상태 확인: http://localhost:8001/health (OpenAI 키가 있고 FAISS 인덱스가 있어야 `ok`, 지금은 인덱스가 없어 `degraded`(503)가 정상)

## 4. 호출해 보기

인증 없이 바로 호출할 수 있습니다 (`/health`, `/translate`, `/rag-query` 모두).

번역:

```bash
curl -s -X POST http://localhost:8001/translate \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "call-0007",
    "utterance_id": "u-0001",
    "text": "냉각 팬이 안 돌아가고 ALARM-402 오류가 떠요.",
    "source_lang": "ko",
    "target_lang": "en",
    "speaker": "USER"
  }'
```

Swagger(`/docs`)에서 각 API의 **Try it out**으로 바로 호출할 수 있습니다.

## RAG 인덱스

`/rag-query`는 서버가 시작될 때 `FAISS_DIR`(기본 `../rag_pipeline/faiss_db/pdf`)의 `index.faiss`, `index.pkl`을 읽습니다.
로그에 `RAG 인덱스 로드 완료: N개 청크`가 보이면 연결된 것이고, `/health`의 `index_loaded`와 `chunks`로도 확인할 수 있습니다.

- 인덱스가 없으면 서버는 뜨지만 `/rag-query`는 503(`VECTORDB_UNAVAILABLE`)을 돌려줍니다.
- `*.faiss`는 git에 올라가지 않으므로, `rag_pipeline/build_faiss.py`로 직접 만들거나 파일을 받아 위 위치에 둡니다.
- 인덱스를 만든 임베딩 모델(`text-embedding-3-small`)과 `.env`의 `EMBEDDING_MODEL`이 같아야 합니다.
- 의존성이 추가되었으니 pull 후에는 `pip install -r requirements.txt`를 다시 실행하세요.

호출 예:

```bash
curl -s -X POST http://localhost:8001/rag-query \
  -H "Content-Type: application/json" \
  -d '{"session_id":"call-0007","request_id":"q-0001","equipment_name":"Brooks GF40","error_code":"AL40","symptom":"유량이 출렁거립니다"}'
```

## 5. 통화 시뮬레이션 (실시간 번역 · 지연 확인)

서버를 켠 상태에서, 상담원(한국어)과 지부 담당자(영어)의 8발화 대화를 순서대로 번역하고 지연을 보여 줍니다. 직전 발화를 `context`로 함께 보냅니다.

```bash
python scripts/simulate_call.py              # 대화 1회: 문장별 원문 · 번역 · 지연
python scripts/simulate_call.py --repeat 5   # 5번 반복해서 평균 · 95% · 최대 지연 확인
```

## 6. 평가셋으로 정확도 재기

평가셋은 두 개이고, 둘 다 **입력 파일(`inputs.json`)과 정답지 파일(`answers.json`)로 나뉘어** 있습니다. 시스템에 넣는 입력과 채점용 정답지가 한 파일에 섞이면 정답이 새는 것처럼 보이기 때문입니다.

| 평가셋 | 무엇을 보나 |
|---|---|
| `eval/q30/` | 팀 표 질문 30개. 문서에 있는 내용을 **제대로 찾아 답하는지** (기대 status가 모두 `found`) |
| `eval/q10/` | **잘못 나와야 하는** 질문 10개. 없는 장비 4개 · 없는 주제 3개는 "검색 결과 없음"이어야 하고, 코드가 틀린 질문 3개는 같은 사례로 단정하지 말고 "관련 사례"로 알리며 확인 필요로 표시해야 합니다 |

```bash
python scripts/run_eval.py                                  # q30, 코드를 비우고 (기본)
python scripts/run_eval.py --known-codes                    # q30, 표의 알람 코드를 알 때
python scripts/run_eval.py --set eval/q10/inputs.json       # q10 (잘못 나와야 하는 질문)
python scripts/run_eval.py --retries 1 --out r.json         # 결과를 JSON으로도 저장
```

`--set` 옆의 `answers.json`을 자동으로 찾아 id로 합칩니다(`--answers`로 직접 지정도 가능). 문장별로 답변 첫 2줄이 같이 나옵니다.

| 파일 | 담는 것 |
|---|---|
| `inputs.json` | 시스템에 넣는 입력만: `equipment_name`, `symptom`, `error_code`, `error_code_known`(코드를 알 때) |
| `answers.json` | 채점용 정답지: `expected_summary`, `source_manual`, `expect`(찾음 여부 · 필수 단어 · 근거 섹션 · 위험도 · 같은 사례인지 · 확인 필요) |

- 채점은 기대값이 있는 항목만 봅니다: `status`(found/not_found), `exact`(같은 사례인지), `review`, `keywords`(필수 단어), `source`(근거 섹션), `risk`(위험도).
- 평가 스크립트가 검색·답변(`run_rag`)에 넘기는 값은 장비명 · 오류코드 · 증상뿐이고, 정답지는 답이 나온 뒤 채점에만 씁니다. 서비스 코드(`app/`)는 평가 파일을 읽지 않습니다.
- 두 파일은 `id`로 합쳐지고, id가 어긋나면 오류로 알려 줍니다. 입력 파일에 정답 필드가 섞이면 테스트가 실패합니다.
- 질문을 추가할 때는 `inputs.json`에 입력을, `answers.json`에 같은 `id`로 정답을 넣습니다. 모델은 매번 조금씩 다르게 답하므로 같은 질문도 여러 번 돌려 보는 것이 좋습니다.

## 7. 번역 용어집

번역에서 용어가 흔들리지 않도록 `data/glossary.json`에 용어를 적어 둡니다 (예: flow ↔ 유량). 번역할 문장에 용어가 나오면 목표 언어의 표기를 모델에 알려 줍니다.

```json
{"id": "flow-rate", "terms": {"en": ["flow rate", "flow"], "ko": ["유량"]}}
```

- 파일을 **저장하면 서버를 재시작하지 않아도** 다음 요청부터 반영됩니다. 파일이 깨져 있으면 이전에 읽은 값을 계속 쓰고 로그에 오류를 남깁니다.
- 같은 언어에 표기를 여러 개 적을 수 있고, 목표 언어로는 **첫 번째** 표기가 쓰입니다.
- 장비명, 모델명, 오류코드는 넣지 않습니다 (영어 원문 그대로 둠).
- 지금 들어 있는 항목은 매뉴얼의 `한국어(영어)` 병기에서 뽑은 **초안**입니다. 현장 담당자가 검수해서 고치거나 추가해 주세요.
- 경로는 `.env`의 `GLOSSARY_FILE`로 바꿀 수 있습니다.

## 8. 평가 방법과 청킹 선택 (.env로 바꿈)

둘 다 프로젝트 루트 `.env`에 적으면 되고, 적지 않으면 기본값입니다.

### 평가 방법: 키워드 옆에 의미 기반 평가 추가

`python scripts/run_eval.py`가 답변을 채점하는 방법입니다. 키워드는 표현이 다르면(예: 협착 / 손 끼임) 틀린 것으로 보므로, 의미로 보는 두 방법을 나란히 둘 수 있습니다. 방법마다 따로 집계되어 비교됩니다.

| 값 | 하는 일 |
|---|---|
| `keywords` | 기대하는 필수 단어가 답변에 있는지 (기본) |
| `embedding` | 답변과 기대 답변(`expected_summary`)의 임베딩 코사인 유사도. 기대 답변(`expected_summary`)이 있는 평가셋(`eval/q30/`)에서만 동작 |
| `judge` | LLM이 관련성 · 충실성(근거 문서에 있는 내용인지) · 정확성(기대 답변이 있을 때)을 1~5점으로 채점 |

```
EVAL_METHODS=keywords,embedding,judge   # 쉼표로 여러 개
EVAL_JUDGE_MODEL=gpt-4o                 # 답변 생성 모델과 다른 모델로 채점 (자기 평가 편향 완화)
EVAL_EMBED_THRESHOLD=0.5                # 유사도 통과 기준
EVAL_JUDGE_THRESHOLD=4                  # Judge 통과 기준 (1~5점)
EVAL_PASS_RULE=all                      # all: 고른 내용 평가를 모두 통과 / any: 하나라도 통과
```

한 번만 바꿔 보려면 `python scripts/run_eval.py --methods keywords,judge`처럼 `--methods`로 덮어씁니다.

- 유사도 기준 0.5는 Q01~Q10의 답변과 기대 답변을 짝지어 잰 값입니다. 맞는 짝은 19/20이 통과하고, 다른 질문의 기대 답변과 짝지은 것은 16/180이 통과했습니다. 점수가 서로 겹치는 구간이 있어서 임베딩 유사도만으로 합격을 정하기는 어렵고 참고용입니다.
- Judge도 같은 입력에 점수가 달라질 수 있고(이유와 점수가 어긋나는 경우가 있었음), 모델 편향이 있습니다. 반복해서 평균으로 보세요.

### Judge를 "확인 필요" 경고로만 쓰기

합격은 키워드로 정하고, Judge는 따로 채점해서 떨어지면 합격 여부와 상관없이 "확인 필요"로만 표시하는 구성입니다. Judge는 같은 입력에도 점수가 달라질 수 있어서(실측 8% 갈림) 합격 판정에 직접 쓰지 않는 방법입니다.

```
EVAL_METHODS=keywords        # 합격을 정하는 방법
EVAL_INFO_METHODS=judge      # 보여 주기만 하는 방법 (떨어지면 ⚠ 확인 필요). 비워 두면 사용 안 함
```

결과 끝에 `⚠ 확인 필요 N건 (judge 기준, 합격에는 영향 없음)`과 해당 질문 번호가 나옵니다. 한 번만 바꿔 보려면 `--info-methods judge`.

### 청킹: 500자 단위 대신 Semantic 청킹

| `CHUNKING` | 서버가 읽는 인덱스 |
|---|---|
| `fixed` (기본) | 파이프라인이 500자 단위로 자른 인덱스 (`FAISS_DIR`) |
| `semantic` | 문장 사이 의미가 크게 바뀌는 곳에서 자른 인덱스 (`FAISS_SEMANTIC_DIR`, 기본 `../rag_pipeline/faiss_db/pdf_semantic`) |

Semantic 인덱스는 따로 만들어야 합니다. 파이프라인 폴더의 코드와 기존 인덱스는 건드리지 않습니다.

```bash
python scripts/build_semantic_index.py      # rag_pipeline/data/*.md를 읽어 pdf_semantic/에 저장 (OpenAI 키 필요)
CHUNKING=semantic uvicorn app.main:app --port 8001   # 또는 .env에 CHUNKING=semantic
```

조절 값:
```
SEMANTIC_BREAKPOINT_PERCENTILE=90   # 인접 문장의 의미 거리가 상위 (100-값)%인 곳을 경계로 봄. 낮출수록 잘게 잘림
SEMANTIC_MIN_CHARS=150              # 이보다 짧은 청크는 만들지 않음
SEMANTIC_MAX_CHARS=900              # 이보다 길면 강제로 자름
```

- 문서의 `## ` 제목과 `---` 구분선은 의미 계산 전에 먼저 경계로 씁니다. 청크 헤더(섹션 · 장비명 · 에러코드)를 청크 본문에서 읽는데, 다른 섹션이 한 청크에 섞이면 이 값이 틀어지기 때문입니다.
- 청크 헤더와 메타데이터 규칙은 `rag_pipeline/build_faiss.py`와 똑같이 맞췄습니다(청킹 방식만 바뀌는 비교가 되도록). 그쪽 규칙을 고치면 `app/services/semantic_chunking.py`도 같이 고쳐야 합니다.
- Docker에서 쓰려면 환경변수 `CHUNKING=semantic`을 넘기면 됩니다(`docker-compose.yml`이 `CHUNKING`을 받도록 되어 있습니다). 인덱스 폴더는 이미 `rag_pipeline/faiss_db` 전체를 연결하므로 `pdf_semantic`도 보입니다.

## 9. 위험도 (`risk_level`)

매뉴얼의 항목마다 `- 위험도: CRITICAL (이유)` 줄이 있고, `/rag-query` 응답이 근거 문서 중 가장 높은 위험도를 돌려줍니다.

| 등급 | 뜻 |
|---|---|
| `INFO` | 절차 · 참조 |
| `WARNING` | 공정 중단이나 수율 · 부품 손상 |
| `CRITICAL` | 인명 위험 또는 즉시 파손 |

- 응답에 `risk_level`(없으면 `null`)과 `risk_reason`(괄호 안 이유)이 들어갑니다. `CRITICAL`이면 화면에서 눈에 띄게 보여 주는 것을 권장합니다.
- **파이프라인의 청크 헤더 `위험도: X`는 쓰지 않습니다.** 청크 안에서 CRITICAL/WARNING/INFO 단어를 처음 찾은 값이고 못 찾으면 INFO로 채우는데, 항목이 500자로 잘리면 뒷부분 청크가 모두 INFO가 되어 틀립니다. 새 데이터로 재 보니 고정 청킹 인덱스의 매뉴얼 청크 80개 중 42개(52%)의 헤더 위험도가 틀렸고, 본문의 위험도 줄을 직접 읽는 방식은 80개 모두 맞았습니다.
- 뒷부분 청크는 항목의 머리 청크까지 거슬러 올라가 위험도 줄을 읽습니다(`RagIndex.risk_of`). 위험도 표기가 없는 문서(예: 사례 로그)는 `null`입니다.
- 평가셋에서는 질문의 `expect.risk_level`로 응답의 위험도가 맞는지 확인합니다(`risk` 항목).

## 10. 테스트

```bash
pytest
```

테스트는 가짜 LLM을 쓰므로 OpenAI 키 없이 실행됩니다.
