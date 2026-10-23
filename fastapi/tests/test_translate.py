import asyncio

import httpx
import openai
import pytest

from app.config import get_settings
from app.main import app
from app.services.llm import get_llm_client
from app.services.translate import parse_json_output, translate_text
from tests.conftest import TRANSLATE_BODY, llm_json, make_settings


def post(client, **overrides):
    return client.post("/translate", json={**TRANSLATE_BODY, **overrides})


def request():
    return httpx.Request("POST", "https://llm.test/v1/chat/completions")


# ---------- 응답 (원문 언어를 아는 경우: 번역문만 받는다) ----------


def test_translate_success(client, llm):
    llm.completions.reply = "The cooling fan is not running and error ALARM-402 is showing."
    res = post(client)

    assert res.status_code == 200
    body = res.json()
    assert body["session_id"] == "call-0007"
    assert body["utterance_id"] == "u-0012"
    assert body["translated_text"] == "The cooling fan is not running and error ALARM-402 is showing."
    assert body["source_lang"] == "ko"
    assert body["target_lang"] == "en"
    assert body["usage"] == {"in_tok": 120, "out_tok": 15}
    assert isinstance(body["latency_ms"], int)


def test_response_has_no_needs_review(client):
    assert "needs_review" not in post(client).json()


def test_known_source_lang_asks_for_plain_text_not_json(client, llm):
    post(client, source_lang="ko")
    call = llm.completions.calls[0]
    assert "response_format" not in call
    assert call["messages"][0]["content"].endswith("Respond with only the translated text.")


def test_reply_whitespace_is_stripped(client, llm):
    llm.completions.reply = "  Hello.\n"
    assert post(client).json()["translated_text"] == "Hello."


def test_empty_translation_is_an_error(client, llm):
    llm.completions.reply = "   "
    res = post(client)
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "LLM_UNAVAILABLE"


# ---------- 응답 (source_lang = auto: 감지된 언어도 받는다) ----------


def test_translate_calls_keep_the_client_default_timeout(client, llm):
    post(client)
    assert "timeout" not in llm.completions.calls[0]  # 번역은 RAG 제한(20초)의 영향을 받지 않는다


def test_auto_source_lang_asks_for_json_and_uses_detected_language(client, llm):
    llm.completions.reply = llm_json("Hello", source_lang="vi")
    res = post(client, source_lang="auto")

    assert res.json()["translated_text"] == "Hello"
    assert res.json()["source_lang"] == "vi"
    call = llm.completions.calls[0]
    assert call["response_format"] == {"type": "json_object"}
    assert "Source language: detect automatically" in call["messages"][1]["content"]


def test_undetected_language_is_und(client, llm):
    llm.completions.reply = llm_json("Hello", source_lang="not a code")
    assert post(client, source_lang="auto").json()["source_lang"] == "und"


def test_auto_non_json_reply_falls_back_to_raw_text(client, llm):
    llm.completions.reply = "Hello there"
    body = post(client, source_lang="auto").json()
    assert body["translated_text"] == "Hello there"
    assert body["source_lang"] == "und"


# ---------- 모델에 보내는 요청 ----------


def test_prompt_carries_model_context_and_rules(client, llm):
    res = post(
        client,
        speaker="USER",
        equipment_name="Brooks GF40",
        error_code="AL40",
        context=[{"speaker": "ADMIN", "text": "Which machine is having the problem?"}],
    )
    assert res.status_code == 200

    call = llm.completions.calls[0]
    assert call["model"] == "fake-translate-model"

    system, user = (m["content"] for m in call["messages"])
    assert "Never translate, transliterate, or alter error codes" in system
    assert "[ADMIN] Which machine is having the problem?" in user
    assert "Error code (keep as is): AL40" in user
    assert "Speaker: USER" in user
    assert "Target language: English (en)" in user
    assert TRANSLATE_BODY["text"] in user


def test_equipment_names_stay_in_english(client, llm):
    post(client, equipment_name="Brooks GF40")
    system = llm.completions.calls[0]["messages"][0]["content"]
    assert "keep them in their original English form" in system


def test_no_glossary_section_without_a_glossary_file(client, llm):
    post(client)
    assert "Glossary (" not in llm.completions.calls[0]["messages"][1]["content"]


def test_prompt_controls_tone_by_speaker(client, llm):
    post(client, speaker="ADMIN")
    system = llm.completions.calls[0]["messages"][0]["content"]
    assert 'polite and professional for "ADMIN"' in system
    assert 'natural spoken language for "USER"' in system


def test_prompt_has_no_review_flag(client, llm):
    post(client)
    post(client, source_lang="auto")
    for call in llm.completions.calls:
        assert "needs_review" not in call["messages"][0]["content"]


# ---------- 오류 ----------


def test_timeout_maps_to_llm_timeout(client, llm):
    llm.completions.reply = openai.APITimeoutError(request=request())
    res = post(client)
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "LLM_TIMEOUT"


def test_connection_error_maps_to_llm_unavailable(client, llm):
    llm.completions.reply = openai.APIConnectionError(request=request())
    res = post(client)
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "LLM_UNAVAILABLE"


def test_missing_model_setting_is_reported(client):
    app.dependency_overrides[get_settings] = lambda: make_settings(translate_model="")
    res = post(client)
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "LLM_UNAVAILABLE"
    assert "TRANSLATE_MODEL" in res.json()["error"]["message"]


def test_missing_api_key_is_reported(client):
    app.dependency_overrides.pop(get_llm_client)  # 실제 의존성 사용
    app.dependency_overrides[get_settings] = lambda: make_settings(openai_api_key="")
    res = post(client)
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "LLM_UNAVAILABLE"


# ---------- 서비스 함수 (RAG에서도 재사용) ----------


def test_translate_text_can_be_called_without_http(llm):
    llm.completions.reply = "The flow rate is unstable."
    result = asyncio.run(
        translate_text(
            llm, "fake-translate-model", text="유량이 불안정합니다", target_lang="en", source_lang="ko"
        )
    )
    assert result.translated_text == "The flow rate is unstable."
    assert result.source_lang == "ko"
    assert (result.in_tok, result.out_tok) == (120, 15)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('{"translation": "Hi", "source_lang": "KO "}', ("Hi", "ko")),
        ('{"translation": "Hi", "source_lang": "korean"}', ("Hi", None)),
        ('{"translation": "Hi"}', ("Hi", None)),
        ("plain text", ("plain text", None)),
        ("null", ("null", None)),
        ('{"translation": 3}', ('{"translation": 3}', None)),
    ],
)
def test_parse_json_output(raw, expected):
    assert parse_json_output(raw) == expected
