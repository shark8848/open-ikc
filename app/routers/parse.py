from fastapi import APIRouter, Query

from app.services.parse import ParseService

router = APIRouter(prefix="/api/v1/knowledge-documents", tags=["解析"])


@router.post("/parse")
async def parse_document() -> dict:
    return ParseService.parse()


@router.get("/parse-result/query")
async def query_parse_result(doc_id: str = Query(..., alias="docId")) -> dict:
    return ParseService.query_parse_result(doc_id)


@router.get("/parse-result/issue-download-ticket")
async def issue_download_ticket(doc_id: str = Query(..., alias="docId")) -> dict:
    return ParseService.issue_download_ticket(doc_id)


@router.get("/parse-result/download")
async def download_parse_result(doc_id: str = Query(..., alias="docId"), ticket: str = Query(...)) -> dict:
    return ParseService.download_parse_result(doc_id, ticket)
