"""Endpoints de documentos (RAG local)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.rag.document_loader import DocumentProcessingError
from app.schemas import (
    DocumentDetail,
    DocumentOut,
    DocumentSearchHit,
    DocumentSearchRequest,
    DocumentSearchResponse,
    DocumentUploadResponse,
)
from app.security.auth import api_key_auth
from app.services import document_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"], dependencies=[Depends(api_key_auth)])


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    settings = get_settings()
    raw = await file.read()
    if len(raw) > settings.max_document_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"El archivo supera el máximo de {settings.max_document_size_mb} MB.",
        )
    try:
        document, chunk_count = document_service.save_uploaded_document(
            db, file.filename or "documento.txt", raw
        )
    except document_service.DuplicateDocumentError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Documento duplicado: ya existe como id={exc.existing.id} ({exc.existing.filename}).",
        ) from exc
    except DocumentProcessingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return DocumentUploadResponse(
        document=DocumentOut.model_validate(document),
        chunk_count=chunk_count,
        message=f"Documento indexado en {chunk_count} chunk(s).",
    )


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)) -> list[DocumentOut]:
    return [DocumentOut.model_validate(d) for d in document_service.list_documents(db)]


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(document_id: int, db: Session = Depends(get_db)) -> DocumentDetail:
    document = document_service.get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"Documento {document_id} no encontrado.")
    return DocumentDetail(
        id=document.id,
        filename=document.filename,
        content_type=document.content_type,
        text_hash=document.text_hash,
        uploaded_at=document.uploaded_at,
        chunk_count=document_service.count_chunks(db, document.id),
        preview=document_service.get_document_preview(db, document),
    )


@router.post("/search", response_model=DocumentSearchResponse)
def search_documents(
    request: DocumentSearchRequest, db: Session = Depends(get_db)
) -> DocumentSearchResponse:
    hits = document_service.search_documents(db, request.query, request.top_k)
    return DocumentSearchResponse(
        query=request.query,
        hits=[
            DocumentSearchHit(
                document_id=hit.document_id,
                filename=hit.filename,
                chunk_index=hit.chunk_index,
                score=round(hit.score, 3),
                snippet=hit.snippet,
            )
            for hit in hits
        ],
    )
