"""Global memory model."""

from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class GlobalMemory(Base):
    """Global memory storing definitions, notation, entities, etc."""

    __tablename__ = "global_memory"

    memory_pk = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False, unique=True)
    definitions = Column(JSONB)
    notation = Column(JSONB)
    entities = Column(JSONB)
    assumptions = Column(JSONB)
    results = Column(JSONB)

    __table_args__ = ({"schema": None},)
