from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # fastapi/
ENV_FILE = BASE_DIR.parent / ".env"  # 프로젝트 루트의 .env (다른 서비스와 같이 씀)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    # LLM (OpenAI 호환)
    openai_api_key: str = ""
    llm_base_url: str = ""
    llm_timeout_seconds: float = 10  # 번역 호출 제한 (실시간이라 짧게)
    rag_llm_timeout_seconds: float = 20  # RAG의 평가 · 질의 재작성 · 답변 생성 · 임베딩 호출 한 번의 제한

    # 용도별 모델
    translate_model: str = "gpt-4o"  # 임시: 번역 품질 확인 시 DeepL과 비교
    rag_judge_model: str = "gpt-6-luna"
    rag_gen_model: str = "gpt-6-luna"
    embedding_model: str = "text-embedding-3-small"

    # RAG
    faiss_dir: Path = Path("../rag_pipeline/faiss_db/pdf")
    rag_top_k: int = 5  # 합친 뒤 평가에 넘길 청크 수
    rag_candidates: int = 10  # 검색기(BM25, Dense)마다 가져올 후보 수
    rag_rrf_k: int = 60
    rag_sparse_weight: float = 1.0
    rag_dense_weight: float = 1.0
    rag_score_threshold: float = 0.6
    rag_review_upper: float = 0.75
    rag_max_retries: int = 1  # 재시도 1회 = 총 최대 2번 시도 (2로 올리면 3번째로 BM25 단독 시도가 추가됨)
    rag_deadline_seconds: float = 20  # 한 번의 /rag-query 전체 대기 시간 상한

    glossary_file: Path = Path("data/glossary.json")

    @property
    def glossary_path(self) -> Path:
        path = self.glossary_file
        return path if path.is_absolute() else (BASE_DIR / path).resolve()

    @property
    def faiss_path(self) -> Path:
        path = self.faiss_dir
        return path if path.is_absolute() else (BASE_DIR / path).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
