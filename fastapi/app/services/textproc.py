"""검색용 텍스트 처리: 장비명 · 오류코드 정규화(docs/data-contract.md §9.1)와 BM25 토큰화."""

import re
import unicodedata
from functools import lru_cache

# 공백, 하이픈류(‐ ‑ ‒ – — ― −), 밑줄은 구분자로 보고 제거한다
_SEPARATORS = re.compile(r"[\s\-_‐-―−]+")

# 오류코드 · 모델명처럼 보이는 토큰의 형태: 영문+숫자, 또는 하이픈 · 밑줄로 이어진 영문 단어 (예: E-1042, ERR_TEMP_HIGH, X200)
_CODE_LIKE = re.compile(
    r"[A-Za-z][A-Za-z0-9]*(?:[-_][A-Za-z0-9]+)+|[A-Za-z]{1,6}\d+[A-Za-z0-9]*"
)

# Kiwi 품사 중 검색에 쓸 것: 명사, 동사 · 형용사 어간, 어근, 외래어(영문), 숫자, 한자
_KEEP_TAGS = ("NNG", "NNP", "NR", "VV", "VA", "XR", "SL", "SN", "SH")


def normalize_key(value: str) -> str:
    """e1042 = E 1042 = E-1042 → E1042. 앞자리 0, O/0, l/1은 바꾸지 않는다."""
    return _SEPARATORS.sub("", unicodedata.normalize("NFKC", value)).upper()


def extract_code_keys(text: str) -> list[str]:
    """텍스트 안의 코드 · 모델명 형태 토큰을 정규화 키로 돌려준다."""
    normalized = unicodedata.normalize("NFKC", text)
    return [normalize_key(m) for m in _CODE_LIKE.findall(normalized)]


@lru_cache
def _kiwi():
    from kiwipiepy import Kiwi

    return Kiwi()


def tokenize(text: str) -> list[str]:
    """코드 키(대문자) + 한국어 형태소 · 영단어(소문자) 토큰."""
    normalized = unicodedata.normalize("NFKC", text)
    tokens = extract_code_keys(normalized)
    for token in _kiwi().tokenize(normalized):
        if token.tag.startswith(_KEEP_TAGS):
            tokens.append(token.form.lower() if token.tag == "SL" else token.form)
    return tokens


def query_tokens(*, equipment_name: str, error_code: str | None = None, extra_text: str = "") -> list[str]:
    """BM25 질의 토큰: 장비명 · 오류코드 키 + 단어, 그리고 증상 문장의 토큰. 오류코드가 없으면 코드 토큰은 뺀다."""
    tokens = [normalize_key(equipment_name)]
    tokens += tokenize(equipment_name)
    if error_code:
        tokens.append(normalize_key(error_code))
        tokens += tokenize(error_code)
    if extra_text:
        tokens += tokenize(extra_text)
    return tokens
