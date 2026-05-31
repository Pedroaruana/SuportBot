import google.generativeai as genai
from langchain.embeddings.base import Embeddings
from app.core.config import settings


class GeminiEmbeddings(Embeddings):
    """Embedding direto via REST HTTP — sem gRPC, sem timeout."""

    def __init__(self):
        genai.configure(api_key=settings.gemini_api_key)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        result = []
        for text in texts:
            r = genai.embed_content(
                model=settings.embedding_model,
                content=text,
                task_type="retrieval_document",
            )
            result.append(r["embedding"])
        return result

    def embed_query(self, text: str) -> list[float]:
        r = genai.embed_content(
            model=settings.embedding_model,
            content=text,
            task_type="retrieval_query",
        )
        return r["embedding"]


def get_embedding_function() -> GeminiEmbeddings:
    return GeminiEmbeddings()