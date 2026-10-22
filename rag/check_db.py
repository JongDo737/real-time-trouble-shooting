from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

load_dotenv("rag/.env")

# FAISS 로드
db = FAISS.load_local("rag/faiss_db/pdf", OpenAIEmbeddings(), allow_dangerous_deserialization=True)

print(f"\n총 적재된 벡터(청크) 수: {db.index.ntotal}개")

# 테스트 검색 1건
docs = db.similarity_search("플라즈마가 안 켜져요", k=5)
if docs:
    print("\n[✅ 테스트 검색 성공!]")
    print(f"• 출처(Source): {docs[0].metadata.get('source')}")
    print(f"• 본문 미리보기:\n{docs[0].page_content[:200].strip()}...\n")
