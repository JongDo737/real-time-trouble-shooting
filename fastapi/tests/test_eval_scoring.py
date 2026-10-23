import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from run_eval import error_outcome, first_lines, keywords_present, missing_groups, score_case  # noqa: E402


def outcome(**overrides):
    base = {"status": "found", "answer": "1. 2 psig 조정\n2. Zero 버튼", "exact_match": True,
            "needs_review": False, "sections": ["[CASE-03] MFC", None]}
    return {**base, **overrides}


def test_keywords_all_groups_must_match_and_alternatives_count():
    assert keywords_present("Zero 버튼과 2 psig", ["2 psig", "zero"])
    assert keywords_present("Manual Reset 수행", ["수동 리셋|Manual Reset"])
    assert not keywords_present("2 psig만 언급", ["2 psig", "Zero"])
    assert not keywords_present(None, ["x"])


def test_score_case_checks_only_what_is_expected():
    expect = {"status": "found", "exact_match": True, "must_contain": ["2 psig"], "section": "CASE-03"}
    assert score_case(expect, outcome()) == {"status": True, "exact": True, "keywords": True, "source": True}
    assert score_case({"status": "not_found"}, outcome()) == {"status": False}


def test_score_case_detects_each_failure():
    expect = {"status": "found", "exact_match": False, "needs_review": True, "must_contain": ["AL40"], "section": "CASE-09"}
    checks = score_case(expect, outcome())
    assert checks == {"status": True, "exact": False, "review": False, "keywords": False, "source": False}


def test_first_lines_keeps_two_non_empty_lines():
    assert first_lines("a\n\nb\nc") == "a\n         b"
    assert first_lines(None) == "-"


def test_missing_groups_lists_what_the_answer_lacks():
    assert missing_groups("5%와 10%", ["5%", "10%", "커패시터|아킹"]) == ["커패시터|아킹"]
    assert missing_groups("아킹 점검", ["커패시터|아킹"]) == []
    assert missing_groups(None, ["x"]) == ["x"]


def test_error_outcome_is_recorded_as_a_failed_case():
    class Boom(Exception):
        code = "LLM_UNAVAILABLE"

    outcome = error_outcome(Boom("x"))
    assert outcome["status"] == "error" and outcome["reason"] == "LLM_UNAVAILABLE"
    assert score_case({"status": "found"}, outcome) == {"status": False}


def test_user_question_set_is_well_formed():
    cases = json.loads((ROOT / "eval" / "eval_set_manual_q10.json").read_text(encoding="utf-8"))
    assert [c["id"] for c in cases] == [f"Q{n:02d}" for n in range(1, 11)]
    for case in cases:
        assert case["symptom"] and case["expected_summary"] and case["source_manual"]
        assert "error_code" in case and "error_code_known" in case  # null = 코드 없음
        assert case["expect"]["must_contain"]


def test_eval_set_is_well_formed():
    cases = json.loads((ROOT / "eval" / "eval_set.json").read_text(encoding="utf-8"))
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids))
    scored = [c for c in cases if c.get("scored", True)]
    assert len(scored) >= 20  # 교재 기준: 평가 질문 20개 이상
    for case in scored:
        assert case["equipment_name"] and case["error_code"]
        assert case["expect"]["status"] in ("found", "not_found")
    assert any(c["expect"]["status"] == "not_found" for c in scored)  # 못 찾는 질문도 포함
