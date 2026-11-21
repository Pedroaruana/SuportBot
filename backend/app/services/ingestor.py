import hashlib
import io

import fitz  # PyMuPDF
from bs4 import BeautifulSoup
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings
from app.core.security import UnsafeUrlError, fetch_public_url
from app.services import retrieval
from app.services.store import get_vector_store


def _split_documents(docs: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    return splitter.split_documents(docs)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _index(source: str, docs: list[Document], file_hash: str) -> dict:
    """
    Indexa evitando duplicatas:
    - mesmo hash: ignora (status duplicate)
    - mesma fonte com conteudo novo: substitui os chunks antigos
    """
    store = get_vector_store()
    existing = store._collection.get(where={"source": source}, include=["metadatas"])
    hashes = {m.get("file_hash") for m in existing["metadatas"]}

    if file_hash in hashes:
        return {"status": "duplicate", "source": source, "chunks": len(existing["ids"])}

    if existing["ids"]:
        store._collection.delete(ids=existing["ids"])

    chunks = _split_documents(docs)
    for i, chunk in enumerate(chunks):
        chunk.metadata["file_hash"] = file_hash
        chunk.metadata["chunk_id"] = f"{file_hash[:12]}:{i}"

    store.add_documents(chunks, ids=[c.metadata["chunk_id"] for c in chunks])
    retrieval.invalidate_bm25()
    return {
        "status": "replaced" if existing["ids"] else "success",
        "source": source,
        "chunks": len(chunks),
    }


def ingest_pdf(file_bytes: bytes, filename: str) -> dict:
    """Extrai o texto por pagina e indexa os chunks no ChromaDB."""
    try:
        pdf = fitz.open(stream=io.BytesIO(file_bytes), filetype="pdf")
    except Exception:
        return {"status": "error", "message": "PDF inválido ou corrompido."}

    docs = []
    for page_num, page in enumerate(pdf):
        text = page.get_text()
        if text.strip():
            docs.append(
                Document(
                    page_content=text,
                    metadata={"source": filename, "type": "pdf", "page": page_num + 1},
                )
            )

    if not docs:
        return {"status": "error", "message": "Nenhum texto encontrado no PDF."}

    result = _index(filename, docs, _sha256(file_bytes))
    result["pages"] = len(docs)
    return result


def ingest_url(url: str) -> dict:
    """Baixa a pagina (com protecao SSRF), extrai o texto principal e indexa."""
    try:
        html = fetch_public_url(url)
    except UnsafeUrlError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": f"Falha ao acessar a URL: {e}"}

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    main = soup.find("main") or soup.find("article") or soup.find("body")
    text = main.get_text(separator="\n", strip=True) if main else ""

    if not text.strip():
        return {"status": "error", "message": "Nenhum conteúdo textual encontrado."}

    docs = [Document(page_content=text, metadata={"source": url, "type": "url"})]
    return _index(url, docs, _sha256(text.encode("utf-8")))


def list_sources() -> list[dict]:
    """Lista as fontes indexadas com a contagem de chunks."""
    collection = get_vector_store()._collection.get(include=["metadatas"])
    seen: dict[str, dict] = {}
    for meta in collection["metadatas"]:
        src = meta.get("source", "desconhecido")
        entry = seen.setdefault(src, {"source": src, "type": meta.get("type", "?"), "chunks": 0})
        entry["chunks"] += 1
    return list(seen.values())


def delete_source(source: str) -> int:
    """Remove todos os chunks de uma fonte. Retorna quantos foram removidos."""
    store = get_vector_store()
    existing = store._collection.get(where={"source": source})
    if existing["ids"]:
        store._collection.delete(ids=existing["ids"])
        retrieval.invalidate_bm25()
    return len(existing["ids"])
