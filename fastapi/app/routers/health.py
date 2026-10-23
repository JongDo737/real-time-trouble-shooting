from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.schemas import HealthResponse

router = APIRouter(tags=["상태"])


@router.get("/health", response_model=HealthResponse, summary="서비스 · LLM · 인덱스 준비 상태")
def health(request: Request):
    settings = get_settings()
    index = getattr(request.app.state, "rag_index", None)
    llm_ready = bool(settings.openai_api_key)
    index_loaded = index is not None

    body = HealthResponse(
        status="ok" if llm_ready and index_loaded else "degraded",
        llm_ready=llm_ready,
        index_loaded=index_loaded,
        chunks=len(index) if index_loaded else 0,
    )
    return JSONResponse(status_code=200 if body.status == "ok" else 503, content=body.model_dump())
