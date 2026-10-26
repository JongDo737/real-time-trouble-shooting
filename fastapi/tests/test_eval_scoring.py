import json
import sys
from pathlib import Path

import pytest

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


def _load(folder):
    inputs = json.loads((ROOT / "eval" / folder / "inputs.json").read_text(encoding="utf-8"))
    answers = json.loads((ROOT / "eval" / folder / "answers.json").read_text(encoding="utf-8"))
    return merge_cases(inputs, answers)


def test_team_table_set_is_well_formed():
    cases = _load("q30")
    assert [c["id"] for c in cases] == [f"Q{n:02d}" for n in range(1, 31)]
    for case in cases:
        assert case["symptom"] and case["expected_summary"] and case["source_manual"]
        assert "error_code" in case and "error_code_known" in case  # error_code는 null = 코드 없음
        assert case["expect"]["must_contain"] and case["expect"]["risk_level"] in ("INFO", "WARNING", "CRITICAL")


def test_wrong_answer_set_covers_not_found_and_related_cases():
    """잘못 나와야 하는(못 찾음 · 관련 사례) 질문 10개."""
    cases = _load("q10")
    assert [c["id"] for c in cases] == [f"N{n:02d}" for n in range(1, 11)]
    kinds = {c["expect"]["status"] for c in cases}
    assert kinds == {"found", "not_found"}
    related = [c for c in cases if c["expect"]["status"] == "found"]
    assert related and all(c["expect"]["exact_match"] is False and c["expect"]["needs_review"] is True for c in related)
    for case in cases:
        assert case["equipment_name"] and case["error_code"] and case["symptom"]


def test_risk_level_is_checked_only_when_expected():
    outcome = {"status": "found", "answer": "x", "exact_match": True, "needs_review": False, "sections": [], "risk_level": "CRITICAL"}
    assert score_case({"risk_level": "CRITICAL"}, outcome) == {"risk": True}
    assert score_case({"risk_level": "WARNING"}, outcome) == {"risk": False}
    assert "risk" not in score_case({"status": "found"}, outcome)


# ---------- 입력 파일과 정답지 파일 분리 ----------

from run_eval import merge_cases  # noqa: E402

ANSWER_KEYS = {"expected_summary", "source_manual", "expect", "must_contain", "section", "risk_level", "note"}
SYSTEM_INPUT_KEYS = {"id", "category", "equipment_name", "error_code", "error_code_known", "symptom"}


def test_merge_cases_joins_inputs_and_answers_by_id():
    inputs = [{"id": "Q1", "symptom": "s1"}, {"id": "Q2", "symptom": "s2"}]
    answers = [{"id": "Q2", "expect": {"status": "found"}}, {"id": "Q1", "expected_summary": "답"}]
    merged = merge_cases(inputs, answers)
    assert [c["id"] for c in merged] == ["Q1", "Q2"]
    assert merged[0] == {"id": "Q1", "symptom": "s1", "expected_summary": "답"}
    assert merged[1]["expect"] == {"status": "found"}


def test_input_without_an_answer_stays_as_an_unscored_question():
    assert merge_cases([{"id": "P1", "symptom": "s"}], []) == [{"id": "P1", "symptom": "s"}]


@pytest.mark.parametrize(
    "inputs,answers",
    [
        ([{"id": "Q1"}], [{"id": "Q1"}, {"id": "Q1"}]),  # 정답 id 중복
        ([{"id": "Q1"}, {"id": "Q1"}], []),  # 입력 id 중복
        ([{"id": "Q1"}], [{"id": "Q9", "expect": {}}]),  # 입력에 없는 정답
    ],
)
def test_merge_cases_rejects_inconsistent_files(inputs, answers):
    with pytest.raises(ValueError):
        merge_cases(inputs, answers)


def test_q30_input_file_contains_no_answers():
    """시스템에 넣는 입력 파일에는 정답 · 채점 기준이 섞이면 안 된다."""
    inputs = json.loads((ROOT / "eval" / "q30" / "inputs.json").read_text(encoding="utf-8"))
    answers = json.loads((ROOT / "eval" / "q30" / "answers.json").read_text(encoding="utf-8"))
    assert {k for case in inputs for k in case} <= SYSTEM_INPUT_KEYS
    assert not ({k for case in answers for k in case} & {"equipment_name", "symptom", "error_code", "error_code_known"})
    assert len(inputs) == len(answers) == 30
    merge_cases(inputs, answers)  # id가 서로 맞아야 한다
