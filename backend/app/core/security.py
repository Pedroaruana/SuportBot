import hmac
import ipaddress
import socket
import time
from collections import defaultdict, deque
from threading import Lock
from urllib.parse import urljoin, urlparse

import requests
from fastapi import Depends, Header, HTTPException, Request

from app.core.config import settings

MAX_REDIRECTS = 3
ALLOWED_CONTENT_TYPES = ("text/html", "text/plain", "application/xhtml+xml")
SITEMAP_CONTENT_TYPES = ("application/xml", "text/xml", "text/plain")


class UnsafeUrlError(ValueError):
    pass


def validate_public_url(url: str) -> None:
    """Bloqueia SSRF: so http(s) e so hosts que resolvem para IPs publicos."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise UnsafeUrlError("Apenas URLs http/https são aceitas.")

    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
    except socket.gaierror as e:
        raise UnsafeUrlError("Não foi possível resolver o host.") from e

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise UnsafeUrlError("A URL aponta para um endereço não público.")


def fetch_public_url(url: str, accept: tuple[str, ...] = ALLOWED_CONTENT_TYPES) -> str:
    """
    Baixa o HTML seguindo redirects manualmente (cada salto e revalidado),
    com timeout e limite de tamanho.
    Limitacao conhecida: ha uma janela de DNS rebinding entre a validacao
    e a conexao. Em producao, usar um proxy de egress.
    """
    max_bytes = settings.max_url_kb * 1024
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SupportBot/1.0)"}
    current = url

    for _ in range(MAX_REDIRECTS + 1):
        validate_public_url(current)
        with requests.get(
            current, headers=headers, timeout=15, allow_redirects=False, stream=True
        ) as resp:
            if resp.is_redirect:
                location = resp.headers.get("Location")
                if not location:
                    raise UnsafeUrlError("Redirect sem destino.")
                current = urljoin(current, location)
                continue

            resp.raise_for_status()
            ctype = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if ctype not in accept:
                raise UnsafeUrlError(f"Tipo de conteúdo não suportado: {ctype or 'desconhecido'}.")

            data = bytearray()
            for chunk in resp.iter_content(chunk_size=16384):
                data.extend(chunk)
                if len(data) > max_bytes:
                    raise UnsafeUrlError("Página maior que o limite permitido.")
            encoding = resp.encoding or "utf-8"
            return data.decode(encoding, errors="replace")

    raise UnsafeUrlError("Redirects demais.")


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not settings.api_key:
        return
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="API key inválida ou ausente.")


class _SlidingWindow:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, window: float = 60.0) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > window:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = _SlidingWindow()


def rate_limit(bucket: str, limit_attr: str):
    """Dependency factory. O limite e lido das settings a cada request."""

    def dependency(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        limit = getattr(settings, limit_attr)
        if not limiter.allow(f"{bucket}:{client}", limit):
            raise HTTPException(status_code=429, detail="Muitas requisições. Tente novamente em instantes.")

    return Depends(dependency)
