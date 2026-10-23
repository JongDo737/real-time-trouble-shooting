import copy

import pytest

from tests.conftest import RAG_BODY, TRANSLATE_BODY, judge_json


def post_translate(client, **overrides):
    body = {**TRANSLATE_BODY, **overrides}
    return client.post("/translate", json=body)


def post_rag(client, **overrides):
    body = {**RAG_BODY, **overrides}
    return client.post("/rag-query", json=body)


def assert_validation_error(res):
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("missing", ["session_id", "utterance_id", "text", "target_lang"])
def test_translate_required_fields(client, missing):
    body = copy.deepcopy(TRANSLATE_BODY)
    del body[missing]
    assert_validation_error(client.post("/translate", json=body))


@pytest.mark.parametrize(
    "overrides",
    [
        {"text": ""},
        {"text": "   "},
        {"text": "가" * 2001},
        {"target_lang": "english"},
        {"target_lang": "auto"},
        {"source_lang": "korean"},
        {"speaker": "customer"},
        {"speaker": "branch"},  # 이전 값 (USER로 변경됨)
        {"speaker": "agent"},  # 이전 값 (ADMIN으로 변경됨)
        {"context": [{"speaker": "agent", "text": "hi"}]},
        {"context": [{"speaker": "ADMIN", "text": "hi"}] * 6},
    ],
)
def test_translate_rejects_invalid_values(client, overrides):
    assert_validation_error(post_translate(client, **overrides))


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"source_lang": "auto"},
        {"source_lang": "KO", "target_lang": "EN"},  # 대소문자 허용
        {"speaker": "USER", "equipment_name": "Brooks GF40", "error_code": "AL40"},
        {"speaker": "admin"},  # 대소문자는 구분하지 않는다
        {"context": [{"speaker": "ADMIN", "text": "Which machine?"}]},
        {"glossary": [{"src": "a", "tgt": "b"}]},  # 지원 종료된 필드: 보내도 무시된다
    ],
)
def test_translate_accepts_valid_values(client, overrides):
    assert post_translate(client, **overrides).status_code == 200


@pytest.mark.parametrize("missing", ["session_id", "request_id", "equipment_name"])
def test_rag_required_fields(client, missing):
    body = copy.deepcopy(RAG_BODY)
    del body[missing]
    assert_validation_error(client.post("/rag-query", json=body))


@pytest.mark.parametrize(
    "overrides",
    [{"equipment_name": ""}, {"symptom": "가" * 501}, {"error_code": "X" * 51}],
)
def test_rag_rejects_invalid_values(client, overrides):
    assert_validation_error(post_rag(client, **overrides))


# ---------- error_code 선택 필드 ----------


def test_rag_error_code_is_optional_when_symptom_is_given(client):
    body = {k: v for k, v in RAG_BODY.items() if k != "error_code"}
    assert client.post("/rag-query", json=body).status_code == 200


@pytest.mark.parametrize("code", [None, "", "  ", "NO-ALARM", "no-alarm", "N/A", "n/a", "None", "UNKNOWN", "-"])
def test_placeholder_error_codes_mean_missing(client, llm, code):
    llm.completions.queue = [judge_json(5), "1. 조치"]
    post_rag(client, error_code=code)
    user = llm.completions.calls[0]["messages"][1]["content"]
    assert "Requested error code: not provided" in user
    assert "Error code:" not in user  # 사례 설명에도 오류코드 줄이 없다


def test_real_pseudo_code_from_the_manual_is_still_a_code(client, llm):
    llm.completions.queue = [judge_json(5), "1. 조치"]
    post_rag(client, error_code="NO-ALARM-IGNITION-FAIL")
    user = llm.completions.calls[0]["messages"][1]["content"]
    assert "Error code: NO-ALARM-IGNITION-FAIL" in user


@pytest.mark.parametrize("code", [None, "NO-ALARM", "N/A", ""])
def test_neither_code_nor_symptom_is_rejected_with_a_clear_message(client, code):
    body = {k: v for k, v in RAG_BODY.items() if k not in ("error_code", "symptom")}
    res = client.post("/rag-query", json={**body, "error_code": code})
    assert_validation_error(res)
    message = res.json()["error"]["message"]
    assert "error_code 또는 symptom 중 하나는 필요합니다" in message


def test_blank_symptom_counts_as_missing(client):
    body = {k: v for k, v in RAG_BODY.items() if k != "error_code"}
    assert_validation_error(client.post("/rag-query", json={**body, "symptom": "   "}))


def test_rag_symptom_is_optional(client):
    body = {k: v for k, v in RAG_BODY.items() if k != "symptom"}
    assert client.post("/rag-query", json=body).status_code == 200


def test_broken_json_gets_a_readable_message(client):
    broken = '{"session_id": "a" "utterance_id": "b"}'  # 쉼표 누락
    res = client.post("/translate", content=broken, headers={"Content-Type": "application/json"})
    assert_validation_error(res)
    assert "올바른 JSON이 아닙니다" in res.json()["error"]["message"]


def test_nested_field_error_names_the_field_path(client):
    res = post_translate(client, context=[{"speaker": "ADMIN", "txt": "hi"}])  # text 오타
    assert_validation_error(res)
    assert "context.0.text" in res.json()["error"]["message"]


def test_validation_error_does_not_echo_input(client):
    secret_text = "민감한통화내용" * 400  # 2000자 초과
    res = post_translate(client, text=secret_text)
    assert res.status_code == 422
    assert "민감한통화내용" not in res.text
    assert "body" not in res.json()["error"]["message"] or "text" in res.json()["error"]["message"]
