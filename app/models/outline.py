"""Outline and retrieval result models."""

from sqlalchemy import Column, ForeignKey, Index, Integer, Real, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class OutlineNode(Base):
    """Outline node representing a section or subsection."""

    __tablename__ = "outline_nodes"

    node_pk = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False)
    node_id = Column(Text, nullable=False)
    parent_id = Column(Text)
    title = Column(Text, nullable=False)
    goal = Column(Text)
    allowed_topics = Column(JSONB)
    excluded_topics = Column(JSONB)
    retrieval_queries = Column(JSONB)
    status = Column(Text, nullable=False)  # 'pending', 'retrieved', 'drafted', 'completed'

    __table_args__ = ({"schema": None},)


class RetrievalResult(Base):
    """Retrieval results for each outline node."""

    __tablename__ = "retrieval_results"

    result_pk = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False)
    node_id = Column(Text, nullable=False)
    chunk_pk = Column(Integer, ForeignKey("chunks.chunk_pk"))
    fts_score = Column(Real)
    vec_score = Column(Real)
    score = Column(Real, nullable=False)
    rank = Column(Integer, nullable=False)

    __table_args__ = (Index("idx_retrieval_run_node", "run_id", "node_id"), {"schema": None})
