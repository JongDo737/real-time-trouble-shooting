"""번역 용어집: 서버 파일(data/glossary.json)에서 읽어, 번역할 문장에 나온 용어만 골라 준다."""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("app.glossary")

MAX_HINTS = 10  # 한 번의 번역에 프롬프트로 넣을 용어 수 상한 (토큰 · 지연 보호)
_LANG = re.compile(r"^[a-z]{2}$")


@dataclass(frozen=True)
class Entry:
    id: str
    terms: dict[str, list[str]]  # 언어 코드 -> 표기들 (첫 번째가 그 언어의 대표 용어)


@dataclass(frozen=True)
class Glossary:
    entries: list[Entry] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.entries)

    def select(self, text: str, source_lang: str, target_lang: str, limit: int = MAX_HINTS) -> list[tuple[str, str]]:
        """문장에 나온 용어 → [(문장 속 표기, 목표 언어 대표 용어)]. source_lang이 auto면 모든 언어에서 찾는다."""
        hits: list[tuple[str, str]] = []
        for entry in self.entries:
            target_terms = entry.terms.get(target_lang)
            if not target_terms:
                continue
            langs = [source_lang] if source_lang != "auto" else list(entry.terms)
            found = next(
                (alias for lang in langs if lang != target_lang for alias in entry.terms.get(lang, []) if _appears(alias, text)),
                None,
            )
            if found:
                hits.append((found, target_terms[0]))
                if len(hits) >= limit:
                    break
        return hits


def _appears(alias: str, text: str) -> bool:
    if alias.isascii():
        # 영어: 단어 시작이 맞으면 매칭 (flow -> flows, flowing). 대소문자 무시
        return re.search(r"(?<![A-Za-z0-9])" + re.escape(alias), text, re.IGNORECASE) is not None
    return alias in text  # 한국어 등: 조사가 붙어도 매칭


def parse(data: object) -> Glossary:
    """파일 내용(JSON)을 검증해서 Glossary로. 잘못된 항목은 건너뛰고 경고를 남긴다."""
    raw_entries = data.get("entries") if isinstance(data, dict) else data
    if not isinstance(raw_entries, list):
        raise ValueError("entries 목록이 없습니다.")

    entries: list[Entry] = []
    for index, raw in enumerate(raw_entries):
        terms = raw.get("terms") if isinstance(raw, dict) else None
        clean: dict[str, list[str]] = {}
        if isinstance(terms, dict):
            for lang, aliases in terms.items():
                values = [a.strip() for a in aliases if isinstance(a, str) and a.strip()] if isinstance(aliases, list) else []
                if _LANG.match(str(lang)) and values:
                    clean[lang] = values
        if len(clean) < 2:
            log.warning("용어집 항목 %d번을 건너뜁니다 (언어 2개 이상의 용어가 필요)", index + 1)
            continue
        entries.append(Entry(id=str(raw.get("id", index + 1)), terms=clean))
    return Glossary(entries)


EMPTY = Glossary()
_cache: dict[Path, tuple[float, Glossary]] = {}


def get_glossary(path: Path) -> Glossary:
    """파일이 바뀌었으면 다시 읽는다 (요청마다 수정 시각만 확인). 없거나 잘못됐으면 이전 값 또는 빈 용어집."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return EMPTY

    cached = _cache.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        glossary = parse(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        # 편집 중인 깨진 파일 때문에 번역이 멈추지 않게, 이전에 읽은 값을 계속 쓴다
        log.error("용어집 파일을 읽지 못했습니다 (%s): %s", path.name, type(exc).__name__)
        return cached[1] if cached else EMPTY

    _cache[path] = (mtime, glossary)
    log.info("용어집 %d개 항목 로드 (%s)", len(glossary), path.name)
    return glossary
