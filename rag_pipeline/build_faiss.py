import os
import re
from pathlib import Path
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def build():
    print("🚀 반도체 데이터 FAISS 벡터DB 빌드 시작...")
    data_dir = BASE_DIR / "data"
    raw_docs = []

    # 1. 원본 마크다운 문서 로드
    for f in ["semiconductor_error_manual.md", "semiconductor_troubleshoot_log.md"]:
        file_path = data_dir / f
        if not file_path.exists():
            print(f"⚠️ 파일이 존재하지 않습니다: {file_path}")
            continue

        for doc in TextLoader(str(file_path), encoding="utf-8").load():
            doc.metadata["source"] = f.replace(".md", ".pdf")
            raw_docs.append(doc)

    # 2. 청킹 분할기 설정
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n---\n", "\n## ", "\n\n", "\n", " "],
    )

    enriched_docs = []
    chunk_counter = 0

    # 3. 문서별 청킹 및 메타데이터 헤더 주입
    for doc in raw_docs:
        text_chunks = splitter.split_text(doc.page_content)
        source_name = doc.metadata.get("source", "unknown")

        for chunk in text_chunks:
            chunk_counter += 1

            # 정규식 패턴으로 메타데이터 추출
            err_match = re.search(r"(ALARM-[A-Z0-9]+|AL\d+|ERR-[A-Z0-9]+)", chunk)
            eq_match = re.search(
                r"(Centura|Endura|Producer|Echoview|TEL|KLA|AMAT|LAM)",
                chunk,
                re.IGNORECASE,
            )
            sec_match = re.search(r"^##\s+(.+)$", chunk, re.MULTILINE)
            risk_match = re.search(r"\b(CRITICAL|WARNING|INFO)\b", chunk, re.IGNORECASE)

            error_code = err_match.group(1) if err_match else "COMMON"
            equipment = eq_match.group(1).upper() if eq_match else "COMMON"
            section = sec_match.group(1).strip() if sec_match else "General"
            risk_level = risk_match.group(1).upper() if risk_match else "INFO"

            # [핵심] 청크 본문 맨 앞에 메타데이터 헤더 주입 (임베딩 검색 정확도 향상)
            enriched_content = (
                f"[장비명: {equipment} | 에러코드: {error_code} | 섹션: {section} | 위험도: {risk_level}]\n"
                f"{chunk}"
            )

            # Document 객체 생성 (본문 + 메타데이터 딕셔너리)
            metadata = {
                "source": source_name,
                "chunk_id": chunk_counter,
                "error_code": error_code,
                "equipment": equipment,
                "section": section,
                "risk_level": risk_level,
            }
            enriched_docs.append(
                Document(page_content=enriched_content, metadata=metadata)
            )

    print(f"✂️ 메타데이터 보강 청킹 완료: 총 {len(enriched_docs)}개 청크 생성")

    # 4. 임베딩 모델 지정 및 FAISS 벡터DB 생성
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vectorstore = FAISS.from_documents(enriched_docs, embeddings)

    # 5. 로컬 디스크 저장
    target_dir = BASE_DIR / "faiss_db" / "pdf"
    target_dir.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(target_dir))
    print(f"🎉 적재 완료! ({target_dir})")


if __name__ == "__main__":
    build()
