from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field, HttpUrl

from app.core.config import settings
from app.core.security import rate_limit, require_api_key
from app.services.ingestor import delete_source, file_kind, ingest_file, ingest_sitemap, ingest_url, list_sources

router = APIRouter(dependencies=[Depends(require_api_key)])
ingest_limit = rate_limit("ingest", "rate_limit_ingest_per_min")


class UrlRequest(BaseModel):
    url: HttpUrl


class SitemapRequest(BaseModel):
    url: HttpUrl
    limit: int | None = Field(default=None, ge=1, le=100)


async def _upload(file: UploadFile):
    filename = file.filename or "documento"
    if file_kind(filename) is None:
        raise HTTPException(status_code=400, detail="Formato não suportado. Use PDF, DOCX, MD ou TXT.")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Arquivo maior que {settings.max_upload_mb} MB.")

    result = ingest_file(content, filename)
    if result["status"] == "error":
        raise HTTPException(status_code=422, detail=result["message"])
    return result


@router.post("/file", summary="Indexar PDF, DOCX, MD ou TXT", dependencies=[ingest_limit])
async def upload_file(file: UploadFile = File(...)):
    return await _upload(file)


@router.post("/pdf", summary="Indexar um documento (alias de /file)", dependencies=[ingest_limit], include_in_schema=False)
async def upload_pdf(file: UploadFile = File(...)):
    return await _upload(file)


@router.post("/url", summary="Indexar uma página web", dependencies=[ingest_limit])
def index_url(body: UrlRequest):
    result = ingest_url(str(body.url))
    if result["status"] == "error":
        raise HTTPException(status_code=422, detail=result["message"])
    return result


@router.post("/sitemap", summary="Indexar as páginas de um sitemap", dependencies=[ingest_limit])
def index_sitemap(body: SitemapRequest):
    result = ingest_sitemap(str(body.url), body.limit)
    if result["status"] == "error":
        raise HTTPException(status_code=422, detail=result["message"])
    return result


@router.get("/sources", summary="Listar fontes indexadas")
def get_sources():
    return list_sources()


@router.delete("/sources", summary="Remover uma fonte indexada")
def remove_source(source: str):
    removed = delete_source(source)
    if removed == 0:
        raise HTTPException(status_code=404, detail="Fonte não encontrada.")
    return {"status": "deleted", "source": source, "chunks": removed}
