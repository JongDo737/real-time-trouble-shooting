import os
from pathlib import Path
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# 1. 저장된 FAISS DB 로드
db_path = BASE_DIR / "faiss_db" / "pdf"
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

vectorstore = FAISS.load_local(
    str(db_path), embeddings=embeddings, allow_dangerous_deserialization=True
)

total_chunks = vectorstore.index.ntotal
print(f"📦 [총 벡터(청크) 개수]: {total_chunks}개\n")

# 2. 첫 3개 청크의 메타데이터 및 본문 헤더 확인
print("=" * 60)
print("🔍 [샘플 청크 메타데이터 확인]")
print("=" * 60)

# docstore에서 앞의 3개 문서 추출
sample_doc_ids = list(vectorstore.docstore._dict.keys())[:3]
for idx, doc_id in enumerate(sample_doc_ids, start=1):
    doc = vectorstore.docstore._dict[doc_id]
    print(f"\n[청크 #{idx}]")
    print(f"  🏷️ 메타데이터: {doc.metadata}")
    print(f"  📄 본문 첫 2줄 미리보기:")
    first_two_lines = "\n".join(doc.page_content.splitlines()[:2])
    print(f"     {first_two_lines}")

# 3. 실제 검색 테스트 (에러코드 질의)
print("\n" + "=" * 60)
print("🎯 [실제 검색 테스트: 'ALARM-402 Centura'] 결과")
print("=" * 60)

results = vectorstore.similarity_search_with_score(
    "ALARM-402 Centura RF 반사파 에러", k=1
)
for doc, score in results:
    print(f"  유사도 거리 점수: {score:.4f} (0에 가까울수록 일치)")
    print(f"  검색된 메타데이터: {doc.metadata}")
    print(f"  본문 내용 요약:\n{doc.page_content[:200]}...")
