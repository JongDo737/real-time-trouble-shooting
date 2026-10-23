"""RAG 흐름: 하이브리드 검색 → 평가(Judge) → 재시도(최대 N회) → 근거 기반 해결방법 생성."""

import asyncio
import json
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from app.config import Settings
from app.services.llm import chat, embed, require_model
from app.services.retrieval import Chunk, RagIndex, chunk_code_keys, hybrid_search, pin_ids
from app.services.textproc import normalize_key, query_tokens

JUDGE_PROMPT = """You are a strict relevance judge for an industrial equipment troubleshooting search system.
You get a case (equipment, error code, symptom) and numbered documents retrieved from a Korean manual / case log.
Rate from 1 to 5 how well the documents together contain what is needed to resolve THIS case:
5 = a direct fix for this equipment and error code
4 = the right case, but the fix is partial or indirect
3 = a closely related case that differs in error code or equipment
2 = loosely related
1 = unrelated
Also set exact_case: true only if the documents cover this exact equipment AND this exact error code; \
false if they only cover a related case (for example the same symptom under a different error code, or a \
different equipment). Documents that do not name any equipment are not an equipment mismatch.
The input has a line saying where the requested error code appears in the documents. If it appears in a \
document about the same symptom or equipment area, treat the case as exact even when another record of the \
case does not repeat the code. If it appears in none of the documents, exact_case is false.
If no error code was requested, judge exact_case by equipment and symptom only: true when the documents cover \
this symptom (and the equipment, if a document names one), false for a different symptom area or equipment.
If the requested error code says there is no alarm (for example NO-ALARM-...), judge by the symptom and \
treat documents about cases without an alarm code as exact.
List the numbers of the documents that are actually relevant.
Respond with JSON only: {"score": integer 1-5, "exact_case": boolean, "relevant": [document numbers], \
"reason": "one short sentence"}"""

GENERATE_PROMPT = """You are a field service engineer assistant. Answer the case using ONLY the provided documents.
Write the answer in Korean as short numbered steps. Keep safety warnings that appear in the documents.
Keep every number, threshold, torque value, and part number from the documents exactly as written.
Do not invent steps, values, or part names that are not in the documents.
If the documents do not contain a fix for this case, reply exactly: N/A"""

GENERATE_RELATED_PROMPT = """You are a field service engineer assistant. The documents describe a RELATED case, not exactly the requested one.
Start the answer with one Korean sentence that states exactly what differs between the requested case and the \
documents (for example the error code or the equipment), in the form: ※ 요청하신 <requested code or equipment>가 아니라 <code or equipment in the documents> 사례입니다.
Then give the procedure from the documents as short numbered steps in Korean. Keep safety warnings that appear in the documents.
Never present the steps as confirmed for the requested case. Keep every number, threshold, torque value, and part number \
from the documents exactly as written. Do not invent steps, values, or part names that are not in the documents.
If the documents contain nothing useful for this symptom, reply exactly: N/A"""

REWRITE_PROMPT = """Rewrite the case as one Korean search query for a Korean equipment manual and troubleshooting log.
Use the wording a manual would use: expand abbreviations, add synonyms, describe the symptom concretely.
Keep equipment names and error codes exactly as given. Output only the query."""

NOT_FOUND = "N/A"


@dataclass
class RagState:
    """진행 상황. 시간 초과로 중단돼도 지금까지의 시도 횟수와 점수를 알려 주기 위해 밖에서 들고 있는다."""

    attempts: int = 0
    last_score: float | None = None
    in_tok: int = 0
    out_tok: int = 0
    saw_hits: bool = False


@dataclass
class RagOutcome:
    status: str  # found | not_found
    attempts: int
    in_tok: int
    out_tok: int
    answer: str | None = None
    reason: str | None = None  # no_hits | low_score | deadline
    score: float | None = None
    needs_review: bool = False
    exact_match: bool | None = None  # found일 때: 같은 장비·오류코드 사례(True) / 관련 사례만(False)
    chunks: list[Chunk] = field(default_factory=list)  # 답변의 근거가 된 청크


def _case_text(equipment_name: str, error_code: str | None, symptom: str | None) -> str:
    lines = [f"Equipment: {equipment_name}"]
    if error_code:
        lines.append(f"Error code: {error_code}")
    if symptom:
        lines.append(f"Symptom: {symptom}")
    return "\n".join(lines)


def _code_hint(error_code: str, chunks: list[Chunk]) -> str:
    """요청한 오류코드가 어느 문서에 적혀 있는지 알려 준다 (평가가 같은 사례인지 판단하는 근거)."""
    key = normalize_key(error_code)
    holders = [str(n) for n, chunk in enumerate(chunks, start=1) if key in chunk_code_keys(chunk)]
    where = f"Documents {', '.join(holders)}" if holders else "none of the documents"
    return f"Requested error code {error_code} appears in: {where}"


def _with_continuations(index: RagIndex, evidence: list[Chunk]) -> list[Chunk]:
    """근거 청크에 같은 섹션의 이어지는 청크를 붙인다 (500자로 잘려 해결 단계가 뒤 청크에 있을 수 있음)."""
    ordered: list[Chunk] = []
    seen: set[str] = set()
    for chunk in evidence:
        for item in [chunk, *index.continuations(chunk.id)]:
            if item.id not in seen:
                seen.add(item.id)
                ordered.append(item)
    return ordered


def _numbered(chunks: list[Chunk]) -> str:
    return "\n\n".join(f"[Document {i}]\n{c.text}" for i, c in enumerate(chunks, start=1))


def parse_judge(raw: str, count: int) -> tuple[float, list[int], bool]:
    """(0~1 점수, 관련 문서 번호들, 같은 장비·오류코드 사례인지). 해석할 수 없으면 가장 낮은 점수로 본다."""
    try:
        data = json.loads(raw)
        score = int(data["score"])
        relevant = [int(n) for n in data.get("relevant", [])]
        exact = bool(data.get("exact_case", True))  # 모델이 빠뜨리면 같은 사례로 본다
    except (ValueError, KeyError, TypeError):
        return 0.2, [], True
    score = max(1, min(5, score))
    return score / 5, [n for n in relevant if 1 <= n <= count], exact


async def _judge(
    client, settings: Settings, state: RagState, case: str, chunks: list[Chunk], error_code: str | None
):
    model = require_model(settings.rag_judge_model, "RAG_JUDGE_MODEL")
    hint = _code_hint(error_code, chunks) if error_code else "Requested error code: not provided"
    result = await chat(
        client,
        model,
        [
            {"role": "system", "content": JUDGE_PROMPT},
            {"role": "user", "content": f"{case}\n{hint}\n\n{_numbered(chunks)}"},
        ],
        json_mode=True,
        timeout=settings.rag_llm_timeout_seconds,
    )
    state.in_tok += result.in_tok
    state.out_tok += result.out_tok
    return parse_judge(result.content, len(chunks))


async def _generate(
    client, settings: Settings, state: RagState, case: str, chunks: list[Chunk], *, related: bool = False
) -> str:
    model = require_model(settings.rag_gen_model, "RAG_GEN_MODEL")
    result = await chat(
        client,
        model,
        [
            {"role": "system", "content": GENERATE_RELATED_PROMPT if related else GENERATE_PROMPT},
            {"role": "user", "content": f"{case}\n\n{_numbered(chunks)}"},
        ],
        timeout=settings.rag_llm_timeout_seconds,
    )
    state.in_tok += result.in_tok
    state.out_tok += result.out_tok
    return result.content.strip()


async def _rewrite(client, settings: Settings, state: RagState, case: str) -> str:
    model = require_model(settings.rag_gen_model, "RAG_GEN_MODEL")
    result = await chat(
        client,
        model,
        [{"role": "system", "content": REWRITE_PROMPT}, {"role": "user", "content": case}],
        timeout=settings.rag_llm_timeout_seconds,
    )
    state.in_tok += result.in_tok
    state.out_tok += result.out_tok
    return result.content.strip()


async def _run(
    client: AsyncOpenAI,
    settings: Settings,
    index: RagIndex,
    state: RagState,
    *,
    equipment_name: str,
    error_code: str | None,
    symptom: str | None,
) -> RagOutcome:
    case = _case_text(equipment_name, error_code, symptom)
    total_attempts = 1 + settings.rag_max_retries
    default_dense_query = symptom or " ".join(p for p in (equipment_name, error_code, "해결방법") if p)
    rewritten: str | None = None

    for number in range(1, total_attempts + 1):
        state.attempts = number
        # 시도 1: Hybrid / 시도 2: Dense 질의 재작성 / 시도 3(마지막): 의미 검색 없이 BM25 단독, 후보 확대
        bm25_only = number == total_attempts and total_attempts > 2
        top_k = settings.rag_top_k * (2 if bm25_only else 1)

        if number >= 2 and rewritten is None:
            rewritten = await _rewrite(client, settings, state, case)

        dense_query = rewritten if (number >= 2 and rewritten) else default_dense_query
        extra_text = " ".join(t for t in (symptom, rewritten) if t) if number >= 2 else (symptom or "")
        sparse = query_tokens(equipment_name=equipment_name, error_code=error_code, extra_text=extra_text)

        dense_vector = None
        if not bm25_only:
            dense_vector = await embed(
                client, settings.embedding_model, dense_query, timeout=settings.rag_llm_timeout_seconds
            )

        ids = hybrid_search(
            index,
            sparse_tokens=sparse,
            dense_vector=dense_vector,
            candidates=settings.rag_candidates * (2 if bm25_only else 1),
            top_k=top_k,
            rrf_k=settings.rag_rrf_k,
            sparse_weight=settings.rag_sparse_weight,
            dense_weight=settings.rag_dense_weight,
        )
        # 요청한 오류코드가 글자 그대로 적힌 청크는 Dense 순위에 밀려도 평가에 반드시 보낸다
        pinned = index.chunks_with_code(normalize_key(error_code), sparse, limit=2) if error_code else []
        ids = pin_ids(ids, pinned, top_k)
        if not ids:
            continue  # 후보가 없으면 LLM을 호출하지 않고 다음 시도로 넘어간다
        state.saw_hits = True

        chunks = [index.by_id[i] for i in ids]
        score, relevant, exact = await _judge(client, settings, state, case, chunks, error_code)
        state.last_score = score
        if score < settings.rag_score_threshold:
            continue

        evidence = _with_continuations(index, [chunks[n - 1] for n in relevant] or chunks[:3])
        # 관련 사례만 있으면(오류코드 · 장비가 다름) 무엇이 다른지 밝히는 답변을 만들고 재시도하지 않는다
        answer = await _generate(client, settings, state, case, evidence, related=not exact)
        if not answer or answer.upper() == NOT_FOUND:
            continue  # 평가는 통과했지만 문서에 해결방법이 없다고 판단 → 다음 시도

        return RagOutcome(
            status="found",
            attempts=number,
            in_tok=state.in_tok,
            out_tok=state.out_tok,
            answer=answer,
            score=score,
            # 관련 사례만 찾았거나, 점수가 합격선 바로 위이거나, 의미 검색 없이 키워드만으로 통과한 경우는 사람이 확인하도록 표시
            needs_review=(not exact) or score < settings.rag_review_upper or bm25_only,
            exact_match=exact,
            chunks=evidence,
        )

    return _not_found(state, reason="low_score" if state.saw_hits else "no_hits")


def _not_found(state: RagState, reason: str) -> RagOutcome:
    return RagOutcome(
        status="not_found",
        reason=reason,
        attempts=state.attempts,
        in_tok=state.in_tok,
        out_tok=state.out_tok,
        score=state.last_score,
    )


async def run_rag(
    client: AsyncOpenAI,
    settings: Settings,
    index: RagIndex,
    *,
    equipment_name: str,
    error_code: str | None = None,
    symptom: str | None = None,
) -> RagOutcome:
    state = RagState()
    try:
        return await asyncio.wait_for(
            _run(
                client,
                settings,
                index,
                state,
                equipment_name=equipment_name,
                error_code=error_code,
                symptom=symptom,
            ),
            timeout=settings.rag_deadline_seconds,
        )
    except asyncio.TimeoutError:
        return _not_found(state, reason="deadline")
