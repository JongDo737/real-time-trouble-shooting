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

`eval/eval_set.json`(질문 25건: 채점 22 + 탐색 3)을 실제 모델에 돌려 정확도와 지연을 잽니다. 문장별로 답변 첫 2줄이 같이 나옵니다.

```bash
python scripts/run_eval.py --retries 1              # 전체 실행
python scripts/run_eval.py --retries 1 --out r.json # 결과를 JSON으로도 저장
```

채점은 기대값이 있는 항목만 봅니다: `status`(found/not_found), `exact`(같은 사례인지), `review`, `keywords`(답변에 필수 단어), `source`(근거 섹션).
`eval/eval_set_heldout.json`(10건)은 개선에 쓰지 않고 따로 둔 질문입니다. `--set eval/eval_set_heldout.json`으로 돌립니다. 질문을 추가할 때는 `eval/eval_set.json`에 항목을 넣으면 됩니다. 모델은 매번 조금씩 다르게 답하므로 같은 질문도 여러 번 돌려 보는 것이 좋습니다.

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

## 8. 테스트

```bash
pytest
```

테스트는 가짜 LLM을 쓰므로 OpenAI 키 없이 실행됩니다.
