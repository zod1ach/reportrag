"""Document routes."""

import hashlib
import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.document import Chunk, Document
from app.schemas.document import DocumentResponse, DocumentUpsert
from app.services.chunking import chunk_document
from app.services.embeddings import EmbeddingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upsert", response_model=DocumentResponse)
def upsert_document(
    data: DocumentUpsert,
    db: Session = Depends(get_db),
):
    """
    Upsert a document: insert if new, return existing if duplicate.

    Args:
        data: Document data with optional embeddings
        db: Database session

    Returns:
        DocumentResponse with doc_id and chunk count
    """
    # Compute content hash
    content_hash = hashlib.sha256(data.content.encode()).hexdigest()

    # Check if document exists
    existing_doc = db.query(Document).filter(Document.content_hash == content_hash).first()

    if existing_doc:
        logger.info(f"Document already exists: {existing_doc.doc_id}")
        chunk_count = db.query(func.count(Chunk.chunk_pk)).filter(
            Chunk.doc_id == existing_doc.doc_id
        ).scalar()
        return DocumentResponse(
            doc_id=existing_doc.doc_id,
            chunk_count=chunk_count,
            existed=True,
        )

    # Create new document
    doc = Document(
        title=data.title,
        author=data.author,
        year=data.year,
        content_hash=content_hash,
    )
    db.add(doc)
    db.flush()  # Get doc_id

    logger.info(f"Created new document: {doc.doc_id}")

    # Chunk the content
    chunks = chunk_document(data.content, str(doc.doc_id))
    logger.info(f"Created {len(chunks)} chunks")

    # Handle embeddings
    embedding_service = EmbeddingService()
    if data.embeddings:
        # Client-provided embeddings
        embedding_service.accept_client_embeddings(len(chunks), data.embeddings)
        embeddings = data.embeddings
    else:
        # Generate embeddings
        texts = [c.text for c in chunks]
        embeddings = embedding_service.embed_texts(texts)

    # Insert chunks
    for i, chunk_schema in enumerate(chunks):
        # Compute FTS vector
        tsv_query = func.to_tsvector("english", chunk_schema.text)

        chunk = Chunk(
            doc_id=doc.doc_id,
            chunk_id=chunk_schema.chunk_id,
            chunk_index=chunk_schema.chunk_index,
            text=chunk_schema.text,
            tsv=tsv_query,
            embedding=embeddings[i],
            char_start=chunk_schema.char_start,
            char_end=chunk_schema.char_end,
            text_hash=chunk_schema.text_hash,
            token_estimate=chunk_schema.token_estimate,
        )
        db.add(chunk)

    db.commit()

    return DocumentResponse(
        doc_id=doc.doc_id,
        chunk_count=len(chunks),
        existed=False,
    )


@router.get("/list")
def list_documents(db: Session = Depends(get_db)):
    """List all documents."""
    docs = db.query(Document).order_by(Document.created_at.desc()).all()
    return [
        {
            "doc_id": str(d.doc_id),
            "title": d.title,
            "author": d.author,
            "year": d.year,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]


@router.delete("/{doc_id}")
def delete_document(
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Delete a document."""
    doc = db.query(Document).filter(Document.doc_id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    db.delete(doc)
    db.commit()

    logger.info(f"Deleted document {doc_id}")

    return {"message": "Document deleted"}
