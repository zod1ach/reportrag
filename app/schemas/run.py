"""Run-related Pydantic schemas."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


class RunCreate(BaseModel):
    """Schema for creating a new run."""

    topic: str
    model_config: Optional[Dict[str, Any]] = None


class RunResponse(BaseModel):
    """Response after creating a run."""

    run_id: UUID
    topic: str
    status: str


class RunStatus(BaseModel):
    """Run status response."""

    run_id: UUID
    topic: str
    status: str
    job_counts: Dict[str, int]  # {'queued': X, 'running': Y, 'done': Z, 'failed': W}
    progress_percent: float


class RunStartResponse(BaseModel):
    """Response after starting a run."""

    run_id: UUID
    job_id: UUID
    message: str


class ArtifactsResponse(BaseModel):
    """Artifacts response containing outline, evidence, claims, drafts."""

    outline_nodes: List[Dict[str, Any]]
    evidence_summary: Dict[str, int]  # node_id -> evidence count
    claims_summary: Dict[str, int]  # node_id -> claim count
    drafts: Dict[str, str]  # node_id -> latex


class LatexResponse(BaseModel):
    """Final LaTeX response."""

    run_id: UUID
    latex: str
    status: str
