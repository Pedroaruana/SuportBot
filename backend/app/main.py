import time
import uuid

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import analytics, chat, ingest
from app.core.config import settings
from app.core.observability import log, metrics, setup_logging
from app.core.security import require_api_key

setup_logging()

app = FastAPI(
    title="SupportBot API",
    description="Chatbot de suporte com RAG híbrido (vetorial + BM25) usando Gemini e ChromaDB",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def access_log(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        ms = (time.perf_counter() - start) * 1000
        metrics.record_request(status, ms)
        log("request", request_id=request_id, method=request.method, path=request.url.path, status=status, ms=round(ms, 1))


app.include_router(ingest.router, prefix="/api/ingest", tags=["Ingestão"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(analytics.router, prefix="/api", tags=["Feedback e analytics"])


@app.get("/health", tags=["Ops"])
def health():
    return {"status": "ok", "service": "SupportBot API", "version": app.version}


@app.get("/metrics", tags=["Ops"], dependencies=[Depends(require_api_key)])
def get_metrics():
    return metrics.snapshot()
