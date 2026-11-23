import hashlib
import io
from pathlib import PurePath
from urllib.parse import urlparse

import fitz  # PyMuPDF
from bs4 import BeautifulSoup
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from docx import Document as DocxDocument
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings
from app.core.security import SITEMAP_CONTENT_TYPES, UnsafeUrlError, fetch_public_url
from app.services import guardrails, retrieval
from app.services.store import get_vector_store

# extensao -> tipo guardado na metadata
SUPPORTED_EXTENSIONS = {".pdf": "pdf", ".docx": "docx", ".md": "md", ".markdown": "md", ".txt": "txt"}
MAX_CHILD_SITEMAPS = 3


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
    Indexa evitando duplicatas e aplicando os guardrails:
    - mesmo hash: ignora (status duplicate)
    - mesma fonte com conteudo novo: substitui os chunks antigos
    - PII mascarada antes do chunking; trechos com prompt injection tratados depois
    """
    store = get_vector_store()
    existing = store._collection.get(where={"source": source}, include=["metadatas"])
    hashes = {m.get("file_hash") for m in existing["metadatas"]}

    if file_hash in hashes:
        return {"status": "duplicate", "source": source, "chunks": len(existing["ids"])}

    try:
        docs, pii = guardrails.mask_documents(docs)
        chunks, flagged = guardrails.filter_chunks(_split_documents(docs))
    except guardrails.GuardrailError as e:
        return {"status": "error", "message": str(e)}

    if existing["ids"]:
        store._collection.delete(ids=existing["ids"])

    for i, chunk in enumerate(chunks):
        chunk.metadata["file_hash"] = file_hash
        chunk.metadata["chunk_id"] = f"{file_hash[:12]}:{i}"

    store.add_documents(chunks, ids=[c.metadata["chunk_id"] for c in chunks])
    retrieval.invalidate_bm25()

    result: dict = {
        "status": "replaced" if existing["ids"] else "success",
        "source": source,
        "chunks": len(chunks),
    }
    guard: dict = {}
    if pii:
        guard["pii_masked"] = pii
    if flagged:
        guard["injection"] = {"mode": settings.injection_mode, "chunks": flagged}
    if guard:
        result["guardrails"] = guard
    return result


# ---------- Arquivos ----------


def _read_pdf(data: bytes, filename: str) -> list[Document]:
    pdf = fitz.open(stream=io.BytesIO(data), filetype="pdf")
    return [
        Document(page_content=page.get_text(), metadata={"source": filename, "type": "pdf", "page": n + 1})
        for n, page in enumerate(pdf)
        if page.get_text().strip()
    ]


def _read_docx(data: bytes, filename: str) -> list[Document]:
    doc = DocxDocument(io.BytesIO(data))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    text = "\n".join(parts)
    return [Document(page_content=text, metadata={"source": filename, "type": "docx"})] if text.strip() else []


def _read_text(data: bytes, filename: str, kind: str) -> list[Document]:
    if b"\x00" in data[:1024]:
        raise ValueError("Arquivo binário não é texto.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    return [Document(page_content=text, metadata={"source": filename, "type": kind})] if text.strip() else []


def file_kind(filename: str) -> str | None:
    return SUPPORTED_EXTENSIONS.get(PurePath(filename).suffix.lower())


def ingest_file(data: bytes, filename: str) -> dict:
    """Extrai o texto (PDF, DOCX, MD ou TXT) e indexa os chunks no ChromaDB."""
    kind = file_kind(filename)
    if kind is None:
        return {"status": "error", "message": "Formato não suportado. Use PDF, DOCX, MD ou TXT."}

    if kind == "pdf" and not data.startswith(b"%PDF"):
        return {"status": "error", "message": "PDF inválido ou corrompido."}
    if kind == "docx" and not data.startswith(b"PK"):
        return {"status": "error", "message": "DOCX inválido ou corrompido."}

    try:
        if kind == "pdf":
            docs = _read_pdf(data, filename)
        elif kind == "docx":
            docs = _read_docx(data, filename)
        else:
            docs = _read_text(data, filename, kind)
    except Exception:
        return {"status": "error", "message": f"Não foi possível ler o arquivo {kind.upper()}."}

    if not docs:
        return {"status": "error", "message": "Nenhum texto encontrado no arquivo."}

    result = _index(filename, docs, _sha256(data))
    if kind == "pdf" and result["status"] != "error":
        result["pages"] = len(docs)
    return result


def ingest_pdf(file_bytes: bytes, filename: str) -> dict:
    return ingest_file(file_bytes, filename)


# ---------- Web ----------


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


def _sitemap_locs(xml_text: str) -> tuple[bool, list[str]]:
    """Retorna (e_indice, urls) de um sitemap, sem depender do namespace."""
    try:
        root = ElementTree.fromstring(xml_text.encode("utf-8"))
    except (ElementTree.ParseError, DefusedXmlException) as e:
        raise ValueError("Sitemap inválido.") from e

    is_index = root.tag.lower().endswith("sitemapindex")
    locs = [el.text.strip() for el in root.iter() if el.tag.lower().endswith("loc") and el.text and el.text.strip()]
    return is_index, locs


def ingest_sitemap(sitemap_url: str, limit: int | None = None) -> dict:
    """Le um sitemap (ou indice de sitemaps) e indexa as paginas do mesmo dominio."""
    cap = min(limit or settings.max_sitemap_urls, settings.max_sitemap_urls)
    host = urlparse(sitemap_url).hostname

    try:
        is_index, locs = _sitemap_locs(fetch_public_url(sitemap_url, accept=SITEMAP_CONTENT_TYPES))
        if is_index:
            pages: list[str] = []
            for child in locs[:MAX_CHILD_SITEMAPS]:
                if urlparse(child).hostname != host:
                    continue
                _, child_locs = _sitemap_locs(fetch_public_url(child, accept=SITEMAP_CONTENT_TYPES))
                pages.extend(child_locs)
        else:
            pages = locs
    except (UnsafeUrlError, ValueError) as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": f"Falha ao ler o sitemap: {e}"}

    urls = list(dict.fromkeys(u for u in pages if urlparse(u).hostname == host))[:cap]
    if not urls:
        return {"status": "error", "message": "Nenhuma URL do mesmo domínio encontrada no sitemap."}

    indexed = duplicates = chunks = 0
    failed: list[dict] = []
    for url in urls:
        result = ingest_url(url)
        if result["status"] == "error":
            failed.append({"url": url, "message": result["message"]})
        elif result["status"] == "duplicate":
            duplicates += 1
        else:
            indexed += 1
            chunks += result["chunks"]

    return {
        "status": "success" if (indexed or duplicates) else "error",
        "message": None if (indexed or duplicates) else "Nenhuma página pôde ser indexada.",
        "source": sitemap_url,
        "pages": indexed,
        "duplicates": duplicates,
        "chunks": chunks,
        "failed": failed,
    }


# ---------- Consulta ----------


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
