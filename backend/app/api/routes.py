"""Health and document-ingestion API routes."""

from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from backend.app.services.document_ingestion import (
    DocumentIngestionError,
    delete_document as remove_document,
    ingest_document,
    list_documents as get_documents,
)
from backend.app.services.analytics import (
    get_collection_summary,
    get_document_analytics,
    get_term_analytics,
)
from backend.app.services.index_construction import get_index_stats
from backend.app.services.multi_pattern_search import search_multiple_patterns
from backend.app.services.phrase_wildcard_search import (
    WildcardPatternError,
    search_phrase,
    search_wildcard,
)
from backend.app.services.relevance_ranking import rank_search_results

router = APIRouter()


class MultiPatternSearchRequest(BaseModel):
    """Patterns to search across the indexed document collection."""

    patterns: list[str]


class PhraseSearchRequest(BaseModel):
    """Exact phrase to find in indexed documents."""

    phrase: str


class WildcardSearchRequest(BaseModel):
    """One simple prefix or suffix wildcard pattern."""

    pattern: str


class RankedSearchRequest(BaseModel):
    """Keyword query to rank using the inverted index."""

    query: str


DOCUMENT_SUMMARY_FIELDS = (
    "document_id",
    "filename",
    "file_type",
    "character_count",
    "word_count",
    "indexed_at",
)


def _document_summary(record: dict[str, Any]) -> dict[str, Any]:
    """Return metadata without sending document text back in API responses."""
    return {field: record[field] for field in DOCUMENT_SUMMARY_FIELDS}


async def _store_upload(upload: UploadFile) -> dict[str, Any]:
    """Read one bounded upload and pass it to the ingestion service."""
    content = await upload.read(10 * 1024 * 1024 + 1)
    try:
        return ingest_document(upload.filename, content)
    except DocumentIngestionError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/health")
def health_check() -> dict[str, str]:
    """Report whether the starter API is responding."""
    return {"status": "ok"}


@router.post("/documents", status_code=201)
async def upload_document(file: UploadFile = File(...)) -> dict[str, Any]:
    """Upload and index one TXT, Markdown, or CSV document."""
    record = await _store_upload(file)
    return {"document": _document_summary(record)}


@router.post("/documents/batch", status_code=201)
async def upload_documents(files: list[UploadFile] = File(...)) -> dict[str, Any]:
    """Upload several documents and report successes and per-file errors."""
    indexed_documents = []
    errors = []
    for upload in files:
        try:
            record = await _store_upload(upload)
            indexed_documents.append(_document_summary(record))
        except HTTPException as error:
            errors.append({"filename": upload.filename, "error": error.detail})

    return {"documents": indexed_documents, "errors": errors}


@router.get("/documents")
def list_indexed_documents() -> dict[str, list[dict[str, Any]]]:
    """List document metadata without returning stored text."""
    return {"documents": [_document_summary(record) for record in get_documents()]}


@router.get("/index/stats")
def index_statistics() -> dict[str, int]:
    """Return counts for the current in-memory inverted index."""
    return get_index_stats()


@router.get("/analytics/summary")
def analytics_summary() -> dict[str, int | float]:
    """Summarize indexed document and token counts."""
    return get_collection_summary()


@router.get("/analytics/documents")
def analytics_documents() -> dict[str, list[dict[str, Any]]]:
    """Return word and term statistics for every indexed document."""
    return {"documents": get_document_analytics()}


@router.get("/analytics/terms")
def analytics_terms(limit: int = Query(default=10, ge=1, le=100)) -> dict[str, Any]:
    """Return collection terms ordered by frequency and then alphabetically."""
    return {"limit": limit, "terms": get_term_analytics(limit)}


@router.post("/search/multi-pattern")
def multi_pattern_search(request: MultiPatternSearchRequest) -> dict[str, Any]:
    """Find all submitted patterns across the currently indexed documents."""
    return search_multiple_patterns(request.patterns)


@router.post("/search/phrase")
def phrase_search_endpoint(request: PhraseSearchRequest) -> dict[str, Any]:
    """Find words that occur consecutively and in the requested order."""
    return search_phrase(request.phrase)


@router.post("/search/wildcard")
def wildcard_search_endpoint(request: WildcardSearchRequest) -> dict[str, Any]:
    """Search indexed terms using one leading or trailing asterisk."""
    try:
        return search_wildcard(request.pattern)
    except WildcardPatternError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/search/ranked")
def ranked_search_endpoint(request: RankedSearchRequest) -> dict[str, Any]:
    """Return keyword results ordered by the transparent relevance score."""
    return rank_search_results(request.query)


@router.delete("/documents/{document_id}", status_code=204)
def delete_indexed_document(document_id: str) -> None:
    """Delete a previously uploaded document."""
    if not remove_document(document_id):
        raise HTTPException(status_code=404, detail="Document not found.")