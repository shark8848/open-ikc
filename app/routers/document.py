from fastapi import APIRouter

from app.services.document import DocumentService

router = APIRouter(prefix="/api/v1/knowledge-documents", tags=["文档"])


@router.post("/ingest")
async def ingest_document() -> dict:
    return DocumentService.ingest()


@router.post("/ingest-and-parse")
async def ingest_and_parse_document() -> dict:
    return DocumentService.ingest_and_parse()


@router.get("/{doc_id}")
async def get_document(doc_id: str) -> dict:
    return DocumentService.get_document(doc_id)
