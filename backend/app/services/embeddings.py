import time

import google.generativeai as genai
from langchain_core.embeddings import Embeddings

from app.core.config import settings

BATCH_SIZE = 50
MAX_RETRIES = 3


class GeminiEmbeddings(Embeddings):
    """Embeddings via REST do Gemini, em lotes e com retry simples."""

    def __init__(self) -> None:
        genai.configure(api_key=settings.gemini_api_key)

    def _embed(self, content: str | list[str], task_type: str):
        for attempt in range(MAX_RETRIES):
            try:
                return genai.embed_content(
                    model=settings.embedding_model,
                    content=content,
                    task_type=task_type,
                )["embedding"]
            except Exception:
                if attempt == MAX_RETRIES - 1:
                    raise
                time.sleep(2**attempt)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            vectors.extend(self._embed(batch, "retrieval_document"))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text, "retrieval_query")


def get_embedding_function() -> Embeddings:
    return GeminiEmbeddings()
