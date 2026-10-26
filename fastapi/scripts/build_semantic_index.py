"""Semantic 청킹으로 검색 인덱스를 따로 만든다 (파이프라인의 인덱스는 건드리지 않는다).

사용:
    python scripts/build_semantic_index.py [--data-dir ../rag_pipeline/data] [--out <폴더>]

같은 원본 문서(rag_pipeline/data/*.md)를 읽어서 글자 수가 아니라 의미가 바뀌는 곳에서 자르고,
파이프라인과 같은 형식(헤더 · 메타데이터)으로 FAISS 인덱스를 저장한다.
서버가 이 인덱스를 읽게 하려면 .env에 CHUNKING=semantic 을 넣는다.

조절 값은 .env: SEMANTIC_BREAKPOINT_PERCENTILE, SEMANTIC_MIN_CHARS, SEMANTIC_MAX_CHARS
"""

import argparse
import asyncio
import statistics
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.services.llm import get_llm_client  # noqa: E402
from app.services.semantic_chunking import (  # noqa: E402
    chunk_block,
    distances,
    split_units,
    threshold,
    windows,
    with_header,
)

SOURCES = ["semiconductor_error_manual.md", "semiconductor_troubleshoot_log.md"]  # build_faiss.py와 같은 문서
BATCH = 96


async def embed_many(client, model: str, texts: list[str]) -> np.ndarray:
    vectors: list[list[float]] = []
    for start in range(0, len(texts), BATCH):
        res = await client.embeddings.create(model=model, input=texts[start : start + BATCH])
        vectors += [item.embedding for item in res.data]
    return np.array(vectors, dtype="float32")


async def chunk_document(client, settings, text: str) -> list[str]:
    blocks = split_units(text)
    # 1) 모든 블록의 문장 묶음을 한 번에 임베딩하고, 2) 블록 안에서 인접 거리를 잰다
    flat = [w for units in blocks for w in windows(units)]
    vectors = await embed_many(client, settings.embedding_model, flat)
    per_block, position = [], 0
    for units in blocks:
        per_block.append(distances(vectors[position : position + len(units)]))
        position += len(units)

    cut = threshold([d for gaps in per_block for d in gaps], settings.semantic_breakpoint_percentile)
    chunks: list[str] = []
    for units, gaps in zip(blocks, per_block):
        chunks += chunk_block(units, gaps, cut, min_chars=settings.semantic_min_chars, max_chars=settings.semantic_max_chars)
    return chunks


async def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Semantic 청킹 인덱스 빌드")
    parser.add_argument("--data-dir", default=str(ROOT.parent / "rag_pipeline" / "data"))
    parser.add_argument("--out", default=str(settings.faiss_semantic_dir if settings.faiss_semantic_dir.is_absolute()
                                              else (ROOT / settings.faiss_semantic_dir).resolve()))
    args = parser.parse_args()

    from langchain_community.vectorstores import FAISS
    from langchain_core.documents import Document
    from langchain_core.embeddings import Embeddings

    class _NoEmbeddings(Embeddings):  # 벡터는 우리가 직접 만들어 넣으므로 이 객체는 쓰이지 않는다
        def embed_documents(self, texts):
            raise NotImplementedError

        def embed_query(self, text):
            raise NotImplementedError

    client = get_llm_client(settings)
    docs, texts, counter = [], [], 0
    for name in SOURCES:
        path = Path(args.data_dir) / name
        if not path.exists():
            print(f"⚠️ 파일이 없습니다: {path}")
            continue
        chunks = await chunk_document(client, settings, path.read_text(encoding="utf-8"))
        print(f"  {name}: {len(chunks)}개 청크")
        for chunk in chunks:
            counter += 1
            content, meta = with_header(chunk)
            texts.append(content)
            docs.append(Document(page_content=content, metadata={
                "source": name.replace(".md", ".pdf"), "chunk_id": counter, "error_code": meta.error_code,
                "equipment": meta.equipment, "section": meta.section, "risk_level": meta.risk_level,
            }))

    vectors = await embed_many(client, settings.embedding_model, texts)
    store = FAISS.from_embeddings(
        list(zip(texts, vectors.tolist())), _NoEmbeddings(),
        metadatas=[d.metadata for d in docs], ids=[str(uuid.uuid4()) for _ in docs],
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    store.save_local(str(out))

    lengths = [len(t) for t in texts]
    print(f"\nSemantic 청킹 완료: {len(texts)}개 청크 | 길이 평균 {statistics.mean(lengths):.0f}자, "
          f"최소 {min(lengths)}자, 최대 {max(lengths)}자")
    print(f"설정: 분할 백분위 {settings.semantic_breakpoint_percentile}, 최소 {settings.semantic_min_chars}자, "
          f"최대 {settings.semantic_max_chars}자")
    print(f"저장: {out}\n서버에서 쓰려면 .env에 CHUNKING=semantic")


if __name__ == "__main__":
    asyncio.run(main())
