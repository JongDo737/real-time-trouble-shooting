import sys
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from dotenv import load_dotenv

# 1. 환경변수 및 벡터 DB 로드
load_dotenv("rag/.env")
db = FAISS.load_local(
    "rag/faiss_db/pdf", OpenAIEmbeddings(), allow_dangerous_deserialization=True
)

# 2. 질문 받기 (기본 질문 또는 터미널 입력 질문)
query = (
    sys.argv[1]
    if len(sys.argv) > 1
    else "13.56MHz 반사파가 12%까지 튈 때 조치법 알려줘"
)

# 3. 벡터 검색 (상위 2개 청크 추출)
docs = db.similarity_search(query, k=2)
context = "\n\n".join([d.page_content for d in docs])
sources = list(set([d.metadata.get("source", "알 수 없음") for d in docs]))

# 4. LLM 질의 (GPT-4o)
llm = ChatOpenAI(model="gpt-4o", temperature=0.2)
prompt = f"""당신은 반도체 설비 유지보수 FSE 전문 AI 어시스턴트입니다.
아래 제공된 매뉴얼 및 트러블슈팅 이력에 근거해서만 답변하세요.

[참고 문서]
{context}

[엔지니어 질문]
{query}

[답변 원칙]
- 위험도 등급(CRITICAL/WARNING/INFO)을 명시하세요.
- 번호 매긴 단계별 구체적 조치 SOP를 작성하세요.
"""

print(f"\n❓ [질문]: {query}\n" + "=" * 50)
response = llm.invoke(prompt)

print(response.content)
print("=" * 50)
print(f"📚 [참조 출처]: {sources}\n")
