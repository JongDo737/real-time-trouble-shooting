import openai
import httpx
import pytest

from app.config import get_settings
from app.main import app
from app.routers.rag import get_rag_index
from app.services.rag import parse_judge
from tests.conftest import RAG_BODY, judge_json, make_settings

ANSWER = "1. 레귤레이터를 2 psig 단위로 상향 조정합니다.\n2. Zero 버튼을 5초 이상 눌러 영점을 재설정합니다."
REWRITTEN = "MFC 유량 헌팅 AL40 인렛 압력 조정"


def post(client, **overrides):
    return client.post("/rag-query", json={**RAG_BODY, **overrides})


def judge_calls(llm):
    return [c for c in llm.completions.calls if "relevance judge" in c["messages"][0]["content"]]


def request():
    return httpx.Request("POST", "https://llm.test/v1")


# ---------- 성공 ----------


def test_found_on_first_attempt(client, llm):
    llm.completions.queue = [judge_json(5, relevant=[1]), ANSWER]
    res = post(client)

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "found"
    assert body["answer"] == ANSWER
    assert body["message"] is None and body["reason"] is None
    assert body["attempts"] == 1
    assert body["score"] == 1.0
    assert body["needs_review"] is False
    assert body["handoff"] is False
    assert body["exact_match"] is True
    assert body["usage"] == {"in_tok": 240, "out_tok": 30}  # 평가 1회 + 생성 1회
    assert body["sources"][0]["doc"] == "semiconductor_troubleshoot_log.pdf"


def test_sources_come_from_the_relevant_chunks_only(client, llm):
    llm.completions.queue = [judge_json(5, relevant=[1]), ANSWER]
    body = post(client).json()
    assert {s["doc"] for s in body["sources"]} == {"semiconductor_troubleshoot_log.pdf"}
    sections = [s["section"] for s in body["sources"]]
    assert "General" not in sections  # 섹션을 모르는 청크의 General은 표시하지 않는다


def test_borderline_score_passes_but_needs_review(client, llm):
    llm.completions.queue = [judge_json(3), ANSWER]  # 3/5 = 0.6 = 합격선
    body = post(client).json()
    assert body["status"] == "found" and body["score"] == 0.6
    assert body["needs_review"] is True


def test_dense_query_defaults_to_equipment_and_code_without_symptom(client, llm):
    llm.completions.queue = [judge_json(5), ANSWER]
    body = {k: v for k, v in RAG_BODY.items() if k != "symptom"}
    client.post("/rag-query", json=body)
    assert llm.embeddings.calls[0]["input"] == "Brooks GF40 AL40 해결방법"
    assert llm.embeddings.calls[0]["model"] == "fake-embedding-model"


def test_rag_calls_use_the_rag_timeout_not_the_translate_one(client, llm):
    app.dependency_overrides[get_settings] = lambda: make_settings(rag_llm_timeout_seconds=7, llm_timeout_seconds=3)
    llm.completions.queue = [judge_json(5), ANSWER]
    post(client)
    assert [c["timeout"] for c in llm.completions.calls] == [7, 7]  # 평가 · 생성
    assert llm.embeddings.calls[0]["timeout"] == 7


def test_rag_timeout_defaults_to_20_seconds(client, llm):
    llm.completions.queue = [judge_json(5), ANSWER]
    post(client)
    assert all(c["timeout"] == 20 for c in llm.completions.calls)


def test_rewrite_call_uses_the_rag_timeout_too(client, llm):
    llm.completions.queue = [judge_json(2), REWRITTEN, judge_json(5), ANSWER]
    post(client)
    assert [c["timeout"] for c in llm.completions.calls] == [20, 20, 20, 20]


def test_without_error_code_the_dense_query_uses_equipment_and_symptom_only(client, llm):
    llm.completions.queue = [judge_json(5), ANSWER]
    post(client, error_code=None)
    assert llm.embeddings.calls[0]["input"] == "유량이 출렁거립니다"  # symptom 그대로
    llm.embeddings.calls.clear()
    llm.completions.queue = [judge_json(5), ANSWER]
    client.post("/rag-query", json={**RAG_BODY, "error_code": "AL40", "symptom": None})
    assert llm.embeddings.calls[0]["input"] == "Brooks GF40 AL40 해결방법"


def test_without_error_code_the_judge_judges_by_symptom_and_the_result_is_exact(client, llm):
    llm.completions.queue = [judge_json(5, exact=True), ANSWER]
    body = post(client, error_code=None).json()
    system = llm.completions.calls[0]["messages"][0]["content"]
    assert "If no error code was requested" in system
    assert body["status"] == "found" and body["exact_match"] is True
    assert body["message"] is None and body["needs_review"] is False  # 코드 불일치 문구가 붙지 않는다


def test_without_error_code_no_chunk_is_pinned(client, llm):
    # 코드가 없으면 "코드가 적힌 청크 고정"은 일어나지 않는다: 증상(냉각 팬) 쪽 결과만 평가에 간다
    app.dependency_overrides[get_settings] = lambda: make_settings(rag_top_k=1)
    llm.completions.queue = [judge_json(5), ANSWER]
    post(client, equipment_name="Centura", error_code=None, symptom="냉각 팬이 안 돌아갑니다")
    user = judge_calls(llm)[0]["messages"][1]["content"]
    assert "ALARM-402" not in user


def test_models_and_case_are_passed_to_judge_and_generator(client, llm):
    llm.completions.queue = [judge_json(5), ANSWER]
    post(client)
    judge, generate = llm.completions.calls
    assert judge["model"] == "fake-judge-model" and judge["response_format"] == {"type": "json_object"}
    assert generate["model"] == "fake-gen-model"
    for call in (judge, generate):
        user = call["messages"][1]["content"]
        assert "Equipment: Brooks GF40" in user and "Error code: AL40" in user
        assert "[Document 1]" in user


# ---------- 평가 입력과 답변 근거 ----------


def test_judge_is_told_where_the_requested_code_appears(client, llm):
    llm.completions.queue = [judge_json(5), ANSWER]
    post(client)  # AL40은 c-mfc-1에 있다
    user = judge_calls(llm)[0]["messages"][1]["content"]
    assert "Requested error code AL40 appears in: Documents" in user


def test_judge_is_told_when_the_code_is_in_no_document(client, llm):
    llm.completions.queue = [judge_json(3, exact=False), ANSWER]
    post(client, error_code="AL99")
    user = judge_calls(llm)[0]["messages"][1]["content"]
    assert "Requested error code AL99 appears in: none of the documents" in user


def test_chunk_with_the_requested_code_is_not_pushed_out_by_dense_ranking(client, llm):
    # 증상은 "냉각 팬"이라 Dense는 팬 청크를 밀어 올리지만, 요청한 코드 ALARM-402는 RF 청크에만 적혀 있다.
    # 그 청크가 평가에 가지 않으면 "코드가 어느 문서에도 없다"고 오판한다.
    app.dependency_overrides[get_settings] = lambda: make_settings(rag_top_k=2)
    llm.completions.queue = [judge_json(5), ANSWER]
    post(client, equipment_name="Centura", error_code="ALARM-402", symptom="냉각 팬이 안 돌아갑니다")
    user = judge_calls(llm)[0]["messages"][1]["content"]
    assert "ALARM-402 appears in: Documents" in user
    assert "[장비명: CENTURA | 에러코드: ALARM-402" in user


def test_code_hint_ignores_spelling_differences(client, llm):
    llm.completions.queue = [judge_json(5), ANSWER]
    post(client, error_code="alarm 402", equipment_name="AE Cesar 1312", symptom="반사파")
    user = judge_calls(llm)[0]["messages"][1]["content"]
    assert "appears in: Documents" in user  # ALARM-402 == alarm 402


def test_generation_gets_the_following_chunks_of_the_same_section(client, llm):
    # 평가가 1번 문서(c-mfc-1)만 골라도, 같은 섹션에서 이어지는 청크(c-mfc-2의 Zero 버튼 단계)가 답변 근거에 함께 들어간다
    llm.completions.queue = [judge_json(5, relevant=[1]), ANSWER]
    post(client)
    judge_user = llm.completions.calls[0]["messages"][1]["content"]
    generate_user = llm.completions.calls[1]["messages"][1]["content"]
    assert "[Document 1]\n[장비명: COMMON | 에러코드: AL40" in judge_user  # 1번이 c-mfc-1
    assert "Zero 버튼" in generate_user


def test_generation_prompts_keep_numbers(client, llm):
    llm.completions.queue = [judge_json(5), ANSWER]
    post(client)
    assert "Keep every number" in llm.completions.calls[1]["messages"][0]["content"]
    llm.completions.calls.clear()
    llm.completions.queue = [judge_json(3, exact=False), NOTICE_ANSWER]
    post(client, error_code="AL99")
    assert "Keep every number" in llm.completions.calls[1]["messages"][0]["content"]


# ---------- 관련 사례만 있는 경우 (오류코드나 장비가 다름) ----------

NOTICE_ANSWER = "※ 요청하신 AL99가 아니라 AL40 사례입니다.\n1. 레귤레이터를 2 psig 단위로 상향 조정합니다."


def test_related_case_is_answered_with_notice_and_review_flag(client, llm):
    llm.completions.queue = [judge_json(3, exact=False), NOTICE_ANSWER]
    body = post(client, error_code="AL99").json()

    assert body["status"] == "found"
    assert body["answer"] == NOTICE_ANSWER
    assert body["exact_match"] is False
    assert body["needs_review"] is True
    assert "관련 사례" in body["message"]
    assert body["handoff"] is False
    assert body["attempts"] == 1


def test_related_case_does_not_retry(client, llm):
    llm.completions.queue = [judge_json(3, exact=False), NOTICE_ANSWER]
    post(client, error_code="AL99")
    assert len(llm.completions.calls) == 2  # 평가 1회 + 생성 1회, 재작성이나 재시도 없음
    assert len(llm.embeddings.calls) == 1


def test_related_case_uses_the_related_generation_prompt(client, llm):
    llm.completions.queue = [judge_json(3, exact=False), NOTICE_ANSWER]
    post(client, error_code="AL99")
    judge, generate = llm.completions.calls
    assert "exact_case" in judge["messages"][0]["content"]
    system = generate["messages"][0]["content"]
    assert "RELATED case" in system and "what differs" in system
    assert "Never present the steps as confirmed" in system


def test_exact_case_uses_the_normal_generation_prompt(client, llm):
    llm.completions.queue = [judge_json(5, exact=True), ANSWER]
    body = post(client).json()
    generate = llm.completions.calls[1]
    assert "RELATED case" not in generate["messages"][0]["content"]
    assert body["exact_match"] is True and body["message"] is None


def test_related_case_with_nothing_useful_moves_on(client, llm):
    llm.completions.queue = [judge_json(3, exact=False), "N/A", REWRITTEN, judge_json(5), ANSWER]
    body = post(client).json()
    assert body["status"] == "found" and body["attempts"] == 2 and body["exact_match"] is True


def test_low_score_related_case_is_still_not_found(client, llm):
    llm.completions.queue = [judge_json(2, exact=False), REWRITTEN, judge_json(2, exact=False), judge_json(1, exact=False)]
    body = post(client).json()
    assert body["status"] == "not_found" and body["exact_match"] is None


def test_missing_exact_flag_is_treated_as_exact(client, llm):
    llm.completions.queue = ['{"score": 5, "relevant": [1]}', ANSWER]
    body = post(client).json()
    assert body["exact_match"] is True


# ---------- 재시도 ----------


def test_retry_rewrites_the_dense_query_and_succeeds_on_second_attempt(client, llm):
    llm.completions.queue = [judge_json(2), REWRITTEN, judge_json(5), ANSWER]
    body = post(client).json()

    assert body["status"] == "found" and body["attempts"] == 2
    assert [c["input"] for c in llm.embeddings.calls] == ["유량이 출렁거립니다", REWRITTEN]
    assert body["needs_review"] is False


def test_third_attempt_is_bm25_only_and_forces_review(client, llm):
    # 재시도를 2회로 올렸을 때만 3번째(BM25 단독) 시도가 생긴다
    app.dependency_overrides[get_settings] = lambda: make_settings(rag_max_retries=2)
    llm.completions.queue = [judge_json(1), REWRITTEN, judge_json(1), judge_json(5), ANSWER]
    body = post(client).json()

    assert body["status"] == "found" and body["attempts"] == 3
    assert body["needs_review"] is True
    assert len(llm.embeddings.calls) == 2  # 3차는 의미 검색(임베딩)을 하지 않는다


def test_not_found_after_two_attempts_hands_off(client, llm):
    llm.completions.queue = [judge_json(1), REWRITTEN, judge_json(2)]
    body = post(client).json()

    assert body["status"] == "not_found"
    assert body["answer"] is None
    assert body["message"] == "검색 결과 없음"
    assert body["reason"] == "low_score"
    assert body["handoff"] is True and body["needs_review"] is False
    assert body["attempts"] == 2  # 기본값: 최대 2번 시도
    assert body["score"] == 0.4  # 마지막 시도의 점수
    assert body["sources"] == []
    assert len(judge_calls(llm)) == 2
    assert len(llm.embeddings.calls) == 2  # 두 번 모두 Hybrid (BM25 단독 시도 없음)


def test_retries_setting_can_raise_attempts_to_three(client, llm):
    app.dependency_overrides[get_settings] = lambda: make_settings(rag_max_retries=2)
    llm.completions.queue = [judge_json(1), REWRITTEN, judge_json(2), judge_json(1)]
    body = post(client).json()
    assert body["status"] == "not_found" and body["attempts"] == 3
    assert len(llm.embeddings.calls) == 2  # 3번째는 BM25 단독


def test_max_retries_setting_limits_attempts(client, llm):
    app.dependency_overrides[get_settings] = lambda: make_settings(rag_max_retries=0)
    llm.completions.queue = [judge_json(1)]
    body = post(client).json()
    assert body["status"] == "not_found" and body["attempts"] == 1


def test_judge_pass_but_generator_finds_no_fix_moves_to_next_attempt(client, llm):
    llm.completions.queue = [judge_json(4), "N/A", REWRITTEN, judge_json(5), ANSWER]
    body = post(client).json()
    assert body["status"] == "found" and body["attempts"] == 2


def test_unparseable_judge_reply_counts_as_low_score(client, llm):
    llm.completions.queue = ["not json", REWRITTEN, "still not json", "nope"]
    body = post(client).json()
    assert body["status"] == "not_found" and body["reason"] == "low_score"


def test_no_hits_skips_the_judge(client, llm, index):
    from app.services.retrieval import RagIndex
    import numpy as np

    app.dependency_overrides[get_rag_index] = lambda: RagIndex([], np.empty((0, 3), dtype="float32"))
    body = post(client).json()
    assert body["status"] == "not_found" and body["reason"] == "no_hits"
    assert judge_calls(llm) == []


def test_deadline_returns_not_found(client, llm):
    app.dependency_overrides[get_settings] = lambda: make_settings(rag_deadline_seconds=0.05)
    llm.completions.delay = 0.3
    llm.completions.queue = [judge_json(5), ANSWER]
    body = post(client).json()
    assert body["status"] == "not_found" and body["reason"] == "deadline"
    assert body["handoff"] is True and body["attempts"] >= 1


# ---------- 오류 ----------


def test_missing_index_is_reported(client):
    app.dependency_overrides.pop(get_rag_index)
    app.state.rag_index = None
    res = post(client)
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "VECTORDB_UNAVAILABLE"


def test_embedding_dimension_mismatch_is_reported(client, llm):
    llm.embeddings.vector = [0.1] * 7
    res = post(client)
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "VECTORDB_UNAVAILABLE"
    assert "EMBEDDING_MODEL" in res.json()["error"]["message"]


def test_embedding_failure_maps_to_llm_unavailable(client, llm):
    llm.embeddings.error = openai.APIConnectionError(request=request())
    res = post(client)
    assert res.status_code == 503 and res.json()["error"]["code"] == "LLM_UNAVAILABLE"


def test_judge_timeout_maps_to_llm_timeout(client, llm):
    llm.completions.queue = [openai.APITimeoutError(request=request())]
    res = post(client)
    assert res.status_code == 503 and res.json()["error"]["code"] == "LLM_TIMEOUT"


def test_missing_judge_model_setting_is_reported(client):
    app.dependency_overrides[get_settings] = lambda: make_settings(rag_judge_model="")
    res = post(client)
    assert res.status_code == 503 and "RAG_JUDGE_MODEL" in res.json()["error"]["message"]


# ---------- 평가 응답 해석 ----------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('{"score": 5, "relevant": [1, 3]}', (1.0, [1, 3], True)),
        ('{"score": 3, "exact_case": false, "relevant": [1]}', (0.6, [1], False)),
        ('{"score": 9, "relevant": []}', (1.0, [], True)),  # 범위를 벗어난 점수는 1~5로 맞춘다
        ('{"score": 0}', (0.2, [], True)),
        ('{"score": 4, "relevant": [1, 7, 0]}', (0.8, [1], True)),  # 존재하지 않는 문서 번호는 버린다
        ("garbage", (0.2, [], True)),
        ('{"relevant": [1]}', (0.2, [], True)),
    ],
)
def test_parse_judge(raw, expected):
    assert parse_judge(raw, count=3) == expected
