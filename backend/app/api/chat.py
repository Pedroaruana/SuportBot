import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.security import rate_limit, require_api_key
from app.services import history
from app.services.rag import ask, generate

router = APIRouter(dependencies=[Depends(require_api_key), rate_limit("chat", "rate_limit_chat_per_min")])

SESSION_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    session_id: str = Field(default="default", pattern=SESSION_PATTERN)


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]
    session_id: str
    fallback: bool


@router.post("/", response_model=ChatResponse, summary="Enviar pergunta ao SupportBot")
def chat(body: ChatRequest):
    result = ask(body.question, body.session_id)
    return ChatResponse(session_id=body.session_id, **result)


def _sse(events: Iterator[dict]) -> Iterator[str]:
    try:
        for event in events:
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    except Exception:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Falha ao gerar a resposta.'})}\n\n"
        raise


@router.post("/stream", summary="Enviar pergunta com resposta em streaming (SSE)")
def chat_stream(body: ChatRequest):
    return StreamingResponse(
        _sse(generate(body.question, body.session_id)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/{session_id}", summary="Limpar histórico de sessão")
def clear_session(session_id: str):
    removed = history.clear_history(session_id)
    return {"status": "cleared", "session_id": session_id, "messages": removed}
