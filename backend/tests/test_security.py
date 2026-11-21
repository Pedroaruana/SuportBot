import socket

import pytest

from app.core import security
from app.core.security import UnsafeUrlError, validate_public_url


def _resolve_to(ip: str):
    return lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.5", "192.168.1.10", "169.254.169.254", "172.16.0.1"])
def test_blocks_private_addresses(monkeypatch, ip):
    monkeypatch.setattr(security.socket, "getaddrinfo", _resolve_to(ip))
    with pytest.raises(UnsafeUrlError):
        validate_public_url("http://exemplo.com/")


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://exemplo.com", "gopher://x"])
def test_blocks_non_http_schemes(url):
    with pytest.raises(UnsafeUrlError):
        validate_public_url(url)


def test_allows_public_address(monkeypatch):
    monkeypatch.setattr(security.socket, "getaddrinfo", _resolve_to("93.184.216.34"))
    validate_public_url("https://exemplo.com/")


def test_url_endpoint_rejects_localhost(client):
    resp = client.post("/api/ingest/url", json={"url": "http://127.0.0.1:8000/health"})
    assert resp.status_code == 422


def test_api_key_required_when_configured(client, monkeypatch):
    monkeypatch.setattr(security.settings, "api_key", "segredo")
    assert client.get("/api/ingest/sources").status_code == 401
    assert client.get("/api/ingest/sources", headers={"X-API-Key": "errada"}).status_code == 401
    assert client.get("/api/ingest/sources", headers={"X-API-Key": "segredo"}).status_code == 200


def test_rate_limit(client, monkeypatch, fake_llm):
    monkeypatch.setattr(security.settings, "rate_limit_chat_per_min", 2)
    for _ in range(2):
        assert client.post("/api/chat/", json={"question": "oi"}).status_code == 200
    assert client.post("/api/chat/", json={"question": "oi"}).status_code == 429
