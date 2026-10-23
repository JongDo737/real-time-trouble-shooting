import time

from fastapi import APIRouter, Depends, Request
from openai import AsyncOpenAI

from app.config import Settings, get_settings
from app.errors import ApiError
from app.schemas import ErrorResponse, RagRequest, RagResponse, Source, Usage
from app.services.llm import get_llm_client
from app.services.rag import run_rag
from app.services.retrieval import RagIndex

router = APIRouter(tags=["해결방법 검색"])


def get_rag_index(request: Request) -> RagIndex:
    index = getattr(request.app.state, "rag_index", None)
    if index is None:
        raise ApiError(
            503,
            "VECTORDB_UNAVAILABLE",
            "검색 인덱스가 로드되지 않았습니다. FAISS_DIR 경로와 인덱스 파일(index.faiss, index.pkl)을 확인하세요.",
        )
    return index


def _sources(chunks) -> list[Source]:
    seen, sources = set(), []
    for chunk in chunks:
        doc = chunk.metadata.get("source") or "unknown"
        section = chunk.metadata.get("section")
        section = None if section in (None, "General") else section
        if (doc, section) not in seen:
            seen.add((doc, section))
            sources.append(Source(doc=doc, section=section))
    return sources


def _message(outcome) -> str | None:
    if outcome.status != "found":
        return "검색 결과 없음"
    if outcome.exact_match is False:
        return "요청한 장비·오류코드와 정확히 일치하는 사례가 아니라 관련 사례입니다. 확인이 필요합니다."
    return None


@router.post(
    "/rag-query",
    response_model=RagResponse,
    responses={422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    summary="장비명 · 오류코드로 해결방법 검색",
)
async def rag_query(
    req: RagRequest,
    settings: Settings = Depends(get_settings),
    client: AsyncOpenAI = Depends(get_llm_client),
    index: RagIndex = Depends(get_rag_index),
):
    started = time.perf_counter()
    outcome = await run_rag(
        client,
        settings,
        index,
        equipment_name=req.equipment_name,
        error_code=req.error_code,
        symptom=req.symptom,
    )

    found = outcome.status == "found"
    return RagResponse(
        session_id=req.session_id,
        request_id=req.request_id,
        status=outcome.status,
        answer=outcome.answer,
        message=_message(outcome),
        reason=outcome.reason,
        sources=_sources(outcome.chunks),
        score=outcome.score,
        attempts=outcome.attempts,
        needs_review=outcome.needs_review,
        exact_match=outcome.exact_match,
        handoff=not found,
        latency_ms=round((time.perf_counter() - started) * 1000),
        usage=Usage(in_tok=outcome.in_tok, out_tok=outcome.out_tok),
    )
