import json
import os
import time

import pytest

from app.config import get_settings
from app.main import app
from app.services import glossary as glossary_mod
from app.services.glossary import MAX_HINTS, Glossary, get_glossary, parse
from tests.conftest import TRANSLATE_BODY, make_settings

ENTRIES = {
    "entries": [
        {"id": "flow", "terms": {"en": ["flow rate", "flow"], "ko": ["유량"]}},
        {"id": "hunting", "terms": {"en": ["hunting"], "ko": ["헌팅"]}},
        {"id": "reflected", "terms": {"en": ["reflected power"], "ko": ["반사파"], "ja": ["反射波"]}},
    ]
}


def glossary(data=ENTRIES) -> Glossary:
    return parse(data)


# ---------- 문장에서 용어 고르기 ----------


def test_english_term_to_korean_uses_the_first_korean_term():
    assert glossary().select("The flow keeps oscillating.", "en", "ko") == [("flow", "유량")]


def test_korean_term_to_english_uses_the_first_english_term():
    assert glossary().select("유량이 출렁거립니다", "ko", "en") == [("유량", "flow rate")]


@pytest.mark.parametrize("text", ["The Flow is low", "flows are low", "FLOWING", "gas flow"])
def test_english_matching_ignores_case_and_accepts_word_suffixes(text):
    assert glossary().select(text, "en", "ko") == [("flow", "유량")]


def test_english_term_inside_another_word_is_not_matched():
    assert glossary().select("the overflow valve", "en", "ko") == []  # 단어 시작이 아니다


@pytest.mark.parametrize("text", ["유량이", "유량을 확인", "가스유량"])
def test_korean_matching_accepts_particles(text):
    assert glossary().select(text, "ko", "en") == [("유량", "flow rate")]


def test_only_terms_in_the_sentence_are_selected():
    hits = glossary().select("The reflected power and flow", "en", "ko")
    assert hits == [("flow", "유량"), ("reflected power", "반사파")]
    assert glossary().select("Nothing special here", "en", "ko") == []


def test_auto_source_language_looks_in_every_language():
    assert glossary().select("반사파가 튑니다", "auto", "en") == [("반사파", "reflected power")]
    assert glossary().select("The hunting starts", "auto", "ko") == [("hunting", "헌팅")]


def test_entry_without_the_target_language_is_skipped():
    assert glossary().select("flow", "en", "vi") == []
    assert glossary().select("flow", "en", "ja") == []  # flow 항목에는 ja가 없다
    assert glossary().select("reflected power", "en", "ja") == [("reflected power", "反射波")]


def test_same_source_and_target_language_gives_nothing():
    assert glossary().select("flow", "en", "en") == []


def test_number_of_hints_is_capped():
    many = {"entries": [{"terms": {"en": [f"term{i}"], "ko": [f"용어{i}"]}} for i in range(30)]}
    text = " ".join(f"term{i}" for i in range(30))
    assert len(glossary(many).select(text, "en", "ko")) == MAX_HINTS


# ---------- 파일 형식 검사 ----------


def test_invalid_entries_are_skipped_not_fatal():
    data = {"entries": [
        {"terms": {"en": ["ok"], "ko": ["확인"]}},
        {"terms": {"en": ["only one language"]}},
        {"terms": {"english": ["x"], "ko": ["y"]}},
        {"terms": "nope"},
        "garbage",
        {"terms": {"en": ["", "  "], "ko": ["빈값"]}},
    ]}
    parsed = glossary(data)
    assert [e.terms for e in parsed.entries] == [{"en": ["ok"], "ko": ["확인"]}]


def test_plain_list_format_is_accepted_too():
    assert len(parse([{"terms": {"en": ["a"], "ko": ["가"]}}])) == 1


def test_missing_entries_key_is_an_error():
    with pytest.raises(ValueError):
        parse({"description": "no entries"})


def test_shipped_glossary_file_is_valid():
    path = get_settings().glossary_path
    parsed = parse(json.loads(path.read_text(encoding="utf-8")))
    raw = json.loads(path.read_text(encoding="utf-8"))["entries"]
    assert len(parsed) == len(raw) and len(parsed) >= 10  # 모든 항목이 유효하다
    ids = [e.id for e in parsed.entries]
    assert len(ids) == len(set(ids))
    # 장비명 · 모델명 · 오류코드는 용어집에 넣지 않는다
    forbidden = ("brooks", "gf40", "al40", "alarm-")
    for entry in parsed.entries:
        for aliases in entry.terms.values():
            assert not any(f in a.lower() for a in aliases for f in forbidden)


# ---------- 파일 읽기: 변경 반영과 오류 처리 ----------


@pytest.fixture
def path(tmp_path):
    glossary_mod._cache.clear()
    return tmp_path / "glossary.json"


def write(path, data, mtime_offset=0):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    stamp = time.time() + mtime_offset
    os.utime(path, (stamp, stamp))


def test_missing_file_means_empty_glossary(path):
    assert len(get_glossary(path)) == 0


def test_file_changes_are_picked_up_without_restart(path):
    write(path, ENTRIES, mtime_offset=-10)
    assert len(get_glossary(path)) == 3
    write(path, {"entries": [{"terms": {"en": ["a"], "ko": ["가"]}}]}, mtime_offset=0)
    assert len(get_glossary(path)) == 1


def test_unchanged_file_is_not_parsed_again(path, monkeypatch):
    write(path, ENTRIES)
    first = get_glossary(path)
    monkeypatch.setattr(glossary_mod, "parse", lambda data: pytest.fail("다시 읽으면 안 된다"))
    assert get_glossary(path) is first


def test_broken_json_keeps_the_previous_glossary(path):
    write(path, ENTRIES, mtime_offset=-10)
    good = get_glossary(path)
    path.write_text("{ 편집 중인 깨진 파일", encoding="utf-8")
    os.utime(path, (time.time(), time.time()))
    assert get_glossary(path) is good  # 번역이 멈추지 않는다


def test_broken_json_without_previous_gives_empty(path):
    path.write_text("not json", encoding="utf-8")
    assert len(get_glossary(path)) == 0


# ---------- /translate와의 연결 ----------


def post(client, **overrides):
    return client.post("/translate", json={**TRANSLATE_BODY, **overrides})


def test_translate_puts_only_matching_terms_into_the_prompt(client, llm, path):
    write(path, ENTRIES)
    app.dependency_overrides[get_settings] = lambda: make_settings(glossary_file=str(path))
    res = post(client, text="The flow keeps oscillating and hunting.", source_lang="en", target_lang="ko")
    assert res.status_code == 200

    call = llm.completions.calls[0]["messages"]
    assert "Glossary (use exactly these target terms when the source term appears):" in call[1]["content"]
    assert "- flow -> 유량" in call[1]["content"]
    assert "- hunting -> 헌팅" in call[1]["content"]
    assert "반사파" not in call[1]["content"]  # 문장에 없는 용어는 넣지 않는다
    assert "The glossary overrides your own choice of terminology" in call[0]["content"]


def test_translate_without_matching_terms_has_no_glossary_section(client, llm, path):
    write(path, ENTRIES)
    app.dependency_overrides[get_settings] = lambda: make_settings(glossary_file=str(path))
    post(client, text="Hello there", source_lang="en", target_lang="ko")
    assert "Glossary (" not in llm.completions.calls[0]["messages"][1]["content"]


def test_translate_works_when_the_glossary_file_is_broken(client, llm, path):
    path.write_text("{ broken", encoding="utf-8")
    app.dependency_overrides[get_settings] = lambda: make_settings(glossary_file=str(path))
    assert post(client).status_code == 200


def test_edited_glossary_applies_to_the_next_request(client, llm, path):
    write(path, {"entries": []}, mtime_offset=-10)
    app.dependency_overrides[get_settings] = lambda: make_settings(glossary_file=str(path))
    post(client, text="flow", source_lang="en", target_lang="ko")
    assert "Glossary (" not in llm.completions.calls[0]["messages"][1]["content"]

    write(path, ENTRIES, mtime_offset=0)  # 서버 재시작 없이 파일만 수정
    post(client, text="flow", source_lang="en", target_lang="ko")
    assert "- flow -> 유량" in llm.completions.calls[1]["messages"][1]["content"]


def test_request_level_glossary_field_is_still_ignored(client, llm, path):
    write(path, {"entries": []})
    app.dependency_overrides[get_settings] = lambda: make_settings(glossary_file=str(path))
    post(client, text="flow", source_lang="en", target_lang="ko", glossary=[{"src": "flow", "tgt": "흐름"}])
    assert "흐름" not in llm.completions.calls[0]["messages"][1]["content"]


def test_glossary_hits_use_the_utterance_not_the_context(client, llm, path):
    write(path, ENTRIES)
    app.dependency_overrides[get_settings] = lambda: make_settings(glossary_file=str(path))
    post(client, text="Okay", source_lang="en", target_lang="ko",
         context=[{"speaker": "ADMIN", "text": "유량이 출렁거려요?"}])
    assert "Glossary (" not in llm.completions.calls[0]["messages"][1]["content"]
