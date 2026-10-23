import os
from pathlib import Path
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def build():
    print("🚀 반도체 데이터 FAISS 벡터DB 빌드 시작...")
    data_dir = BASE_DIR / "data"
    raw_docs = []
    for f in ["semiconductor_error_manual.md", "semiconductor_troubleshoot_log.md"]:
        for doc in TextLoader(str(data_dir / f), encoding="utf-8").load():
            doc.metadata["source"] = f.replace(".md", ".pdf")
            raw_docs.append(doc)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500, chunk_overlap=50, separators=["\n---\n", "\n## ", "\n\n", "\n"]
    )
    chunks = splitter.split_documents(raw_docs)
    vectorstore = FAISS.from_documents(chunks, OpenAIEmbeddings())

    target_dir = BASE_DIR / "faiss_db" / "pdf"
    target_dir.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(target_dir))
    print(f"🎉 적재 완료! ({target_dir})")


if __name__ == "__main__":
    build()
