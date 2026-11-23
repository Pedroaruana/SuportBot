from app.core.config import settings
from tests.conftest import make_pdf

PDF_TEXT = "Politica de reembolso. O cliente pode pedir reembolso em ate 7 dias apos a compra."


def _upload(client, data: bytes, name="reembolso.pdf"):
    return client.post("/api/ingest/pdf", files={"file": (name, data, "application/pdf")})


def test_pdf_ingest_and_list(client):
    resp = _upload(client, make_pdf(PDF_TEXT))
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"

    sources = client.get("/api/ingest/sources").json()
    assert len(sources) == 1
    assert sources[0]["source"] == "reembolso.pdf"
    assert sources[0]["type"] == "pdf"


def test_duplicate_pdf_is_skipped(client):
    data = make_pdf(PDF_TEXT)
    _upload(client, data)
    again = _upload(client, data).json()
    assert again["status"] == "duplicate"
    assert len(client.get("/api/ingest/sources").json()) == 1


def test_changed_pdf_replaces_old_chunks(client):
    _upload(client, make_pdf(PDF_TEXT))
    resp = _upload(client, make_pdf("Texto totalmente novo sobre planos e precos.")).json()
    assert resp["status"] == "replaced"
    assert client.get("/api/ingest/sources").json()[0]["chunks"] == resp["chunks"]


def test_rejects_non_pdf_content(client):
    resp = _upload(client, b"isto nao e um pdf", name="falso.pdf")
    assert resp.status_code == 422


def test_rejects_oversized_upload(client, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 0)
    resp = _upload(client, make_pdf(PDF_TEXT))
    assert resp.status_code == 413


def test_delete_source(client):
    _upload(client, make_pdf(PDF_TEXT))
    assert client.delete("/api/ingest/sources", params={"source": "reembolso.pdf"}).status_code == 200
    assert client.get("/api/ingest/sources").json() == []
    assert client.delete("/api/ingest/sources", params={"source": "reembolso.pdf"}).status_code == 404
