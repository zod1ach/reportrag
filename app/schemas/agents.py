"""Agent input/output schemas."""

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from pydantic import BaseModel


# Outline Agent
class OutlineNodeSchema(BaseModel):
    """Schema for an outline node."""

    node_id: str
    parent_id: Optional[str] = None
    title: str
    goal: str
    allowed_topics: List[str]
    excluded_topics: List[str]
    retrieval_queries: List[str]


class OutlineInput(BaseModel):
    """Input for OutlineAgent."""

    topic: str
    documents: List[Dict[str, Any]]  # Document metadata


class OutlineOutput(BaseModel):
    """Output from OutlineAgent."""

    nodes: List[OutlineNodeSchema]


# Retrieval Agent
class RetrievalInput(BaseModel):
    """Input for RetrievalAgent."""

    run_id: UUID
    node_id: str


class RetrievalOutput(BaseModel):
    """Output from RetrievalAgent."""

    chunk_count: int


# Evidence Agent
class EvidenceItemSchema(BaseModel):
    """Schema for an evidence item."""

    ev_id: str
    chunk_pk: int
    quote: str
    start_in_chunk: int
    end_in_chunk: int
    tag: str


class EvidenceInput(BaseModel):
    """Input for EvidenceAgent."""

    run_id: UUID
    node_id: str
    chunk_texts: List[Tuple[int, str]]  # (chunk_pk, text)


class EvidenceOutput(BaseModel):
    """Output from EvidenceAgent."""

    evidence_items: List[EvidenceItemSchema]


# Claim Agent
class ClaimSchema(BaseModel):
    """Schema for a claim."""

    claim_id: str
    claim: str
    type: str  # 'fact', 'finding', 'interpretation'
    strength: str  # 'strong', 'moderate', 'weak'
    conditions: Optional[str] = None
    evidence_ev_ids: List[str]
    conflicts: Optional[List[str]] = None


class ClaimInput(BaseModel):
    """Input for ClaimAgent."""

    run_id: UUID
    node_id: str
    evidence_items: List[EvidenceItemSchema]
    node_goal: str


class ClaimOutput(BaseModel):
    """Output from ClaimAgent."""

    claims: List[ClaimSchema]


# Draft Agent
class DraftInput(BaseModel):
    """Input for DraftAgent."""

    run_id: UUID
    node_id: str
    node_title: str
    claims: List[ClaimSchema]
    global_memory: Dict[str, Any]
    doc_mapping: Dict[int, str]  # chunk_pk -> doc_id


class DraftOutput(BaseModel):
    """Output from DraftAgent."""

    latex: str
    citations: List[str]
    quality_flags: Dict[str, Any]


# Global Memory Agent
class GlobalMemorySchema(BaseModel):
    """Schema for global memory."""

    definitions: Dict[str, str]
    notation: Dict[str, str]
    entities: List[str]
    assumptions: List[str]
    results: List[str]


class MemoryInput(BaseModel):
    """Input for GlobalMemoryAgent."""

    run_id: UUID
    new_claims: List[ClaimSchema]
    current_memory: Optional[GlobalMemorySchema] = None


class MemoryOutput(BaseModel):
    """Output from GlobalMemoryAgent."""

    memory: GlobalMemorySchema


# Global Consistency Agent
class ConsistencyInput(BaseModel):
    """Input for GlobalConsistencyAgent."""

    run_id: UUID
    outline_nodes: List[OutlineNodeSchema]
    global_memory: GlobalMemorySchema
    drafts: List[Dict[str, str]]  # node_id -> latex
    claim_summaries: List[Dict[str, Any]]  # node_id -> claims


class PatchPlan(BaseModel):
    """Patch plan from GlobalConsistencyAgent."""

    terminology_changes: Dict[str, str]  # old -> new
    conflicts_to_mention: List[str]
    nodes_needing_rewrite: List[str]  # node_ids
    reason: Dict[str, str]  # node_id -> reason


class ConsistencyOutput(BaseModel):
    """Output from GlobalConsistencyAgent."""

    patch_plan: PatchPlan


# Final Assembler Agent
class AssemblerInput(BaseModel):
    """Input for FinalAssembler."""

    run_id: UUID


class AssemblerOutput(BaseModel):
    """Output from FinalAssembler."""

    latex: str
