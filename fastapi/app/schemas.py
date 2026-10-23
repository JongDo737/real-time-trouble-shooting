"""요청·응답 스키마 (docs/api2.md 기준)."""

from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, StringConstraints, field_validator, model_validator


def _normalize_lang(value):
    # 패턴 검사 전에 공백 제거 · 소문자 변환 (대소문자 차이 허용)
    return value.strip().lower() if isinstance(value, str) else value


Id = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
LangCode = Annotated[str, BeforeValidator(_normalize_lang), StringConstraints(pattern=r"^[a-z]{2}$")]
SourceLangCode = Annotated[
    str, BeforeValidator(_normalize_lang), StringConstraints(pattern=r"^([a-z]{2}|auto)$")
]
def _normalize_speaker(value):
    # USER / ADMIN만 허용한다 (대소문자는 구분하지 않음). 이전 값(branch, agent)은 422.
    return value.strip().upper() if isinstance(value, str) else value


Speaker = Annotated[Literal["USER", "ADMIN"], BeforeValidator(_normalize_speaker)]


class Usage(BaseModel):
    in_tok: int = 0
    out_tok: int = 0


# ---------- /translate ----------


class ContextTurn(BaseModel):
    speaker: Speaker
    text: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class TranslateRequest(BaseModel):
    session_id: Id
    utterance_id: Id
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    source_lang: SourceLangCode = "auto"
    target_lang: LangCode
    speaker: Speaker | None = None
    equipment_name: Annotated[str, StringConstraints(max_length=100)] | None = None
    error_code: Annotated[str, StringConstraints(max_length=50)] | None = None
    context: Annotated[list[ContextTurn], Field(max_length=5)] | None = None


class TranslateResponse(BaseModel):
    session_id: str
    utterance_id: str
    translated_text: str
    source_lang: str
    target_lang: str
    latency_ms: int = 0
    usage: Usage = Usage()


# ---------- /rag-query ----------


# 오류코드를 모를 때 호출하는 쪽이 임시로 넣던 값들: 실제 코드가 아니라 "없음"으로 본다.
# (문서에 있는 NO-ALARM-IGNITION-FAIL 같은 의사 코드는 실제 코드이므로 여기에 넣지 않는다)
MISSING_ERROR_CODES = {"", "NO-ALARM", "N/A", "NONE", "UNKNOWN", "-"}
NEEDS_CODE_OR_SYMPTOM = "error_code 또는 symptom 중 하나는 필요합니다."


class RagRequest(BaseModel):
    session_id: Id
    request_id: Id
    equipment_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    error_code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)] | None = None
    symptom: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None

    @field_validator("error_code", mode="before")
    @classmethod
    def _placeholder_means_missing(cls, value):
        if isinstance(value, str) and value.strip().upper() in MISSING_ERROR_CODES:
            return None
        return value

    @model_validator(mode="after")
    def _needs_code_or_symptom(self):
        # 장비명만으로는 검색할 단서가 없다
        if not self.error_code and not self.symptom:
            raise ValueError(NEEDS_CODE_OR_SYMPTOM)
        return self


class Source(BaseModel):
    doc: str
    # 파이프라인 메타데이터에 page가 아직 없어 선택 필드로 둔다 (data-contract.md §4)
    page: int | None = None
    section: str | None = None


class RagResponse(BaseModel):
    session_id: str
    request_id: str
    status: Literal["found", "not_found"]
    answer: str | None = None
    message: str | None = None
    reason: Literal["no_hits", "low_score", "deadline"] | None = None
    sources: list[Source] = []
    score: float | None = None
    attempts: int = 0
    needs_review: bool = False
    exact_match: bool | None = None  # found일 때: 같은 장비·오류코드 사례(true) / 관련 사례만(false)
    handoff: bool = False
    latency_ms: int = 0
    usage: Usage = Usage()


# ---------- 공통 ----------


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    llm_ready: bool
    index_loaded: bool
    chunks: int = 0
