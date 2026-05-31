from fastapi import APIRouter
from pydantic import BaseModel
from langchain.memory import ConversationBufferWindowMemory
from app.services.rag import ask

router = APIRouter()

# Armazena memória por session_id (em produção: Redis ou banco)
_sessions: dict[str, ConversationBufferWindowMemory] = {}


class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]
    session_id: str


def _get_or_create_memory(session_id: str) -> ConversationBufferWindowMemory:
    if session_id not in _sessions:
        _sessions[session_id] = ConversationBufferWindowMemory(
            k=5,                           # Mantém os últimos 5 turnos
            memory_key="chat_history",
            return_messages=True,
            output_key="answer",
        )
    return _sessions[session_id]


@router.post("/", response_model=ChatResponse, summary="Enviar pergunta ao SupportBot")
def chat(body: ChatRequest):
    memory = _get_or_create_memory(body.session_id)
    result = ask(body.question, memory)
    return ChatResponse(
        answer=result["answer"],
        sources=result["sources"],
        session_id=body.session_id,
    )


@router.delete("/{session_id}", summary="Limpar histórico de sessão")
def clear_session(session_id: str):
    if session_id in _sessions:
        del _sessions[session_id]
    return {"status": "cleared", "session_id": session_id}
