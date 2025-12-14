"""Job model for worker queue."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class Job(Base):
    """Job represents a queued task for the worker."""

    __tablename__ = "jobs"

    job_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False)
    node_id = Column(Text)  # Nullable for run-level jobs
    agent = Column(Text, nullable=False)  # 'outline', 'retrieval', 'evidence', etc.
    status = Column(Text, nullable=False)  # 'queued', 'running', 'done', 'failed'
    payload = Column(JSONB)
    retries = Column(Integer, default=0)
    last_error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_run_id", "run_id"),
        {"schema": None},
    )
