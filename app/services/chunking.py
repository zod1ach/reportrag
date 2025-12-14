"""Paragraph-aware document chunking with overlap."""

import hashlib
from typing import List

from app.config import settings
from app.schemas.document import ChunkCreate


def chunk_document(text: str, doc_id: str) -> List[ChunkCreate]:
    """
    Chunk document text into paragraph-aware chunks with overlap.

    Args:
        text: Full document text
        doc_id: Document identifier

    Returns:
        List of ChunkCreate schemas
    """
    target_size = settings.CHUNK_TARGET_SIZE
    overlap_percent = settings.CHUNK_OVERLAP_PERCENT

    # Split into paragraphs (double newline)
    paragraphs = text.split("\n\n")
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks = []
    current_chunk = []
    current_length = 0
    chunk_index = 0
    char_offset = 0

    for paragraph in paragraphs:
        para_length = len(paragraph)

        # If adding this paragraph exceeds target, finalize current chunk
        if current_length + para_length > target_size and current_chunk:
            # Create chunk
            chunk_text = "\n\n".join(current_chunk)
            chunk_start = char_offset
            chunk_end = char_offset + len(chunk_text)

            chunks.append(
                _create_chunk_schema(
                    chunk_text=chunk_text,
                    doc_id=doc_id,
                    chunk_index=chunk_index,
                    char_start=chunk_start,
                    char_end=chunk_end,
                )
            )

            # Calculate overlap
            overlap_size = int(len(chunk_text) * overlap_percent)
            overlap_text = chunk_text[-overlap_size:] if overlap_size > 0 else ""

            # Reset for next chunk with overlap
            char_offset = chunk_end - len(overlap_text)
            current_chunk = [overlap_text] if overlap_text else []
            current_length = len(overlap_text)
            chunk_index += 1

        # Add paragraph to current chunk
        current_chunk.append(paragraph)
        current_length += para_length + 2  # +2 for "\n\n"

    # Handle remaining paragraphs
    if current_chunk:
        chunk_text = "\n\n".join(current_chunk)
        chunk_start = char_offset
        chunk_end = char_offset + len(chunk_text)

        chunks.append(
            _create_chunk_schema(
                chunk_text=chunk_text,
                doc_id=doc_id,
                chunk_index=chunk_index,
                char_start=chunk_start,
                char_end=chunk_end,
            )
        )

    return chunks


def _create_chunk_schema(
    chunk_text: str,
    doc_id: str,
    chunk_index: int,
    char_start: int,
    char_end: int,
) -> ChunkCreate:
    """
    Create a ChunkCreate schema from chunk data.

    Args:
        chunk_text: The chunk text
        doc_id: Document ID
        chunk_index: Index of this chunk
        char_start: Start offset in original document
        char_end: End offset in original document

    Returns:
        ChunkCreate schema
    """
    # Compute hash
    text_hash = hashlib.sha256(chunk_text.encode()).hexdigest()

    # Estimate tokens (simple heuristic: chars / 4)
    token_estimate = len(chunk_text) // 4

    # Create chunk ID
    chunk_id = f"{doc_id}::{chunk_index}"

    return ChunkCreate(
        chunk_id=chunk_id,
        chunk_index=chunk_index,
        text=chunk_text,
        char_start=char_start,
        char_end=char_end,
        text_hash=text_hash,
        token_estimate=token_estimate,
    )
