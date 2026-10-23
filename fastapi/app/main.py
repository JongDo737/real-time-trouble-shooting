import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.config import get_settings
from app.errors import register_error_handlers
from app.routers import health, rag, translate
from app.services.glossary import get_glossary
from app.services.retrieval import load_index

# uvicorn은 자기 로거만 설정하므로, 우리 로그(인덱스 로드 · 요청별 지연)가 보이도록 INFO를 켠다
logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s %(message)s")
log = logging.getLogger("app.ops")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 검색 인덱스는 시작할 때 한 번 읽는다. 없어도 서버는 뜨고, /rag-query만 503을 돌려준다.
    app.state.rag_index = None
    get_glossary(get_settings().glossary_path)  # 파일이 있으면 항목 수를 로그에 남긴다
    path = get_settings().faiss_path
    try:
        app.state.rag_index = load_index(path)
        log.info("RAG 인덱스 로드 완료: %d개 청크 (%s)", len(app.state.rag_index), path)
    except FileNotFoundError:
        log.warning("RAG 인덱스가 없습니다: %s", path)
    except Exception as exc:  # 손상된 파일 등: 원인 종류만 남기고 서버는 계속 띄운다
        log.error("RAG 인덱스 로드 실패 (%s): %s", path, type(exc).__name__)
    yield


app = FastAPI(
    title="통번역 · RAG 서비스",
    description="지부-본사 실시간 통번역과 장비 오류 해결방법 검색 (docs/api2.md)",
    version="0.1.0",
    lifespan=lifespan,
)
register_error_handlers(app)


@app.middleware("http")
async def ops_logger(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    # 경로 · 상태 · 지연만 기록한다 (발화 · 질의 원문은 저장하지 않음)
    log.info(
        {
            "path": request.url.path,
            "status": response.status_code,
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "request_id": request.state.request_id,
        }
    )
    return response


app.include_router(health.router)
app.include_router(translate.router)
app.include_router(rag.router)
