"""문서의 위험도 줄을 읽는다.

데이터(매뉴얼)의 항목마다 `- 위험도: CRITICAL (이유)` 줄이 있다.
  INFO     = 절차 · 참조
  WARNING  = 공정 중단이나 수율 · 부품 손상
  CRITICAL = 인명 위험 또는 즉시 파손

파이프라인이 청크 헤더에 넣는 `위험도: X`는 청크 안에서 CRITICAL / WARNING / INFO 단어를 처음 찾은 것이고,
못 찾으면 INFO로 채운다. 항목이 500자 단위로 잘리면 뒷부분 청크는 모두 INFO가 되어 믿을 수 없으므로,
여기서는 헤더가 아니라 **본문의 위험도 줄**을 직접 읽는다.
"""

import re
from dataclasses import dataclass

LEVELS = ("INFO", "WARNING", "CRITICAL")  # 낮은 순

# 줄 맨 앞(들여쓰기와 `-`/`*` 목록 표시만 허용)의 `위험도: LEVEL (이유)`. 청크 헤더(`[장비명: … | 위험도: INFO]`)는 `[`로 시작해 걸리지 않는다.
_RISK_LINE = re.compile(
    r"^[ \t]*(?:[-*][ \t]*)?위험도:[ \t]*(CRITICAL|WARNING|INFO)\b[ \t]*(?:\(([^)\n]*)\))?",
    re.MULTILINE | re.IGNORECASE,
)


@dataclass(frozen=True)
class Risk:
    level: str  # INFO | WARNING | CRITICAL
    reason: str | None = None


def parse_risk(text: str) -> Risk | None:
    """본문에서 위험도 줄을 찾는다. 없으면 None (위험도가 적히지 않은 문서)."""
    match = _RISK_LINE.search(text or "")
    if not match:
        return None
    reason = (match.group(2) or "").strip() or None
    return Risk(level=match.group(1).upper(), reason=reason)


def highest(risks) -> Risk | None:
    """여러 근거 중 가장 높은 위험도. 같은 등급이면 먼저 나온 것을 쓴다."""
    best: Risk | None = None
    for risk in risks:
        if risk is not None and (best is None or LEVELS.index(risk.level) > LEVELS.index(best.level)):
            best = risk
    return best
