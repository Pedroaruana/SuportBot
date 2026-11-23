from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.security import rate_limit, require_api_key
from app.services import analytics, guardrails

router = APIRouter(dependencies=[Depends(require_api_key)])


class FeedbackRequest(BaseModel):
    message_id: int = Field(ge=1)
    rating: Literal["up", "down"]
    comment: str | None = Field(default=None, max_length=500)


@router.post("/feedback", summary="Avaliar uma resposta", dependencies=[rate_limit("feedback", "rate_limit_chat_per_min")])
def send_feedback(body: FeedbackRequest):
    comment = guardrails.redact(body.comment) if body.comment else None
    saved = analytics.set_feedback(body.message_id, 1 if body.rating == "up" else -1, comment)
    if not saved:
        raise HTTPException(status_code=404, detail="Resposta não encontrada.")
    return {"status": "saved", "message_id": body.message_id, "rating": body.rating}


@router.get("/analytics/summary", summary="Resumo de uso e satisfação")
def get_summary():
    return analytics.summary()


@router.get("/analytics/unanswered", summary="Perguntas sem resposta (fallback), mais frequentes primeiro")
def get_unanswered(limit: int = Query(default=50, ge=1, le=200)):
    return analytics.unanswered(limit)


@router.get("/analytics/downvoted", summary="Respostas avaliadas negativamente")
def get_downvoted(limit: int = Query(default=50, ge=1, le=200)):
    return analytics.downvoted(limit)
