from functools import lru_cache
from pathlib import Path
from typing import Literal

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

    # 청킹: 서버가 읽을 인덱스를 어느 방식으로 만든 것으로 할지
    #   fixed    = 파이프라인이 500자 단위로 자른 인덱스 (FAISS_DIR)
    #   semantic = scripts/build_semantic_index.py가 의미가 바뀌는 곳에서 자른 인덱스 (FAISS_SEMANTIC_DIR)
    chunking: Literal["fixed", "semantic"] = "fixed"
    faiss_semantic_dir: Path = Path("../rag_pipeline/faiss_db/pdf_semantic")
    semantic_breakpoint_percentile: float = 90  # 인접 문장의 의미 거리가 이 백분위보다 크면 그 사이를 자른다
    semantic_min_chars: int = 150  # 이보다 짧은 청크는 만들지 않는다
    semantic_max_chars: int = 900  # 이보다 길면 강제로 자른다

    # 평가 (scripts/run_eval.py): 쉼표로 여러 개 선택  keywords | embedding | judge
    eval_methods: str = "keywords"  # 합격을 정하는 방법
    eval_info_methods: str = ""  # 계산해서 보여 주기만 하고 합격에는 쓰지 않는 방법. 떨어지면 "확인 필요"로 표시 (예: judge)
    eval_judge_model: str = "gpt-4o"  # 답변을 만드는 모델과 다른 모델로 채점해 자기 평가 편향을 줄인다
    eval_embed_threshold: float = 0.5  # 답변과 기대 답변의 임베딩 유사도가 이 값 이상이면 통과 (Q01~Q10 실측: 맞는 답 19/20 통과, 다른 질문의 기대 답 16/180 오통과)
    eval_judge_threshold: int = 4  # Judge 점수(1~5)가 이 값 이상이면 통과
    eval_pass_rule: Literal["all", "any"] = "all"  # 선택한 내용 평가를 모두 통과해야(all) / 하나라도 통과하면(any) 합격

    glossary_file: Path = Path("data/glossary.json")

    @property
    def glossary_path(self) -> Path:
        path = self.glossary_file
        return path if path.is_absolute() else (BASE_DIR / path).resolve()

    @property
    def faiss_path(self) -> Path:
        path = self.faiss_semantic_dir if self.chunking == "semantic" else self.faiss_dir
        return path if path.is_absolute() else (BASE_DIR / path).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
