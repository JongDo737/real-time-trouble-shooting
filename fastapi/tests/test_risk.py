import pytest

from app.services.risk import Risk, highest, parse_risk
from tests.conftest import RAG_BODY, judge_json, sample_index

ANSWER = "1. 레귤레이터를 조정합니다."


@pytest.mark.parametrize(
    "text,expected",
    [
        ("## 제목\n- 위험도: CRITICAL (인터록·EMO 오조작 시 인명 위험)\n- 관련 장비: X", Risk("CRITICAL", "인터록·EMO 오조작 시 인명 위험")),
        ("- 위험도: warning (소문자도 읽는다)", Risk("WARNING", "소문자도 읽는다")),
        ("  * 위험도: INFO", Risk("INFO", None)),
        ("위험도: WARNING (목록 표시 없이도)", Risk("WARNING", "목록 표시 없이도")),
    ],
)
def test_parse_risk_reads_the_risk_line(text, expected):
    assert parse_risk(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "본문에 CRITICAL 이라는 단어만 있다",
        "위험도 등급은 각 항목의 위험도 줄을 따른다.",  # 문서 머리말: 줄 형식이 아니다
        "[장비명: COMMON | 에러코드: AL40 | 섹션: General | 위험도: CRITICAL]\n본문",  # 파이프라인 헤더는 믿지 않는다
    ],
)
def test_parse_risk_ignores_everything_but_the_risk_line(text):
    assert parse_risk(text) is None


def test_highest_picks_the_most_dangerous_level():
    risks = [Risk("INFO"), None, Risk("CRITICAL", "인명"), Risk("WARNING")]
    assert highest(risks) == Risk("CRITICAL", "인명")
    assert highest([None, None]) is None
    assert highest([]) is None


def test_highest_keeps_the_first_of_equal_levels():
    assert highest([Risk("WARNING", "첫째"), Risk("WARNING", "둘째")]).reason == "첫째"


# ---------- 인덱스: 500자로 잘린 뒷부분 청크는 항목의 머리에서 읽는다 ----------


def test_risk_of_reads_the_chunk_itself():
    index = sample_index()
    assert index.risk_of("c-rf-1") == Risk("CRITICAL", "방전·아크로 급전 부품 즉시 손상")  # 본문 줄이 헤더(WARNING)보다 우선


def test_risk_of_walks_back_from_a_continuation_chunk():
    index = sample_index()
    assert index.risk_of("c-mfc-2").level == "WARNING"  # c-mfc-2는 c-mfc-1의 뒷부분 (섹션이 General)


def test_risk_of_is_none_when_the_item_has_no_risk_line():
    assert sample_index().risk_of("c-fan-1") is None  # 섹션 제목이 있는데 위험도 줄이 없다


# ---------- API 응답 ----------


def post(client, **overrides):
    return client.post("/rag-query", json={**RAG_BODY, **overrides})


def test_response_carries_the_risk_of_the_evidence(client, llm):
    llm.completions.queue = [judge_json(5, relevant=[1]), ANSWER]
    body = post(client).json()
    assert body["status"] == "found"
    assert body["risk_level"] == "WARNING"
    assert body["risk_reason"].startswith("유량 이탈")


def test_response_risk_is_the_highest_among_the_evidence(client, llm):
    llm.completions.queue = [judge_json(5, relevant=[1, 2]), ANSWER]  # MFC 사례(WARNING) + 근거에 같이 들어간 문서
    llm.embeddings.vector = [0.0, 0.0, 1.0]
    body = post(client, equipment_name="Centura", error_code="ALARM-402", symptom="반사파").json()
    assert body["risk_level"] == "CRITICAL"


def test_response_has_no_risk_when_the_documents_do_not_state_one(client, llm):
    llm.completions.queue = [judge_json(5, relevant=[1]), ANSWER]
    body = post(client, equipment_name="x", error_code="ALARM-777", symptom="냉각 팬이 안 돌아갑니다").json()
    assert body["status"] == "found" and body["risk_level"] is None and body["risk_reason"] is None


def test_not_found_has_no_risk(client, llm):
    llm.completions.queue = [judge_json(1), "REWRITTEN", judge_json(1)]
    body = post(client).json()
    assert body["status"] == "not_found" and body["risk_level"] is None
