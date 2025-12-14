"""Run model."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class Run(Base):
    """Run represents a single report generation workflow."""

    __tablename__ = "runs"

    run_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic = Column(Text, nullable=False)
    status = Column(Text, nullable=False)  # 'initializing', 'running', 'completed', 'failed'
    created_at = Column(DateTime, default=datetime.utcnow)
    model_config = Column(JSONB)  # Model routing overrides, retrieval params
