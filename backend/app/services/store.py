import os
from functools import lru_cache

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

from langchain_chroma import Chroma  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.services import embeddings  # noqa: E402

# v2: colecao com metrica cosseno (necessaria para o corte por relevancia)
COLLECTION_NAME = "supportbot_docs_v2"


@lru_cache(maxsize=1)
def get_vector_store() -> Chroma:
    return Chroma(
        persist_directory=settings.chroma_persist_dir,
        embedding_function=embeddings.get_embedding_function(),
        collection_name=COLLECTION_NAME,
        collection_metadata={"hnsw:space": "cosine"},
    )


def reset_store_cache() -> None:
    get_vector_store.cache_clear()
