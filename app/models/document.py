"""Document and Chunk models."""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import relationship

from app.config import settings
from app.database import Base


class Document(Base):
    """Document metadata table."""

    __tablename__ = "documents"

    doc_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(Text, nullable=False)
    author = Column(Text)
    year = Column(Integer)
    content_hash = Column(String(64), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    """Document chunk table with FTS and vector embeddings."""

    __tablename__ = "chunks"

    chunk_pk = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(UUID(as_uuid=True), ForeignKey("documents.doc_id", ondelete="CASCADE"), nullable=False)
    chunk_id = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    tsv = Column(TSVECTOR)
    embedding = Column(Vector(settings.EMBED_DIM))
    char_start = Column(Integer)
    char_end = Column(Integer)
    text_hash = Column(String(64), nullable=False)
    token_estimate = Column(Integer)

    # Relationships
    document = relationship("Document", back_populates="chunks")

    # Constraints
    __table_args__ = (
        Index("idx_chunks_doc_id", "doc_id"),
        Index("idx_chunks_gin_tsv", "tsv", postgresql_using="gin"),
        Index(
            "idx_chunks_ivfflat_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("idx_chunks_text_hash", "text_hash"),
        {"schema": None},
    )
