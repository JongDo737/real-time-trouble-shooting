import asyncio
import json

import numpy as np
import pytest

from app.services.evaluation import (
    build_judge_messages,
    cosine,
    embedding_similarity,
    judge_answer,
    judge_passes,
    overall_pass,
    parse_judge,
    parse_methods,
)
from tests.conftest import FakeLLM


def test_parse_methods_keeps_order_and_drops_duplicates():
    assert parse_methods("keywords, judge,keywords") == ["keywords", "judge"]


@pytest.mark.parametrize("value", ["", "keyword", "keywords,bleu"])
def test_parse_methods_rejects_unknown_names(value):
    with pytest.raises(ValueError):
        parse_methods(value)


def test_cosine():
    assert cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert cosine([0, 0], [1, 0]) == 0.0


def test_embedding_similarity_embeds_answer_and_reference_in_one_call():
    llm = FakeLLM()
    llm.embeddings.vector = [1.0, 0.0, 0.0]
    score = asyncio.run(embedding_similarity(llm, "fake-embedding-model", "답변", "기대 답변"))
    assert score == pytest.approx(1.0)
    assert llm.embeddings.calls[0]["input"] == ["답변", "기대 답변"]


def test_judge_prompt_carries_question_evidence_and_answer():
    messages = build_judge_messages("유량이 출렁거립니다", "2 psig", ["문서 본문"], "답변 본문")
    assert messages[0]["role"] == "system" and "different wording or synonyms are fine" in messages[0]["content"]
    user = messages[1]["content"]
    for part in ("유량이 출렁거립니다", "2 psig", "[Document 1]\n문서 본문", "답변 본문"):
        assert part in user


def test_judge_prompt_marks_missing_reference():
    assert "Reference answer:\n(none)" in build_judge_messages("q", None, [], "a")[1]["content"]


def test_parse_judge_reads_scores_and_clamps():
    scores = parse_judge(json.dumps({"relevance": 5, "faithfulness": 9, "correctness": None, "reason": "ok"}))
    assert scores == {"relevance": 5, "faithfulness": 5, "correctness": None, "reason": "ok"}


@pytest.mark.parametrize("raw", ["not json", "{}", '{"relevance": "high"}'])
def test_unreadable_judge_reply_gets_the_lowest_score(raw):
    scores = parse_judge(raw)
    assert scores["relevance"] == 1 and scores["faithfulness"] == 1


def test_judge_passes_needs_every_score_at_threshold():
    assert judge_passes({"relevance": 4, "faithfulness": 5, "correctness": None}, 4)
    assert not judge_passes({"relevance": 4, "faithfulness": 3, "correctness": 5}, 4)
    assert not judge_passes({"relevance": 5, "faithfulness": 5, "correctness": 2}, 4)


def test_judge_answer_calls_the_judge_model_in_json_mode():
    llm = FakeLLM()
    llm.completions.reply = json.dumps({"relevance": 5, "faithfulness": 4, "correctness": 5, "reason": "맞음"})
    scores = asyncio.run(judge_answer(llm, "judge-model", "q", "ref", ["doc"], "answer"))
    assert scores["faithfulness"] == 4
    call = llm.completions.calls[0]
    assert call["model"] == "judge-model" and call["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize(
    "structural,content,rule,expected",
    [
        ({}, {}, "all", None),
        ({"status": True}, {}, "all", True),
        ({"status": False}, {"judge": True}, "any", False),
        ({"status": True}, {"keywords": False, "judge": True}, "all", False),
        ({"status": True}, {"keywords": False, "judge": True}, "any", True),
        ({"status": True}, {"keywords": False, "embedding": False}, "any", False),
        ({}, {"keywords": True}, "all", True),
    ],
)
def test_overall_pass(structural, content, rule, expected):
    assert overall_pass(structural, content, rule) is expected



def test_parse_methods_allows_an_empty_list_for_info_methods():
    assert parse_methods("", allow_empty=True) == []
    assert parse_methods("judge", allow_empty=True) == ["judge"]
