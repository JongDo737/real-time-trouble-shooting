"""하이브리드 검색: 파이프라인이 만든 FAISS 인덱스를 읽고 BM25(Sparse) + Dense를 RRF로 합친다."""

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from app.errors import ApiError
from app.services.risk import Risk, parse_risk
from app.services.textproc import extract_code_keys, normalize_key, tokenize

# 파이프라인이 청크 맨 앞에 붙이는 헤더: [장비명: X | 에러코드: Y | 섹션: Z | 위험도: W]
_HEADER = re.compile(r"^\[장비명:.*\]\s*\n")
_UNKNOWN = "COMMON"  # 파이프라인이 장비명 · 오류코드를 못 찾았을 때 넣는 값


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str  # 헤더가 붙은 청크 본문 (LLM에 그대로 전달)
    metadata: dict = field(default_factory=dict)


def chunk_tokens(chunk: Chunk) -> list[str]:
    """BM25 색인용 토큰: 본문 + 섹션 제목 + 장비명 · 오류코드 키 (헤더의 라벨 단어는 제외)."""
    meta = chunk.metadata
    body = _HEADER.sub("", chunk.text, count=1)
    tokens = tokenize(body)

    section = meta.get("section")
    if section and section != "General":
        tokens += tokenize(str(section))
    for key in ("equipment", "error_code"):
        value = str(meta.get(key) or "")
        if value and value != _UNKNOWN:
            tokens.append(normalize_key(value))
            tokens += tokenize(value)
    return tokens


_WORDS = re.compile(r"[A-Z0-9]+")


def chunk_code_keys(chunk: Chunk) -> set[str]:
    """청크에 적혀 있는 오류코드 · 모델명의 정규화 키들. (EMO 같은 짧은 코드가 REMOTE에 걸리지 않게 단어 단위로 본다)"""
    text = unicodedata.normalize("NFKC", chunk.text)
    keys = set(extract_code_keys(text)) | set(_WORDS.findall(text.upper()))
    meta_code = str(chunk.metadata.get("error_code") or "")
    if meta_code and meta_code != _UNKNOWN:
        keys.add(normalize_key(meta_code))
    return keys


def pin_ids(ids: list[str], pinned: list[str], top_k: int) -> list[str]:
    """pinned(반드시 넣을 청크)가 상위 top_k에 없으면 맨 뒤 순위를 밀어내고 넣는다."""
    missing = [p for p in pinned if p not in ids[:top_k]]
    if not missing:
        return ids[:top_k]
    return ids[: max(top_k - len(missing), 0)] + missing


def rrf(ranked_lists: list[list[str]], k: int = 60, weights: list[float] | None = None) -> list[str]:
    """Reciprocal Rank Fusion: 점수 = Σ weight / (k + 순위). 점수가 높은 순서로 청크 ID를 돌려준다."""
    weights = weights or [1.0] * len(ranked_lists)
    scores: dict[str, float] = {}
    for weight, ids in zip(weights, ranked_lists):
        for rank, chunk_id in enumerate(ids, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + weight / (k + rank)
    return sorted(scores, key=scores.get, reverse=True)


class RagIndex:
    def __init__(self, chunks: list[Chunk], vectors: np.ndarray):
        if len(chunks) != len(vectors):
            raise ValueError("청크 수와 벡터 수가 다릅니다.")
        self.chunks = chunks
        self.by_id = {c.id: c for c in chunks}
        self.position = {c.id: i for i, c in enumerate(chunks)}
        self._code_keys = [chunk_code_keys(c) for c in chunks]
        self.vectors = np.asarray(vectors, dtype="float32")
        self.dim = int(self.vectors.shape[1]) if len(chunks) else 0
        self._bm25 = BM25Okapi([chunk_tokens(c) for c in chunks]) if chunks else None

    def __len__(self) -> int:
        return len(self.chunks)

    def dense_search(self, vector: list[float], k: int) -> list[str]:
        """질의 벡터와 가까운(L2 거리 작은) 순서의 청크 ID. 평탄(Flat) FAISS 인덱스와 같은 결과."""
        if not self.chunks:
            return []
        query = np.asarray(vector, dtype="float32")
        if query.shape[0] != self.dim:
            raise ApiError(
                503,
                "VECTORDB_UNAVAILABLE",
                f"임베딩 차원({query.shape[0]})이 인덱스 차원({self.dim})과 다릅니다. EMBEDDING_MODEL을 확인하세요.",
            )
        distances = np.linalg.norm(self.vectors - query, axis=1)
        order = np.argsort(distances, kind="stable")[:k]
        return [self.chunks[i].id for i in order]

    def chunks_with_code(self, code_key: str, tokens: list[str], limit: int = 2) -> list[str]:
        """요청한 오류코드가 글자 그대로 적힌 청크 중 BM25 점수가 높은 순서의 ID (최대 limit개)."""
        hits = [i for i, keys in enumerate(self._code_keys) if code_key in keys]
        if not hits:
            return []
        scores = self._bm25.get_scores(tokens) if self._bm25 is not None and tokens else np.zeros(len(self.chunks))
        hits.sort(key=lambda i: -scores[i])
        return [self.chunks[i].id for i in hits[:limit]]

    def continuations(self, chunk_id: str, limit: int = 2) -> list[Chunk]:
        """같은 섹션이 500자 단위로 쪼개져 이어지는 뒷부분 청크 (섹션 제목이 없어 section이 General인 청크)."""
        start = self.position[chunk_id]
        base = self.chunks[start]
        following = []
        for nxt in self.chunks[start + 1 : start + 1 + limit]:
            if nxt.metadata.get("source") != base.metadata.get("source") or nxt.metadata.get("section") != "General":
                break
            following.append(nxt)
        return following

    def risk_of(self, chunk_id: str, max_back: int = 4) -> Risk | None:
        """이 청크가 속한 항목의 위험도. 위험도 줄은 항목 맨 앞부분에 있어서, 500자로 잘린 뒷부분 청크는
        거슬러 올라가 항목의 머리 청크(섹션 제목이 있는 청크)에서 읽는다. 위험도가 적히지 않은 항목은 None."""
        start = self.position[chunk_id]
        source = self.chunks[start].metadata.get("source")
        for back in range(max_back + 1):
            index = start - back
            if index < 0 or self.chunks[index].metadata.get("source") != source:
                break
            risk = parse_risk(self.chunks[index].text)
            if risk is not None:
                return risk
            if self.chunks[index].metadata.get("section") != "General":
                break  # 항목의 머리인데 위험도 줄이 없다 = 이 항목에는 위험도 표기가 없다
        return None

    def sparse_search(self, tokens: list[str], k: int) -> list[str]:
        """BM25 점수가 높은 순서의 청크 ID. 질의 단어가 하나도 맞지 않은(0점 이하) 청크는 제외한다."""
        if self._bm25 is None or not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        order = np.argsort(-scores, kind="stable")[:k]
        return [self.chunks[i].id for i in order if scores[i] > 0]


def hybrid_search(
    index: RagIndex,
    *,
    sparse_tokens: list[str],
    dense_vector: list[float] | None,
    candidates: int,
    top_k: int,
    rrf_k: int = 60,
    sparse_weight: float = 1.0,
    dense_weight: float = 1.0,
) -> list[str]:
    """BM25와 Dense 후보를 RRF로 합쳐 상위 top_k개 ID. dense_vector가 None이면 BM25 단독."""
    ranked = [index.sparse_search(sparse_tokens, candidates)]
    weights = [sparse_weight]
    if dense_vector is not None:
        ranked.append(index.dense_search(dense_vector, candidates))
        weights.append(dense_weight)
    return rrf(ranked, k=rrf_k, weights=weights)[:top_k]


def load_index(path: Path) -> RagIndex:
    """파이프라인이 만든 FAISS 폴더(index.faiss + index.pkl)를 읽는다.

    index.pkl은 pickle이라 신뢰할 수 있는 폴더만 읽어야 한다 (LangChain 저장 형식).
    벡터는 인덱스에서 꺼내 메모리에 두고 numpy로 검색한다 (평탄 인덱스는 결과가 같음).
    """
    if not (path / "index.faiss").exists() or not (path / "index.pkl").exists():
        raise FileNotFoundError(f"FAISS 인덱스가 없습니다: {path}")

    from langchain_community.vectorstores import FAISS
    from langchain_core.embeddings import Embeddings

    class _NoEmbeddings(Embeddings):
        # 질의 임베딩은 우리가 OpenAI 클라이언트로 직접 하므로 이 객체는 쓰이지 않는다
        def embed_documents(self, texts):
            raise NotImplementedError

        def embed_query(self, text):
            raise NotImplementedError

    store = FAISS.load_local(str(path), _NoEmbeddings(), allow_dangerous_deserialization=True)
    total = store.index.ntotal
    vectors = store.index.reconstruct_n(0, total) if total else np.empty((0, store.index.d), dtype="float32")

    chunks = []
    for position in range(total):
        doc_id = store.index_to_docstore_id[position]
        doc = store.docstore.search(doc_id)
        chunks.append(Chunk(id=doc_id, text=doc.page_content, metadata=dict(doc.metadata)))
    return RagIndex(chunks, vectors)
