import hashlib
import math
import os
import re

import pytest

os.environ.setdefault("GEMINI_API_KEY", "test-key")

from fastapi.testclient import TestClient  # noqa: E402
from langchain_core.embeddings import Embeddings  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.observability import metrics  # noqa: E402
from app.core.security import limiter  # noqa: E402
from app.services import embeddings as embeddings_module  # noqa: E402
from app.services import rag, retrieval  # noqa: E402
from app.services.store import reset_store_cache  # noqa: E402

DIM = 256


class FakeEmbeddings(Embeddings):
    """Bag-of-words com hash: textos parecidos ficam próximos, sem rede."""

    def _vec(self, text: str) -> list[float]:
        vec = [0.0] * DIM
        for token in re.findall(r"\w+", text.lower()):
            idx = int(hashlib.md5(token.encode()).hexdigest(), 16) % DIM
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


class FakeChunk:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeLLM:
    def __init__(self) -> None:
        self.calls: list[list] = []

    def stream(self, messages):
        self.calls.append(messages)
        for part in ["Resposta ", "de teste ", "[1]"]:
            yield FakeChunk(part)

    def invoke(self, messages):
        self.calls.append(messages)
        text = str(messages[-1].content)
        return FakeChunk(text.rsplit("Última pergunta:", 1)[-1].strip())


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chroma"))
    monkeypatch.setattr(settings, "sqlite_path", str(tmp_path / "test.db"))
    monkeypatch.setattr(settings, "api_key", "")
    monkeypatch.setattr(settings, "min_relevance", 0.2)
    monkeypatch.setattr(embeddings_module, "get_embedding_function", lambda: FakeEmbeddings())
    reset_store_cache()
    retrieval.invalidate_bm25()
    limiter.reset()
    metrics.reset()
    yield
    reset_store_cache()


@pytest.fixture
def fake_llm(monkeypatch):
    llm = FakeLLM()
    monkeypatch.setattr(rag, "get_llm", lambda: llm)
    return llm


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


def make_pdf(text: str) -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(50, 50, 550, 750), text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data
