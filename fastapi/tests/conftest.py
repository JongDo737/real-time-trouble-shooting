import asyncio
import json
import os
from types import SimpleNamespace

# app을 import하기 전에 설정값을 고정한다 (실제 .env · 키에 의존하지 않음)
os.environ["OPENAI_API_KEY"] = ""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.routers.rag import get_rag_index
from app.services.llm import get_llm_client
from app.services.retrieval import Chunk, RagIndex


def llm_json(translation="Hello", source_lang="ko") -> str:
    """source_lang가 auto일 때 모델이 돌려주는 JSON 응답."""
    return json.dumps({"translation": translation, "source_lang": source_lang})


def judge_json(score: int, relevant=(1,), exact: bool = True) -> str:
    return json.dumps({"score": score, "exact_case": exact, "relevant": list(relevant), "reason": "test"})


class FakeCompletions:
    """OpenAI `chat.completions`를 흉내 낸다.

    - queue에 응답을 넣어 두면 호출 순서대로 하나씩 꺼내 쓰고, 비면 reply를 쓴다.
    - 응답이 예외면 그 예외를 발생시킨다. delay가 있으면 그만큼 기다린 뒤 응답한다.
    """

    def __init__(self):
        self.reply = "The cooling fan is not running."
        self.queue: list = []
        self.delay = 0.0
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.delay:
            await asyncio.sleep(self.delay)
        reply = self.queue.pop(0) if self.queue else self.reply
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=reply))],
            usage=SimpleNamespace(prompt_tokens=120, completion_tokens=15),
        )


def keyword_vector(text: str) -> list[float]:
    """3차원 가짜 임베딩: 키워드가 있는 축으로 향한다. (냉각 팬 / 유량 / 플라즈마)"""
    lowered = text.lower()
    vector = [
        1.0 if ("냉각" in lowered or "fan" in lowered) else 0.0,
        1.0 if ("유량" in lowered or "flow" in lowered or "mfc" in lowered) else 0.0,
        1.0 if ("플라즈마" in lowered or "plasma" in lowered or "반사파" in lowered) else 0.0,
    ]
    return vector if any(vector) else [0.3, 0.3, 0.3]


class FakeEmbeddings:
    def __init__(self):
        self.calls: list[dict] = []
        self.error: Exception | None = None
        self.vector: list[float] | None = None

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        vector = self.vector or keyword_vector(kwargs["input"])
        return SimpleNamespace(data=[SimpleNamespace(embedding=vector)])


class FakeLLM:
    def __init__(self):
        self.chat = SimpleNamespace(completions=FakeCompletions())
        self.embeddings = FakeEmbeddings()

    @property
    def completions(self) -> FakeCompletions:
        return self.chat.completions


def make_settings(**overrides) -> Settings:
    values = {
        "openai_api_key": "test-key",
        "translate_model": "fake-translate-model",
        "rag_judge_model": "fake-judge-model",
        "rag_gen_model": "fake-gen-model",
        "embedding_model": "fake-embedding-model",
        "glossary_file": "/nonexistent/glossary.json",  # 실제 data/glossary.json의 영향을 받지 않는다
        **overrides,
    }
    # _env_file=None: 프로젝트 루트 .env의 값이 테스트에 섞이지 않게 한다
    return Settings(_env_file=None, **values)


def sample_chunks() -> list[Chunk]:
    """파이프라인이 만드는 형식(헤더 + 본문, 메타데이터)을 흉내 낸 청크."""
    log = "semiconductor_troubleshoot_log.pdf"
    manual = "semiconductor_error_manual.pdf"
    return [
        Chunk(
            id="c-mfc-1",
            text="[장비명: COMMON | 에러코드: AL40 | 섹션: [CASE-03] 가스 박스 MFC 유량 출렁거림 | 위험도: INFO]\n"
            "## [CASE-03] 가스 박스 MFC 유량 출렁거림 및 AL40 알람\n레귤레이터를 2 psig 단위로 상향 조정하자 유량 헌팅이 소멸했다.",
            metadata={"source": log, "error_code": "AL40", "equipment": "COMMON", "section": "[CASE-03] MFC 유량 출렁거림"},
        ),
        Chunk(
            id="c-mfc-2",  # 같은 섹션의 뒤쪽 청크: 파이프라인 정규식이 코드를 못 찾아 COMMON이 된 경우
            text="[장비명: COMMON | 에러코드: COMMON | 섹션: General | 위험도: INFO]\n"
            "제어 밸브 양단 압력 평형 후 Zero 버튼을 5초 이상 눌러 영점을 재설정했다. 유량 오차 ±0.5% 이내.",
            metadata={"source": log, "error_code": "COMMON", "equipment": "COMMON", "section": "General"},
        ),
        Chunk(
            id="c-rf-1",
            text="[장비명: CENTURA | 에러코드: ALARM-402 | 섹션: [SPEC-01] RF Generator | 위험도: WARNING]\n"
            "## [SPEC-01] RF Power Generator ALARM-402\n플라즈마 반사파가 10%를 넘으면 매처 가변 커패시터를 점검한다.",
            metadata={"source": manual, "error_code": "ALARM-402", "equipment": "CENTURA", "section": "[SPEC-01] RF Generator", "risk_level": "WARNING"},
        ),
        Chunk(
            id="c-fan-1",
            text="[장비명: COMMON | 에러코드: ALARM-777 | 섹션: [CASE-09] 냉각 팬 정지 | 위험도: INFO]\n"
            "냉각 팬 커넥터 체결 상태를 확인하고 팬 날개의 이물질을 제거한다.",
            metadata={"source": log, "error_code": "ALARM-777", "equipment": "COMMON", "section": "[CASE-09] 냉각 팬 정지"},
        ),
    ]


def sample_index() -> RagIndex:
    chunks = sample_chunks()
    # 청크 벡터는 가짜 임베딩과 같은 규칙(키워드 축)으로 만든다
    vectors = np.array([keyword_vector(c.text) for c in chunks], dtype="float32")
    return RagIndex(chunks, vectors)


@pytest.fixture
def llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture(scope="session")
def index() -> RagIndex:
    return sample_index()  # Kiwi 로딩이 있어 세션에 한 번만 만든다


@pytest.fixture(autouse=True)
def override_dependencies(llm, index):
    app.dependency_overrides[get_settings] = lambda: make_settings()
    app.dependency_overrides[get_llm_client] = lambda: llm
    app.dependency_overrides[get_rag_index] = lambda: index
    yield
    app.dependency_overrides.clear()
    app.state.rag_index = None


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


TRANSLATE_BODY = {
    "session_id": "call-0007",
    "utterance_id": "u-0012",
    "text": "냉각 팬이 안 돌아가고 ALARM-402 오류가 떠요.",
    "source_lang": "ko",
    "target_lang": "en",
}

RAG_BODY = {
    "session_id": "call-0007",
    "request_id": "q-0003",
    "equipment_name": "Brooks GF40",
    "error_code": "AL40",
    "symptom": "유량이 출렁거립니다",
}
