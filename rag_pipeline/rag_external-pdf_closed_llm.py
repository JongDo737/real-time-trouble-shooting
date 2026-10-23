import os
import re
from pathlib import Path
from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader  # (PDF면 PdfReader)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

# 1. 환경변수 (.env) 로드
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# 2. 문서 로딩 (반도체 매뉴얼/로그)
data_dir = BASE_DIR / "data"
raw_docs = []
for f in ["semiconductor_error_manual.md", "semiconductor_troubleshoot_log.md"]:
    for doc in TextLoader(str(data_dir / f), encoding="utf-8").load():
        doc.metadata["source"] = f.replace(".md", ".pdf")
        raw_docs.append(doc)

# 3. 청킹 및 메타데이터 헤더 주입
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500, chunk_overlap=50, separators=["\n---\n", "\n## ", "\n\n", "\n", " "]
)
enriched_docs = []
for doc in raw_docs:
    for chunk in splitter.split_text(doc.page_content):
        err = re.search(r"(ALARM-[A-Z0-9]+|AL\d+|ERR-[A-Z0-9]+)", chunk)
        eq = re.search(
            r"(Centura|Endura|Producer|Echoview|TEL|KLA|AMAT|LAM)", chunk, re.IGNORECASE
        )
        sec = re.search(r"^##\s+(.+)$", chunk, re.MULTILINE)
        risk = re.search(r"\b(CRITICAL|WARNING|INFO)\b", chunk, re.IGNORECASE)

        equipment = eq.group(1).upper() if eq else "COMMON"
        error_code = err.group(1) if err else "COMMON"
        section = sec.group(1).strip() if sec else "General"
        risk_level = risk.group(1).upper() if risk else "INFO"

        header = f"[장비명: {equipment} | 에러코드: {error_code} | 섹션: {section} | 위험도: {risk_level}]\n"
        meta = {
            "source": doc.metadata["source"],
            "equipment": equipment,
            "error_code": error_code,
            "section": section,
            "risk_level": risk_level,
        }
        enriched_docs.append(Document(page_content=header + chunk, metadata=meta))

# 4. 임베딩 및 FAISS 저장
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = FAISS.from_documents(enriched_docs, embeddings)

target_dir = BASE_DIR / "faiss_db" / "pdf"
target_dir.mkdir(parents=True, exist_ok=True)
vectorstore.save_local(str(target_dir))
print("🎉 FAISS 적재 완료!")
