"""Claim and Draft models."""

from sqlalchemy import Column, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class Claim(Base):
    """Claim derived from evidence."""

    __tablename__ = "claims"

    claim_pk = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False)
    node_id = Column(Text, nullable=False)
    claim_id = Column(Text, nullable=False)
    claim = Column(Text, nullable=False)
    type = Column(Text)
    strength = Column(Text)
    conditions = Column(Text)
    evidence_ev_ids = Column(JSONB)  # Array of ev_id references
    conflicts = Column(JSONB)

    __table_args__ = ({"schema": None},)


class Draft(Base):
    """LaTeX draft for an outline node."""

    __tablename__ = "drafts"

    draft_pk = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False)
    node_id = Column(Text, nullable=False, unique=True)
    latex = Column(Text, nullable=False)
    citations = Column(JSONB)  # Array of doc_ids cited
    quality_flags = Column(JSONB)

    __table_args__ = ({"schema": None},)
