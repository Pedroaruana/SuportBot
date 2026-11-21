import json

from app.services import history
from tests.conftest import make_pdf


def _index(client):
    text = "Politica de reembolso. O cliente pode pedir reembolso em ate 7 dias apos a compra."
    client.post("/api/ingest/pdf", files={"file": ("reembolso.pdf", make_pdf(text), "application/pdf")})


def test_answers_with_sources(client, fake_llm):
    _index(client)
    body = client.post("/api/chat/", json={"question": "reembolso em quantos dias", "session_id": "s1"}).json()
    assert body["fallback"] is False
    assert body["answer"] == "Resposta de teste [1]"
    assert body["sources"][0]["source"] == "reembolso.pdf"
    assert body["sources"][0]["id"] == 1
    assert len(fake_llm.calls) == 1


def test_fallback_without_calling_llm(client, fake_llm):
    _index(client)
    body = client.post("/api/chat/", json={"question": "zzzz qqqq xxxx"}).json()
    assert body["fallback"] is True
    assert body["sources"] == []
    assert fake_llm.calls == []


def test_fallback_on_empty_index(client, fake_llm):
    body = client.post("/api/chat/", json={"question": "qualquer coisa"}).json()
    assert body["fallback"] is True


def test_history_is_persisted_and_condensed(client, fake_llm):
    _index(client)
    client.post("/api/chat/", json={"question": "reembolso em quantos dias", "session_id": "h1"})
    client.post("/api/chat/", json={"question": "e depois disso reembolso", "session_id": "h1"})
    # 1a pergunta: so stream. 2a: invoke (condensar) + stream
    assert len(fake_llm.calls) == 3
    assert len(history.get_history("h1")) == 4
    assert client.delete("/api/chat/h1").json()["messages"] == 4
    assert history.get_history("h1") == []


def test_stream_events(client, fake_llm):
    _index(client)
    with client.stream("POST", "/api/chat/stream", json={"question": "reembolso em quantos dias"}) as resp:
        lines = [ln for ln in resp.iter_lines() if ln.startswith("data: ")]
    events = [json.loads(ln[6:]) for ln in lines]
    assert events[0]["type"] == "sources"
    assert [e["text"] for e in events if e["type"] == "token"] == ["Resposta ", "de teste ", "[1]"]
    assert events[-1] == {"type": "done", "fallback": False}


def test_validates_input(client):
    assert client.post("/api/chat/", json={"question": ""}).status_code == 422
    assert client.post("/api/chat/", json={"question": "oi", "session_id": "../x"}).status_code == 422


def test_metrics_endpoint(client, fake_llm):
    _index(client)
    client.post("/api/chat/", json={"question": "reembolso em quantos dias"})
    snap = client.get("/metrics").json()
    assert snap["chat"]["requests"] == 1
    assert snap["requests"] >= 2
