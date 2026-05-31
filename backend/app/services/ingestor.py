import io
import requests
from bs4 import BeautifulSoup
import fitz  # PyMuPDF

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain.schema import Document

from app.core.config import settings
from app.services.embeddings import get_embedding_function


def _get_vector_store() -> Chroma:
    return Chroma(
        persist_directory=settings.chroma_persist_dir,
        embedding_function=get_embedding_function(),
        collection_name="supportbot_docs",
    )


def _split_documents(docs: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    return splitter.split_documents(docs)


def ingest_pdf(file_bytes: bytes, filename: str) -> dict:
    """
    Lê um PDF em memória, extrai o texto por página
    e armazena os chunks no ChromaDB.
    """
    pdf = fitz.open(stream=io.BytesIO(file_bytes), filetype="pdf")
    docs = []

    for page_num, page in enumerate(pdf):
        text = page.get_text()
        if text.strip():
            docs.append(
                Document(
                    page_content=text,
                    metadata={
                        "source": filename,
                        "type": "pdf",
                        "page": page_num + 1,
                    },
                )
            )

    if not docs:
        return {"status": "error", "message": "Nenhum texto encontrado no PDF."}

    chunks = _split_documents(docs)
    store = _get_vector_store()
    store.add_documents(chunks)

    return {
        "status": "success",
        "source": filename,
        "pages": len(docs),
        "chunks": len(chunks),
    }


def ingest_url(url: str) -> dict:
    """
    Faz scraping de uma URL, extrai o texto principal
    e armazena os chunks no ChromaDB.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; SupportBot/1.0)"}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        return {"status": "error", "message": f"Falha ao acessar a URL: {e}"}

    soup = BeautifulSoup(response.text, "html.parser")

    # Remove elementos desnecessários
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    # Prioriza o conteúdo principal
    main = soup.find("main") or soup.find("article") or soup.find("body")
    text = main.get_text(separator="\n", strip=True) if main else ""

    if not text.strip():
        return {"status": "error", "message": "Nenhum conteúdo textual encontrado."}

    docs = [Document(page_content=text, metadata={"source": url, "type": "url"})]
    chunks = _split_documents(docs)
    store = _get_vector_store()
    store.add_documents(chunks)

    return {
        "status": "success",
        "source": url,
        "chunks": len(chunks),
    }


def list_sources() -> list[dict]:
    """Lista todas as fontes já indexadas."""
    store = _get_vector_store()
    collection = store._collection.get(include=["metadatas"])
    seen = {}
    for meta in collection["metadatas"]:
        src = meta.get("source", "desconhecido")
        if src not in seen:
            seen[src] = {"source": src, "type": meta.get("type", "?")}
    return list(seen.values())
