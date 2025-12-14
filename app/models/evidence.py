"""Evidence model."""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class EvidenceItem(Base):
    """Evidence item with validated quote and offsets."""

    __tablename__ = "evidence_items"

    ev_pk = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False)
    node_id = Column(Text, nullable=False)
    ev_id = Column(Text, nullable=False)
    chunk_pk = Column(Integer, ForeignKey("chunks.chunk_pk"))
    quote = Column(Text, nullable=False)
    start_in_chunk = Column(Integer, nullable=False)
    end_in_chunk = Column(Integer, nullable=False)
    tag = Column(Text)
    validated = Column(Boolean, default=False)

    __table_args__ = ({"schema": None},)
