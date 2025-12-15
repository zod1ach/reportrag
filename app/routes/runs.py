"""Run routes."""

import logging
import uuid
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.claim import Claim, Draft
from app.models.document import Document
from app.models.evidence import EvidenceItem
from app.models.job import Job
from app.models.memory import GlobalMemory
from app.models.outline import OutlineNode
from app.models.run import Run
from app.schemas.run import (
    ArtifactsResponse,
    LatexResponse,
    RunCreate,
    RunResponse,
    RunStartResponse,
    RunStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunResponse)
def create_run(
    data: RunCreate,
    db: Session = Depends(get_db),
):
    """Create a new run."""
    run = Run(
        topic=data.topic,
        status="initializing",
        model_config=data.model_config,
    )
    db.add(run)
    db.flush()  # Flush to get the auto-generated run_id

    # Initialize global memory
    memory = GlobalMemory(
        run_id=run.run_id,
        definitions={},
        notation={},
        entities=[],
        assumptions=[],
        results=[],
    )
    db.add(memory)

    db.commit()

    logger.info(f"Created run {run.run_id}")

    return RunResponse(
        run_id=run.run_id,
        topic=run.topic,
        status=run.status,
    )


@router.get("/list")
def list_runs(db: Session = Depends(get_db)):
    """List all runs with basic info."""
    runs = db.query(Run).order_by(Run.created_at.desc()).all()
    return [
        {
            "run_id": str(r.run_id),
            "topic": r.topic,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in runs
    ]


@router.post("/{run_id}/start", response_model=RunStartResponse)
def start_run(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Start a run by enqueueing the outline job."""
    run = db.query(Run).filter(Run.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Get all documents for outline
    documents = db.query(Document).all()
    doc_list = [
        {"doc_id": str(d.doc_id), "title": d.title, "author": d.author, "year": d.year}
        for d in documents
    ]

    # Enqueue outline job
    job = Job(
        run_id=run_id,
        agent="outline",
        status="queued",
        payload={
            "run_id": str(run_id),
            "topic": run.topic,
            "documents": doc_list,
        },
    )
    db.add(job)

    run.status = "running"
    db.commit()

    logger.info(f"Started run {run_id}, outline job {job.job_id}")

    return RunStartResponse(
        run_id=run_id,
        job_id=job.job_id,
        message="Run started, outline job enqueued",
    )


@router.get("/{run_id}", response_model=RunStatus)
def get_run_status(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Get run status and progress."""
    run = db.query(Run).filter(Run.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Count jobs by status
    job_counts = {}
    for status in ["queued", "running", "done", "failed"]:
        count = db.query(func.count(Job.job_id)).filter(
            Job.run_id == run_id,
            Job.status == status,
        ).scalar()
        job_counts[status] = count

    # Calculate progress
    total_jobs = sum(job_counts.values())
    done_jobs = job_counts["done"]
    progress_percent = (done_jobs / total_jobs * 100) if total_jobs > 0 else 0

    return RunStatus(
        run_id=run_id,
        topic=run.topic,
        status=run.status,
        job_counts=job_counts,
        progress_percent=progress_percent,
    )


@router.get("/{run_id}/artifacts", response_model=ArtifactsResponse)
def get_artifacts(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Get run artifacts (outline, evidence, claims, drafts)."""
    run = db.query(Run).filter(Run.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Outline nodes
    nodes = db.query(OutlineNode).filter(OutlineNode.run_id == run_id).all()
    outline_nodes = [
        {
            "node_id": n.node_id,
            "title": n.title,
            "status": n.status,
        }
        for n in nodes
    ]

    # Evidence summary
    evidence_summary = {}
    for node in nodes:
        count = db.query(func.count(EvidenceItem.ev_pk)).filter(
            EvidenceItem.run_id == run_id,
            EvidenceItem.node_id == node.node_id,
        ).scalar()
        evidence_summary[node.node_id] = count

    # Claims summary
    claims_summary = {}
    for node in nodes:
        count = db.query(func.count(Claim.claim_pk)).filter(
            Claim.run_id == run_id,
            Claim.node_id == node.node_id,
        ).scalar()
        claims_summary[node.node_id] = count

    # Drafts
    drafts = db.query(Draft).filter(Draft.run_id == run_id).all()
    drafts_dict = {d.node_id: d.latex for d in drafts}

    return ArtifactsResponse(
        outline_nodes=outline_nodes,
        evidence_summary=evidence_summary,
        claims_summary=claims_summary,
        drafts=drafts_dict,
    )


@router.delete("/{run_id}")
def delete_run(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Delete a run and all associated data."""
    run = db.query(Run).filter(Run.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    db.delete(run)
    db.commit()

    logger.info(f"Deleted run {run_id}")

    return {"message": "Run deleted"}


@router.get("/{run_id}/latex", response_model=LatexResponse)
def get_latex(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Get final LaTeX output."""
    run = db.query(Run).filter(Run.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status != "completed":
        raise HTTPException(status_code=400, detail="Run not completed")

    # Get the final latex from the assembler job result
    # For simplicity, re-run assembler logic here
    from app.agents.assembler import FinalAssembler
    from app.services.llm_client import LLMClient

    llm_client = LLMClient()
    assembler = FinalAssembler(llm_client, db)
    result = assembler.execute({"run_id": str(run_id)})

    return LatexResponse(
        run_id=run_id,
        latex=result["latex"],
        status=run.status,
    )
