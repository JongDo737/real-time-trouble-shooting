import numpy as np
import pytest

from app.config import Settings
from app.services.semantic_chunking import (
    chunk_block,
    chunk_meta,
    distances,
    split_units,
    threshold,
    windows,
    with_header,
)

DOC = """# 제목
문서 번호: X-1

---

## [SPEC-01] RF Power Generator
- 에러 코드: `ALARM-402`
- 반사파 5% 미만이 정상이다.

---

## [SPEC-02] MFC 유량
- 에러 코드: `AL40`
""" + "긴 설명 문장입니다. " * 30 + "\n두 번째 줄."


def test_headings_and_rules_are_section_boundaries():
    blocks = split_units(DOC)
    firsts = [b[0] for b in blocks]
    assert "## [SPEC-01] RF Power Generator" in firsts and "## [SPEC-02] MFC 유량" in firsts
    assert all("---" not in unit for b in blocks for unit in b)  # 구분선은 내용이 아니다


def test_long_lines_are_split_into_sentences():
    block = next(b for b in split_units(DOC) if b[0].startswith("## [SPEC-02]"))
    assert len(block) > 5


def test_windows_include_neighbours():
    assert windows(["a", "b", "c"]) == ["a b", "a b c", "b c"]


def test_distances_between_neighbours():
    vectors = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    gaps = distances(vectors)
    assert gaps == pytest.approx([0.0, 1.0])
    assert distances(vectors[:1]) == []


def test_threshold_uses_the_percentile_and_handles_no_distances():
    assert threshold([0.1, 0.2, 0.3, 0.4, 0.5], 80) == pytest.approx(0.42)
    assert threshold([], 90) == float("inf")


def _units(n, size=60):
    return [f"{i}" * size for i in range(n)]


def test_cuts_where_the_topic_changes():
    units = _units(6)
    gaps = [0.01, 0.01, 0.9, 0.01, 0.01]  # 세 번째 단위 뒤에서 주제가 바뀐다
    chunks = chunk_block(units, gaps, cut=0.5, min_chars=100, max_chars=900)
    assert len(chunks) == 2
    assert chunks[0].count("\n") == 2 and chunks[1].count("\n") == 2


def test_does_not_cut_before_the_minimum_length():
    chunks = chunk_block(_units(4, size=20), [0.9, 0.9, 0.9], cut=0.5, min_chars=100, max_chars=900)
    assert len(chunks) == 1  # 80자 남짓이라 주제가 바뀌어도 자르지 않는다


def test_cuts_when_too_long_even_without_a_topic_change():
    chunks = chunk_block(_units(10, size=100), [0.0] * 9, cut=0.5, min_chars=100, max_chars=350)
    assert len(chunks) > 1 and all(len(c) <= 350 for c in chunks)


def test_short_tail_joins_the_previous_chunk():
    units = _units(4, size=80)
    chunks = chunk_block(units, [0.9, 0.0, 0.9], cut=0.5, min_chars=100, max_chars=900)
    assert chunks[-1].count("\n") >= 1  # 마지막 짧은 조각이 따로 남지 않는다


def test_header_and_metadata_follow_the_pipeline_format():
    content, meta = with_header("## [SPEC-01] RF\n에러 코드 ALARM-402, AMAT 장비, WARNING")
    assert content.startswith("[장비명: AMAT | 에러코드: ALARM-402 | 섹션: [SPEC-01] RF | 위험도: WARNING]\n## [SPEC-01] RF")
    assert (meta.error_code, meta.equipment, meta.section, meta.risk_level) == ("ALARM-402", "AMAT", "[SPEC-01] RF", "WARNING")


def test_metadata_defaults_when_nothing_matches():
    meta = chunk_meta("그냥 본문")
    assert (meta.error_code, meta.equipment, meta.section, meta.risk_level) == ("COMMON", "COMMON", "General", "INFO")


def test_chunking_setting_picks_the_index_folder(monkeypatch):
    # 환경변수(FAISS_DIR 등)가 남아 있어도 같은 결과가 나오도록 폴더를 직접 지정한다
    folders = {"faiss_dir": "../rag_pipeline/faiss_db/pdf", "faiss_semantic_dir": "../rag_pipeline/faiss_db/pdf_semantic"}
    fixed = Settings(_env_file=None, chunking="fixed", **folders)
    semantic = Settings(_env_file=None, chunking="semantic", **folders)
    assert fixed.faiss_path.name == "pdf"
    assert semantic.faiss_path.name == "pdf_semantic"
