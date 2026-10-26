"""평가 보조 (scripts/run_eval.py에서 사용): 키워드 채점 옆에 두는 의미 기반 평가 두 가지.

- embedding: 답변과 기대 답변의 임베딩 코사인 유사도 (표현이 달라도 의미가 같으면 높다)
- judge: LLM이 채점자 역할로 관련성 · 충실성 · (기대 답변이 있으면) 정확성을 1~5점으로 채점한다
  (SKALA RAG Pipeline p.156~157: 평가 기준을 명확히 쓰고, CoT + Form-filling 출력으로 고정)

어떤 방법을 쓸지는 .env의 EVAL_METHODS (예: keywords,embedding,judge).
"""

import json

import numpy as np

from app.services.llm import chat

METHODS = ("keywords", "embedding", "judge")


def parse_methods(value: str, *, allow_empty: bool = False) -> list[str]:
    """쉼표로 적은 평가 방법 목록. 모르는 이름이면 오타를 알려 준다."""
    methods = [m.strip().lower() for m in value.split(",") if m.strip()]
    unknown = [m for m in methods if m not in METHODS]
    if unknown or (not methods and not allow_empty):
        raise ValueError(f"EVAL_METHODS는 {', '.join(METHODS)} 중에서 쉼표로 골라 주세요 (받은 값: {value!r})")
    return list(dict.fromkeys(methods))


def cosine(a, b) -> float:
    a, b = np.asarray(a, dtype="float64"), np.asarray(b, dtype="float64")
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(a @ b / denom) if denom else 0.0


async def embedding_similarity(client, model: str, answer: str, reference: str, *, timeout: float | None = None) -> float:
    kwargs = {"model": model, "input": [answer, reference]}
    if timeout is not None:
        kwargs["timeout"] = timeout
    res = await client.embeddings.create(**kwargs)
    return cosine(res.data[0].embedding, res.data[1].embedding)


JUDGE_PROMPT = """You are an expert evaluator of a troubleshooting assistant for semiconductor equipment.
Rate the answer using ONLY the question, the evidence documents, and (if given) the reference answer.

Criteria (each 1-5):
- relevance: Does the answer directly address the question?
- faithfulness: Is every claim in the answer (numbers, part numbers, steps, thresholds) supported by the evidence documents? Any unsupported or contradicted claim lowers the score.
- correctness: Does the answer contain the key facts of the reference answer? Judge by meaning; different wording or synonyms are fine, and extra correct detail is not a penalty. Use null when no reference answer is given.

Steps: 1) Read the question and the evidence. 2) Compare the answer with the evidence claim by claim. 3) Assign the scores.
Respond with JSON only: {"relevance": int, "faithfulness": int, "correctness": int or null, "reason": "one short sentence"}"""


def build_judge_messages(question: str, reference: str | None, evidence: list[str], answer: str) -> list[dict]:
    docs = "\n\n".join(f"[Document {i}]\n{text}" for i, text in enumerate(evidence, start=1)) or "(none)"
    user = (
        f"Question:\n{question}\n\nReference answer:\n{reference or '(none)'}\n\n"
        f"Evidence documents:\n{docs}\n\nAnswer to evaluate:\n{answer}"
    )
    return [{"role": "system", "content": JUDGE_PROMPT}, {"role": "user", "content": user}]


def _score(value) -> int | None:
    try:
        return max(1, min(5, int(value)))
    except (TypeError, ValueError):
        return None


def parse_judge(raw: str) -> dict:
    """모델 출력을 점수로 바꾼다. 해석할 수 없으면 가장 낮은 점수로 보고 이유를 남긴다."""
    try:
        data = json.loads(raw)
        return {
            "relevance": _score(data["relevance"]) or 1,
            "faithfulness": _score(data["faithfulness"]) or 1,
            "correctness": _score(data.get("correctness")),
            "reason": str(data.get("reason", ""))[:300],
        }
    except (ValueError, KeyError, TypeError):
        return {"relevance": 1, "faithfulness": 1, "correctness": None, "reason": "채점 결과를 해석하지 못했습니다."}


async def judge_answer(client, model: str, question: str, reference: str | None, evidence: list[str], answer: str,
                       *, timeout: float | None = None) -> dict:
    result = await chat(client, model, build_judge_messages(question, reference, evidence, answer),
                        json_mode=True, timeout=timeout)
    return parse_judge(result.content)


def judge_passes(scores: dict, threshold: int) -> bool:
    values = [scores["relevance"], scores["faithfulness"]]
    if scores.get("correctness") is not None:
        values.append(scores["correctness"])
    return all(v >= threshold for v in values)


def overall_pass(structural: dict[str, bool], content: dict[str, bool], rule: str) -> bool | None:
    """구조 확인(찾음 · 같은 사례 · 근거 섹션 등)은 모두 맞아야 하고, 내용 평가는 규칙(all/any)에 따른다.

    확인할 것이 하나도 없으면 None(채점 대상 아님).
    """
    if not structural and not content:
        return None
    if not all(structural.values()):
        return False
    if not content:
        return True
    return all(content.values()) if rule == "all" else any(content.values())
