"""Document routes."""

import hashlib
import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.document import Chunk, Document
from app.schemas.document import DocumentResponse, DocumentUpsert
from app.services.chunking import chunk_document
from app.services.embeddings import EmbeddingService
from app.services.pdf_parser import extract_text_from_pdf

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


@router.post("/upload", response_model=DocumentResponse)
async def upload_document_file(
    file: UploadFile = File(...),
    title: str = Form(...),
    author: Optional[str] = Form(None),
    year: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Upload a document file (PDF or text).

    Args:
        file: Uploaded file (PDF or TXT)
        title: Document title
        author: Document author (optional)
        year: Publication year (optional)
        db: Database session

    Returns:
        DocumentResponse with doc_id and chunk count
    """
    # Read file content
    file_content = await file.read()

    # Extract text based on file type
    filename_lower = file.filename.lower() if file.filename else ""

    if filename_lower.endswith('.pdf'):
        try:
            content = extract_text_from_pdf(file_content)
            logger.info(f"Extracted {len(content)} characters from PDF: {file.filename}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {str(e)}")
    elif filename_lower.endswith(('.txt', '.md', '.text')):
        try:
            content = file_content.decode('utf-8')
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="File must be UTF-8 encoded text")
    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Only PDF and text files are supported."
        )

    if not content.strip():
        raise HTTPException(status_code=400, detail="File contains no text")

    # Compute content hash
    content_hash = hashlib.sha256(content.encode()).hexdigest()

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
        title=title,
        author=author or "",
        year=year,
        content_hash=content_hash,
    )
    db.add(doc)
    db.flush()

    logger.info(f"Created new document from file: {doc.doc_id}")

    # Chunk the content
    chunks = chunk_document(content, str(doc.doc_id))
    logger.info(f"Created {len(chunks)} chunks")

    # Generate embeddings
    embedding_service = EmbeddingService()
    texts = [c.text for c in chunks]
    embeddings = embedding_service.embed_texts(texts)

    # Insert chunks
    for i, chunk_schema in enumerate(chunks):
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
