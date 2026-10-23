from tests.conftest import RAG_BODY


def test_health_reports_degraded_without_key_and_index(client):
    res = client.get("/health")
    # 테스트 환경에는 OpenAI 키도 인덱스도 없으므로 503 + degraded
    assert res.status_code == 503
    body = res.json()
    assert body["status"] == "degraded"
    assert body["llm_ready"] is False
    assert set(body) == {"status", "llm_ready", "index_loaded", "chunks"}


def test_health_reports_loaded_index(client, index):
    from app.main import app

    app.state.rag_index = index
    body = client.get("/health").json()
    assert body["index_loaded"] is True
    assert body["chunks"] == len(index)


def test_request_id_is_echoed_in_header_and_error_body(client):
    res = client.post("/rag-query", json={**RAG_BODY, "equipment_name": ""}, headers={"X-Request-ID": "req-123"})
    assert res.status_code == 422
    assert res.headers["X-Request-ID"] == "req-123"
    assert res.json()["error"]["request_id"] == "req-123"


def test_endpoints_need_no_token(client):
    assert client.post("/rag-query", json=RAG_BODY).status_code == 200
