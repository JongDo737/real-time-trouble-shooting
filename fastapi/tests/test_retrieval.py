import numpy as np
import pytest

from app.errors import ApiError
from app.services.retrieval import (
    Chunk,
    RagIndex,
    chunk_code_keys,
    chunk_tokens,
    hybrid_search,
    load_index,
    pin_ids,
    rrf,
)
from app.services.textproc import extract_code_keys, normalize_key, query_tokens
from tests.conftest import keyword_vector, sample_chunks


# ---------- 정규화 · 토큰화 ----------


@pytest.mark.parametrize("value", ["e1042", "E 1042", "E-1042", "Ｅ－１０４２", "e_1042", "E–1042"])
def test_normalize_key_unifies_case_space_and_hyphens(value):
    assert normalize_key(value) == "E1042"


def test_normalize_key_keeps_leading_zero_and_letter_o():
    assert normalize_key("E-01042") != normalize_key("E-1042")
    assert normalize_key("E-1O42") != normalize_key("E-1042")


def test_extract_code_keys_finds_codes_and_model_names():
    keys = extract_code_keys("Brooks GF40 shows AL40, ALARM-402 and ERR-MATCH-TUNE at 2 psig")
    assert {"GF40", "AL40", "ALARM402", "ERRMATCHTUNE"} <= set(keys)


def test_chunk_tokens_drop_header_labels_but_keep_codes():
    tokens = chunk_tokens(sample_chunks()[2])  # CENTURA / ALARM-402
    assert "ALARM402" in tokens
    assert "CENTURA" in tokens
    assert "장비명" not in tokens and "에러코드" not in tokens


def test_query_tokens_without_error_code_have_no_code_tokens():
    tokens = query_tokens(equipment_name="Brooks GF40", extra_text="유량이 출렁거립니다")
    assert {"BROOKSGF40", "GF40", "brooks", "유량"} <= set(tokens)
    assert "AL40" not in tokens
    assert query_tokens(equipment_name="Brooks GF40", error_code=None) == query_tokens(equipment_name="Brooks GF40")


def test_query_tokens_contain_equipment_error_and_symptom_words():
    tokens = query_tokens(equipment_name="Brooks GF40", error_code="AL40", extra_text="유량이 출렁거립니다")
    assert {"BROOKSGF40", "GF40", "brooks", "AL40", "유량"} <= set(tokens)


# ---------- RRF ----------


def test_rrf_prefers_items_found_by_both_lists():
    assert rrf([["a", "b", "c"], ["c", "a", "d"]])[:2] == ["a", "c"]


def test_rrf_weights_shift_the_order():
    lists = [["a", "b"], ["b", "a"]]
    assert rrf(lists, weights=[1.0, 1.0])[0] == "a"  # 동점이면 먼저 나온 쪽
    assert rrf(lists, weights=[1.0, 3.0])[0] == "b"


def test_rrf_handles_empty_lists():
    assert rrf([[], []]) == []


# ---------- 개별 검색기 ----------


def test_sparse_search_ranks_the_matching_error_code_first(index):
    tokens = query_tokens(equipment_name="Brooks GF40", error_code="AL40", extra_text="유량")
    assert index.sparse_search(tokens, 5)[0] == "c-mfc-1"


def test_sparse_search_matches_across_code_spellings(index):
    tokens = query_tokens(equipment_name="Centura", error_code="alarm 402")
    assert index.sparse_search(tokens, 3)[0] == "c-rf-1"


def test_sparse_search_returns_nothing_without_overlap(index):
    assert index.sparse_search(["ZZZNOTHING"], 5) == []


def test_dense_search_returns_nearest_first(index):
    assert index.dense_search(keyword_vector("냉각 팬"), 2)[0] == "c-fan-1"
    assert index.dense_search(keyword_vector("플라즈마"), 1) == ["c-rf-1"]


def test_dense_search_rejects_dimension_mismatch(index):
    with pytest.raises(ApiError) as exc:
        index.dense_search([0.1, 0.2], 3)
    assert exc.value.code == "VECTORDB_UNAVAILABLE"


def test_continuations_follow_the_same_section_only(index):
    # c-mfc-1 다음의 c-mfc-2는 섹션 제목이 없는(General) 같은 문서의 뒷부분
    assert [c.id for c in index.continuations("c-mfc-1")] == ["c-mfc-2"]
    # 다음 청크가 자기 섹션을 가지면(다른 섹션의 시작) 이어 붙이지 않는다
    assert index.continuations("c-rf-1") == []
    assert index.continuations("c-fan-1") == []


# ---------- 요청한 오류코드가 적힌 청크 고정 ----------


def test_chunk_code_keys_match_whole_words_and_spellings():
    rf = sample_chunks()[2]
    assert {"ALARM402", "CENTURA"} <= chunk_code_keys(rf)
    remote = Chunk(id="x", text="REMOTE 접속 안내", metadata={})
    assert "EMO" not in chunk_code_keys(remote)  # REMOTE 안의 EMO는 코드가 아니다
    assert "EMO" in chunk_code_keys(Chunk(id="y", text="EMO 버튼을 누르면", metadata={}))


def test_chunk_code_keys_include_metadata_code_but_not_common():
    with_meta = Chunk(id="m", text="조치 단계만 있는 본문", metadata={"error_code": "ALARM-402"})
    common = Chunk(id="c", text="조치 단계만 있는 본문", metadata={"error_code": "COMMON"})
    assert "ALARM402" in chunk_code_keys(with_meta)
    assert "COMMON" not in chunk_code_keys(common)


def test_chunks_with_code_prefers_higher_bm25_and_respects_limit(index):
    tokens = query_tokens(equipment_name="Centura", error_code="ALARM-402", extra_text="반사파")
    assert index.chunks_with_code("ALARM402", tokens) == ["c-rf-1"]
    assert index.chunks_with_code("NOSUCHCODE", tokens) == []
    assert index.chunks_with_code("AL40", tokens, limit=1) == ["c-mfc-1"]


@pytest.mark.parametrize(
    "ids,pinned,top_k,expected",
    [
        (["a", "b", "c"], [], 3, ["a", "b", "c"]),
        (["a", "b", "c"], ["b"], 3, ["a", "b", "c"]),  # 이미 있으면 그대로
        (["a", "b", "c"], ["z"], 3, ["a", "b", "z"]),  # 없으면 맨 뒤를 밀어내고 넣는다
        (["a", "b", "c"], ["y", "z"], 3, ["a", "y", "z"]),
        (["a"], ["z"], 3, ["a", "z"]),  # 자리가 남으면 그냥 추가
        ([], ["z"], 3, ["z"]),
    ],
)
def test_pin_ids(ids, pinned, top_k, expected):
    assert pin_ids(ids, pinned, top_k) == expected


def test_empty_index_returns_nothing():
    empty = RagIndex([], np.empty((0, 3), dtype="float32"))
    assert empty.sparse_search(["A"], 3) == [] and empty.dense_search([0.0, 0.0, 0.0], 3) == []


# ---------- 하이브리드 ----------


def test_hybrid_combines_both_retrievers(index):
    # 증상 문장은 유량(MFC) 쪽을, 오류코드는 AL40 쪽을 가리킨다 → 두 검색기가 같은 청크를 밀어 올린다
    ids = hybrid_search(
        index,
        sparse_tokens=query_tokens(equipment_name="Brooks GF40", error_code="AL40", extra_text="유량"),
        dense_vector=keyword_vector("유량이 출렁거립니다"),
        candidates=4,
        top_k=2,
    )
    assert ids[0] == "c-mfc-1" and "c-mfc-2" in ids


def test_hybrid_without_dense_vector_is_bm25_only(index):
    tokens = query_tokens(equipment_name="Centura", error_code="ALARM-402")
    ids = hybrid_search(index, sparse_tokens=tokens, dense_vector=None, candidates=4, top_k=3)
    assert ids == index.sparse_search(tokens, 4)[:3]


def test_hybrid_dense_rescues_a_chunk_with_no_keyword_match(index):
    # 코드가 틀려서 BM25에는 걸리지 않지만 증상은 의미상 맞는 경우
    ids = hybrid_search(
        index,
        sparse_tokens=query_tokens(equipment_name="Unknown", error_code="XX99"),
        dense_vector=keyword_vector("냉각 팬이 멈춤"),
        candidates=4,
        top_k=2,
    )
    assert ids[0] == "c-fan-1"


# ---------- 파이프라인이 만든 FAISS 폴더 읽기 ----------


def test_load_index_reads_a_langchain_faiss_folder(tmp_path):
    from langchain_community.vectorstores import FAISS
    from langchain_core.documents import Document
    from langchain_core.embeddings import Embeddings

    class FakeEmb(Embeddings):
        def embed_documents(self, texts):
            return [keyword_vector(t) for t in texts]

        def embed_query(self, text):
            return keyword_vector(text)

    chunks = sample_chunks()
    docs = [Document(page_content=c.text, metadata=c.metadata) for c in chunks]
    FAISS.from_documents(docs, FakeEmb()).save_local(str(tmp_path))  # build_faiss.py와 같은 저장 방식

    loaded = load_index(tmp_path)
    assert len(loaded) == len(chunks)
    assert [c.text for c in loaded.chunks] == [c.text for c in chunks]
    assert loaded.chunks[0].metadata["error_code"] == "AL40"
    assert loaded.dim == 3
    assert loaded.dense_search(keyword_vector("플라즈마"), 1) == [loaded.chunks[2].id]
    assert loaded.sparse_search(query_tokens(equipment_name="x", error_code="ALARM-402"), 1) == [loaded.chunks[2].id]


def test_load_index_missing_folder_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_index(tmp_path / "nope")
