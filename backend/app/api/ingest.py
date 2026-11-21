from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, HttpUrl

from app.core.config import settings
from app.core.security import rate_limit, require_api_key
from app.services.ingestor import delete_source, ingest_pdf, ingest_url, list_sources

router = APIRouter(dependencies=[Depends(require_api_key)])
ingest_limit = rate_limit("ingest", "rate_limit_ingest_per_min")


class UrlRequest(BaseModel):
    url: HttpUrl


@router.post("/pdf", summary="Indexar um documento PDF", dependencies=[ingest_limit])
async def upload_pdf(file: UploadFile = File(...)):
    max_bytes = settings.max_upload_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)

    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Arquivo maior que {settings.max_upload_mb} MB.")
    if not content.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF válidos são aceitos.")

    result = ingest_pdf(content, file.filename or "documento.pdf")
    if result["status"] == "error":
        raise HTTPException(status_code=422, detail=result["message"])
    return result


@router.post("/url", summary="Indexar uma página web", dependencies=[ingest_limit])
def index_url(body: UrlRequest):
    result = ingest_url(str(body.url))
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
