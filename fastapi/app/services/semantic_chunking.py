"""Semantic 청킹: 글자 수가 아니라 문장 사이의 의미가 크게 바뀌는 곳에서 청크를 나눈다.

SKALA RAG Pipeline 자료(p.38, p.106)의 방식이다. 인접한 문장 묶음의 임베딩 거리를 재고,
거리가 큰 곳(전체 거리 분포의 상위 N%)을 주제가 바뀌는 경계로 본다.

- 문서 구조(`## ` 제목, `---` 구분선)는 의미 계산 전에 먼저 경계로 쓴다. 청크 헤더의 섹션 · 장비명 ·
  에러코드를 청크에서 읽어 내는데, 서로 다른 섹션이 한 청크에 섞이면 그 값이 틀어지기 때문이다.
- 이 모듈의 함수는 임베딩을 직접 부르지 않는다 (벡터는 밖에서 받는다). 그래서 API 키 없이 테스트할 수 있다.
"""

import re
from dataclasses import dataclass

import numpy as np

_HEADING = re.compile(r"^#{1,6}\s")
_RULE = re.compile(r"^-{3,}\s*$")
_SENTENCE_END = re.compile(r"(?<=[.!?。])\s+")
_LONG_LINE = 200  # 이보다 긴 줄은 문장 단위로 더 쪼갠다


def split_units(text: str) -> list[list[str]]:
    """문서를 섹션 블록으로 나누고, 블록마다 문장 단위(줄 · 문장) 목록을 돌려준다.

    `## ` 제목은 새 블록의 첫 단위가 되고, `---` 줄은 경계 표시일 뿐이라 내용에 넣지 않는다.
    """
    blocks: list[list[str]] = []
    current: list[str] = []

    def close() -> None:
        nonlocal current
        if current:
            blocks.append(current)
        current = []

    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if _RULE.match(stripped):
            close()
            continue
        if _HEADING.match(stripped):
            close()
        if len(stripped) > _LONG_LINE:
            current.extend(part.strip() for part in _SENTENCE_END.split(stripped) if part.strip())
        else:
            current.append(line)
    close()
    return blocks


def windows(units: list[str], buffer: int = 1) -> list[str]:
    """각 단위를 앞뒤 `buffer`개와 합친 문장 묶음. 한 줄만으로는 의미가 흔들려서 이웃을 함께 임베딩한다."""
    return [" ".join(u.strip() for u in units[max(0, i - buffer) : i + buffer + 1]) for i in range(len(units))]


def distances(vectors: np.ndarray) -> list[float]:
    """인접한 벡터 사이의 코사인 거리 (0에 가까울수록 같은 내용). 벡터가 n개면 n-1개."""
    if len(vectors) < 2:
        return []
    unit = vectors / np.clip(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12, None)
    return [float(1 - unit[i] @ unit[i + 1]) for i in range(len(unit) - 1)]


def threshold(all_distances: list[float], percentile: float) -> float:
    """경계로 볼 거리의 기준. 모든 거리 중 상위 (100 - percentile)%가 경계가 된다."""
    return float(np.percentile(all_distances, percentile)) if all_distances else float("inf")


def chunk_block(
    units: list[str], gaps: list[float], cut: float, *, min_chars: int, max_chars: int
) -> list[str]:
    """한 섹션 블록을 청크로 자른다. gaps[i]는 units[i]와 units[i+1] 사이의 거리다."""
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for i, unit in enumerate(units):
        current.append(unit)
        length += len(unit) + 1
        if i == len(units) - 1:
            break
        topic_changed = gaps[i] > cut and length >= min_chars
        too_long = length + len(units[i + 1]) + 1 > max_chars
        if topic_changed or too_long:
            chunks.append("\n".join(current))
            current, length = [], 0
    if current:
        tail = "\n".join(current)
        # 끝에 남은 아주 짧은 조각은 앞 청크에 붙인다 (너무 길어지지 않을 때만)
        if chunks and len(tail) < min_chars and len(chunks[-1]) + len(tail) + 1 <= max_chars:
            chunks[-1] += "\n" + tail
        else:
            chunks.append(tail)
    return chunks


@dataclass
class ChunkMeta:
    error_code: str
    equipment: str
    section: str
    risk_level: str


# rag_pipeline/build_faiss.py와 같은 규칙이다. 청크 형식(헤더 · 메타데이터)이 달라지면 검색이 달라지므로
# 청킹 방식만 바꾸는 비교가 되도록 일부러 똑같이 둔다. 그쪽을 고치면 여기도 같이 고쳐야 한다.
_ERR = re.compile(r"(ALARM-[A-Z0-9]+|AL\d+|ERR-[A-Z0-9]+)")
_EQ = re.compile(r"(Centura|Endura|Producer|Echoview|TEL|KLA|AMAT|LAM)", re.IGNORECASE)
_SEC = re.compile(r"^##\s+(.+)$", re.MULTILINE)
_RISK = re.compile(r"\b(CRITICAL|WARNING|INFO)\b", re.IGNORECASE)


def chunk_meta(chunk: str) -> ChunkMeta:
    err, eq, sec, risk = _ERR.search(chunk), _EQ.search(chunk), _SEC.search(chunk), _RISK.search(chunk)
    return ChunkMeta(
        error_code=err.group(1) if err else "COMMON",
        equipment=eq.group(1).upper() if eq else "COMMON",
        section=sec.group(1).strip() if sec else "General",
        risk_level=risk.group(1).upper() if risk else "INFO",
    )


def with_header(chunk: str) -> tuple[str, ChunkMeta]:
    """청크 맨 앞에 `[장비명 | 에러코드 | 섹션 | 위험도]` 헤더를 붙인다 (임베딩과 BM25가 이 헤더를 함께 본다)."""
    meta = chunk_meta(chunk)
    header = (
        f"[장비명: {meta.equipment} | 에러코드: {meta.error_code} | 섹션: {meta.section} | 위험도: {meta.risk_level}]\n"
    )
    return header + chunk, meta
