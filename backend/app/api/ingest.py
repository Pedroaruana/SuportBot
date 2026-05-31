from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel, HttpUrl
from app.services.ingestor import ingest_pdf, ingest_url, list_sources

router = APIRouter()


class UrlRequest(BaseModel):
    url: HttpUrl


@router.post("/pdf", summary="Indexar um documento PDF")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Apenas arquivos .pdf são aceitos.")

    content = await file.read()
    result = ingest_pdf(content, file.filename)

    if result["status"] == "error":
        raise HTTPException(status_code=422, detail=result["message"])

    return result


@router.post("/url", summary="Indexar uma página web")
async def index_url(body: UrlRequest):
    result = ingest_url(str(body.url))

    if result["status"] == "error":
        raise HTTPException(status_code=422, detail=result["message"])

    return result


@router.get("/sources", summary="Listar fontes indexadas")
def get_sources():
    return list_sources()
