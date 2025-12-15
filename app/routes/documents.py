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

    # Extract metadata using LLM if not provided
    if not title or title == file.filename.rsplit('.', 1)[0]:
        logger.info(f"Extracting metadata for: {file.filename}")
        from app.services.llm_client import LLMClient
        import json

        llm_client = LLMClient()
        content_preview = content[:3000]

        metadata_prompt = f"""Extract the title, author(s), and publication year from this document.

Document content:
{content_preview}

Return ONLY a JSON object with this exact format:
{{"title": "extracted title", "author": "author name(s)", "year": 2024}}

If you cannot find any field, use:
- title: use the filename "{file.filename}"
- author: use empty string ""
- year: use null

Be concise. Extract only what's clearly stated in the document."""

        try:
            logger.info(f"Calling DeepSeek to extract metadata from {file.filename}...")
            metadata_response = llm_client.chat_completion(
                model="tngtech/deepseek-r1t2-chimera:free",
                messages=[{"role": "user", "content": metadata_prompt}],
                temperature=0.1,
                max_tokens=500,  # Increased to ensure complete JSON
                json_mode=True,  # Force JSON output
            )

            logger.info(f"LLM metadata response FULL: {metadata_response}")  # Log full response to debug

            # Parse JSON response with multiple fallback strategies
            metadata_text = metadata_response

            # Strategy 1: Try direct JSON parse
            try:
                metadata = json.loads(metadata_text)
            except json.JSONDecodeError:
                # Strategy 2: Extract from markdown code blocks
                if "```json" in metadata_text:
                    metadata_text = metadata_text.split("```json")[1].split("```")[0].strip()
                elif "```" in metadata_text:
                    metadata_text = metadata_text.split("```")[1].split("```")[0].strip()

                # Strategy 3: Try to find JSON object with regex
                import re
                json_match = re.search(r'\{[^}]+\}', metadata_text, re.DOTALL)
                if json_match:
                    metadata_text = json_match.group(0)

                metadata = json.loads(metadata_text)

            # Validate metadata structure
            if not isinstance(metadata, dict):
                raise ValueError("Metadata is not a dictionary")

            # Extract and validate fields
            extracted_title = metadata.get("title", "")
            extracted_author = metadata.get("author", "")
            extracted_year = metadata.get("year")

            # Validate title (most important field)
            if not extracted_title or extracted_title.strip() == "" or extracted_title == file.filename:
                logger.warning(f"Invalid title extracted, using filename")
                title = file.filename.rsplit('.', 1)[0] if not title else title
            else:
                title = extracted_title.strip()

            # Validate author
            if extracted_author:
                author = extracted_author.strip()
            else:
                author = author or ""

            # Validate year
            if extracted_year:
                try:
                    year_int = int(extracted_year)
                    if 1900 <= year_int <= 2100:
                        year = year_int
                    else:
                        logger.warning(f"Year {year_int} out of range, setting to None")
                        year = None
                except (ValueError, TypeError):
                    logger.warning(f"Invalid year format '{extracted_year}', setting to None")
                    year = None

            logger.info(f"✓ Extracted metadata - Title: '{title}', Author: '{author}', Year: {year}")

        except Exception as e:
            logger.error(f"Failed to extract metadata with LLM: {e}", exc_info=True)
            logger.warning("Using fallback: filename as title")
            if not title:
                title = file.filename.rsplit('.', 1)[0]
            author = author or ""
            year = year

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


@router.post("/upload-batch")
async def upload_documents_batch(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Upload multiple documents at once. Processes them sequentially."""
    from app.services.llm_client import LLMClient
    import json
    import asyncio

    results = []
    llm_client = LLMClient()

    for i, file in enumerate(files):
        # Add delay between documents to avoid rate limits (except first one)
        if i > 0:
            logger.info(f"Waiting 6 seconds before processing next document ({i+1}/{len(files)})...")
            await asyncio.sleep(6)  # 6 second delay between documents to avoid rate limits

        logger.info(f"Processing document {i+1}/{len(files)}: {file.filename}")
        try:
            # Read file content
            file_content = await file.read()
            filename_lower = file.filename.lower() if file.filename else ""

            # Extract text based on file type
            if filename_lower.endswith('.pdf'):
                content = extract_text_from_pdf(file_content)
                logger.info(f"Extracted {len(content)} characters from PDF: {file.filename}")
            elif filename_lower.endswith(('.txt', '.md', '.text')):
                content = file_content.decode('utf-8')
            else:
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "error": "Unsupported file type. Please upload PDF or text files."
                })
                continue

            if not content.strip():
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "error": "File is empty or could not extract text"
                })
                continue

            # Extract metadata using LLM
            logger.info(f"Extracting metadata for: {file.filename}")

            # Use first ~3000 chars which usually contains title, author, year
            content_preview = content[:3000]

            metadata_prompt = f"""Extract the title, author(s), and publication year from this document.

Document content:
{content_preview}

Return ONLY a JSON object with this exact format:
{{"title": "extracted title", "author": "author name(s)", "year": 2024}}

If you cannot find any field, use:
- title: use the filename "{file.filename}"
- author: use empty string ""
- year: use null

Be concise. Extract only what's clearly stated in the document."""

            try:
                logger.info(f"Calling DeepSeek to extract metadata from {file.filename}...")
                metadata_response = llm_client.chat_completion(
                    model="tngtech/deepseek-r1t2-chimera:free",
                    messages=[{"role": "user", "content": metadata_prompt}],
                    temperature=0.1,
                    max_tokens=500,  # Increased to ensure complete JSON
                    json_mode=True,  # Force JSON output
                )

                logger.info(f"LLM metadata response for {file.filename} FULL: {metadata_response}")  # Log full response

                # Parse JSON response with multiple fallback strategies
                metadata_text = metadata_response

                # Strategy 1: Try direct JSON parse
                try:
                    metadata = json.loads(metadata_text)
                except json.JSONDecodeError:
                    # Strategy 2: Extract from markdown code blocks
                    if "```json" in metadata_text:
                        metadata_text = metadata_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in metadata_text:
                        metadata_text = metadata_text.split("```")[1].split("```")[0].strip()

                    # Strategy 3: Try to find JSON object with regex
                    import re
                    json_match = re.search(r'\{[^}]+\}', metadata_text, re.DOTALL)
                    if json_match:
                        metadata_text = json_match.group(0)

                    metadata = json.loads(metadata_text)

                # Validate metadata structure
                if not isinstance(metadata, dict):
                    raise ValueError("Metadata is not a dictionary")

                # Extract and validate fields
                extracted_title = metadata.get("title", "")
                extracted_author = metadata.get("author", "")
                extracted_year = metadata.get("year")

                # Validate title
                if not extracted_title or extracted_title.strip() == "" or extracted_title == file.filename:
                    title = file.filename.rsplit('.', 1)[0] if file.filename else "Untitled Document"
                else:
                    title = extracted_title.strip()

                # Validate author
                author = extracted_author.strip() if extracted_author else ""

                # Validate year
                if extracted_year:
                    try:
                        year_int = int(extracted_year)
                        year = year_int if 1900 <= year_int <= 2100 else None
                    except (ValueError, TypeError):
                        year = None
                else:
                    year = None

                logger.info(f"✓ Extracted metadata for {file.filename} - Title: '{title}', Author: '{author}', Year: {year}")

            except Exception as e:
                logger.error(f"Failed to extract metadata for {file.filename}: {e}", exc_info=True)
                logger.warning(f"Using fallback for {file.filename}")
                title = file.filename.rsplit('.', 1)[0] if file.filename else "Untitled Document"
                author = ""
                year = None

            # Compute content hash
            content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

            # Check if document exists
            existing_doc = db.query(Document).filter(Document.content_hash == content_hash).first()

            if existing_doc:
                logger.info(f"Document already exists: {existing_doc.doc_id}")
                chunk_count = db.query(func.count(Chunk.chunk_pk)).filter(
                    Chunk.doc_id == existing_doc.doc_id
                ).scalar()
                results.append({
                    "filename": file.filename,
                    "success": True,
                    "doc_id": str(existing_doc.doc_id),
                    "chunk_count": chunk_count,
                    "existed": True
                })
                continue

            # Create new document
            doc = Document(
                title=title,
                author="",
                year=None,
                content_hash=content_hash,
            )
            db.add(doc)
            db.flush()

            logger.info(f"Created new document from file: {doc.doc_id}")

            # Chunk the content
            chunks = chunk_document(content, str(doc.doc_id))
            logger.info(f"Created {len(chunks)} chunks for {file.filename}")

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

            results.append({
                "filename": file.filename,
                "success": True,
                "doc_id": str(doc.doc_id),
                "chunk_count": len(chunks),
                "existed": False
            })

        except Exception as e:
            logger.error(f"Error processing {file.filename}: {e}", exc_info=True)
            results.append({
                "filename": file.filename,
                "success": False,
                "error": str(e)
            })

    # Return summary
    successful = sum(1 for r in results if r["success"])
    return {
        "total": len(files),
        "successful": successful,
        "failed": len(files) - successful,
        "results": results
    }


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
