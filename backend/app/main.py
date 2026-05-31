from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import ingest, chat

app = FastAPI(
    title="SupportBot API",
    description="RAG-powered support chatbot using Gemini + ChromaDB",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router, prefix="/api/ingest", tags=["Ingestão"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])


@app.get("/health")
def health():
    return {"status": "ok", "service": "SupportBot API"}
