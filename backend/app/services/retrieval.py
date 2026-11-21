import re
from dataclasses import dataclass
from threading import Lock

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from app.core.config import settings
from app.services.store import get_vector_store

RRF_K = 60
_TOKEN = re.compile(r"\w+", re.UNICODE)


@dataclass
class Hit:
    doc: Document
    vector_score: float | None  # similaridade cosseno (None se veio so do BM25)


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class _Bm25Index:
    def __init__(self) -> None:
        self._lock = Lock()
        self._bm25: BM25Okapi | None = None
        self._docs: list[Document] = []

    def invalidate(self) -> None:
        with self._lock:
            self._bm25 = None
            self._docs = []

    def search(self, query: str, k: int) -> list[Document]:
        with self._lock:
            if self._bm25 is None:
                data = get_vector_store()._collection.get(include=["documents", "metadatas"])
                self._docs = [
                    Document(page_content=text, metadata=meta or {})
                    for text, meta in zip(data["documents"], data["metadatas"])
                ]
                if not self._docs:
                    return []
                self._bm25 = BM25Okapi([_tokenize(d.page_content) for d in self._docs])

            tokens = _tokenize(query)
            if not tokens:
                return []
            scores = self._bm25.get_scores(tokens)
            ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
            return [self._docs[i] for i in ranked if scores[i] > 0]


_bm25_index = _Bm25Index()


def invalidate_bm25() -> None:
    _bm25_index.invalidate()


def _key(doc: Document) -> str:
    return doc.metadata.get("chunk_id") or str(hash(doc.page_content))


def rrf_fuse(rankings: list[list[Document]], k: int) -> list[Document]:
    """Reciprocal Rank Fusion entre varias listas ordenadas de documentos."""
    scores: dict[str, float] = {}
    docs: dict[str, Document] = {}
    for ranking in rankings:
        for rank, doc in enumerate(ranking):
            key = _key(doc)
            docs[key] = doc
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank + 1)
    ordered = sorted(scores, key=lambda key: scores[key], reverse=True)
    return [docs[key] for key in ordered[:k]]


def retrieve(query: str) -> tuple[list[Hit], float]:
    """
    Busca hibrida: vetorial (cosseno) + BM25, fundidas por RRF.
    Retorna os hits finais e a melhor similaridade vetorial, usada
    para decidir se ha contexto suficiente para responder.
    """
    store = get_vector_store()
    vector_results = store.similarity_search_with_relevance_scores(query, k=settings.fetch_k)
    vector_docs = [doc for doc, _ in vector_results]
    vector_scores = {_key(doc): score for doc, score in vector_results}
    best = max(vector_scores.values(), default=0.0)

    bm25_docs = _bm25_index.search(query, settings.fetch_k)
    fused = rrf_fuse([vector_docs, bm25_docs], settings.retriever_k)

    hits = [Hit(doc=d, vector_score=vector_scores.get(_key(d))) for d in fused]
    return hits, best
