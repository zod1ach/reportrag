"""Document-related Pydantic schemas."""

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class DocumentUpsert(BaseModel):
    """Schema for upserting a document."""

    title: str
    author: Optional[str] = None
    year: Optional[int] = None
    content: str
    embeddings: Optional[List[List[float]]] = None


class DocumentResponse(BaseModel):
    """Response after document upsert."""

    doc_id: UUID
    chunk_count: int
    existed: bool


class ChunkCreate(BaseModel):
    """Schema for creating a chunk."""

    chunk_id: str
    chunk_index: int
    text: str
    char_start: int
    char_end: int
    text_hash: str
    token_estimate: int


class DocumentMeta(BaseModel):
    """Document metadata for outline generation."""

    doc_id: UUID
    title: str
    author: Optional[str]
    year: Optional[int]
