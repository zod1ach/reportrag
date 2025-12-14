"""Background worker for processing jobs."""

import logging
import time
from typing import Dict, Type

from sqlalchemy.orm import Session

from app.agents.assembler import FinalAssembler
from app.agents.base import BaseAgent
from app.agents.claim import ClaimAgent
from app.agents.consistency import GlobalConsistencyAgent
from app.agents.draft import DraftAgent
from app.agents.evidence import EvidenceAgent
from app.agents.global_memory import GlobalMemoryAgent
from app.agents.outline import OutlineAgent
from app.agents.retrieval import RetrievalAgent
from app.config import settings
from app.database import SessionLocal
from app.models.job import Job
from app.models.outline import OutlineNode
from app.models.run import Run
from app.services.llm_client import LLMClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


class Worker:
    """Background worker for processing jobs."""

    def __init__(self):
        """Initialize worker."""
        self.llm_client = LLMClient()
        self.poll_interval = settings.WORKER_POLL_INTERVAL
        self.max_retries = settings.MAX_JOB_RETRIES

        # Agent registry
        self.agents: Dict[str, Type[BaseAgent]] = {
            "outline": OutlineAgent,
            "retrieval": RetrievalAgent,
            "evidence": EvidenceAgent,
            "claim": ClaimAgent,
            "draft": DraftAgent,
            "global_memory": GlobalMemoryAgent,
            "consistency": GlobalConsistencyAgent,
            "assembler": FinalAssembler,
        }

    def run(self, stop_event=None):
        """Main worker loop.

        Args:
            stop_event: Optional threading.Event to signal worker to stop
        """
        logger.info("Worker started - waiting for database to be ready...")

        # Wait for database tables to be created
        import sqlalchemy
        max_wait = 60  # Wait up to 60 seconds for migrations
        waited = 0
        while waited < max_wait:
            try:
                db = SessionLocal()
                # Try to query jobs table to verify it exists
                db.execute(sqlalchemy.text("SELECT 1 FROM jobs LIMIT 1"))
                db.close()
                logger.info("Database is ready, starting worker loop")
                break
            except Exception as e:
                if "does not exist" in str(e):
                    logger.info(f"Waiting for migrations to complete... ({waited}s)")
                    time.sleep(2)
                    waited += 2
                else:
                    logger.error(f"Database error: {e}")
                    time.sleep(2)
                    waited += 2

        if waited >= max_wait:
            logger.error("Database not ready after 60 seconds, starting anyway...")

        while True:
            # Check if stop signal received
            if stop_event and stop_event.is_set():
                logger.info("Worker stop signal received")
                break

            try:
                db = SessionLocal()
                job = self.get_next_job(db)

                if job:
                    self.process_job(job, db)
                else:
                    db.close()
                    time.sleep(self.poll_interval)

            except KeyboardInterrupt:
                logger.info("Worker shutting down")
                break
            except Exception as e:
                logger.error(f"Worker error: {e}", exc_info=True)
                time.sleep(self.poll_interval)

    def get_next_job(self, db: Session) -> Job:
        """Get next queued job."""
        job = (
            db.query(Job)
            .filter(Job.status == "queued")
            .order_by(Job.created_at)
            .with_for_update(skip_locked=True)
            .first()
        )
        return job

    def process_job(self, job: Job, db: Session):
        """Process a single job."""
        logger.info(f"Processing job {job.job_id} (agent: {job.agent})")

        # Mark as running
        job.status = "running"
        db.commit()

        try:
            # Get agent
            agent_class = self.agents.get(job.agent)
            if not agent_class:
                raise ValueError(f"Unknown agent: {job.agent}")

            agent = agent_class(self.llm_client, db)

            # Execute
            result = agent.execute(job.payload)

            # Mark done
            job.status = "done"
            db.commit()

            logger.info(f"Job {job.job_id} completed successfully")

            # Enqueue next jobs
            self.enqueue_next_jobs(job, result, db)

        except Exception as e:
            logger.error(f"Job {job.job_id} failed: {e}", exc_info=True)

            # Handle failure
            job.retries += 1
            job.last_error = str(e)

            if job.retries >= self.max_retries:
                job.status = "failed"
                # Mark run as failed
                run = db.query(Run).filter(Run.run_id == job.run_id).first()
                if run:
                    run.status = "failed"
                logger.error(f"Job {job.job_id} failed after {job.retries} retries")
            else:
                job.status = "queued"
                logger.warning(f"Job {job.job_id} retry {job.retries}/{self.max_retries}")

            db.commit()

        finally:
            db.close()

    def enqueue_next_jobs(self, job: Job, result: Dict, db: Session):
        """Enqueue next jobs based on agent type."""
        run_id = job.run_id

        if job.agent == "outline":
            # After outline, enqueue retrieval for each node
            nodes = db.query(OutlineNode).filter(
                OutlineNode.run_id == run_id,
                OutlineNode.status == "pending",
            ).all()

            for node in nodes:
                retrieval_job = Job(
                    run_id=run_id,
                    node_id=node.node_id,
                    agent="retrieval",
                    status="queued",
                    payload={"run_id": str(run_id), "node_id": node.node_id},
                )
                db.add(retrieval_job)

            db.commit()
            logger.info(f"Enqueued {len(nodes)} retrieval jobs")

        elif job.agent == "retrieval":
            # After retrieval, enqueue evidence
            evidence_job = Job(
                run_id=run_id,
                node_id=job.node_id,
                agent="evidence",
                status="queued",
                payload={"run_id": str(run_id), "node_id": job.node_id},
            )
            db.add(evidence_job)
            db.commit()

        elif job.agent == "evidence":
            # After evidence, enqueue claim + global_memory
            claim_job = Job(
                run_id=run_id,
                node_id=job.node_id,
                agent="claim",
                status="queued",
                payload={"run_id": str(run_id), "node_id": job.node_id},
            )
            memory_job = Job(
                run_id=run_id,
                node_id=job.node_id,
                agent="global_memory",
                status="queued",
                payload={"run_id": str(run_id), "node_id": job.node_id},
            )
            db.add(claim_job)
            db.add(memory_job)
            db.commit()

        elif job.agent == "claim":
            # After claim, enqueue draft
            draft_job = Job(
                run_id=run_id,
                node_id=job.node_id,
                agent="draft",
                status="queued",
                payload={
                    "run_id": str(run_id),
                    "node_id": job.node_id,
                    "node_title": job.payload.get("node_title", ""),
                },
            )
            db.add(draft_job)
            db.commit()

        elif job.agent == "draft":
            # Check if all nodes drafted
            total_nodes = db.query(OutlineNode).filter(OutlineNode.run_id == run_id).count()
            drafted_nodes = (
                db.query(OutlineNode)
                .filter(OutlineNode.run_id == run_id, OutlineNode.status == "drafted")
                .count()
            )

            # After all drafts, enqueue assembler
            if drafted_nodes == total_nodes:
                assembler_job = Job(
                    run_id=run_id,
                    agent="assembler",
                    status="queued",
                    payload={"run_id": str(run_id)},
                )
                db.add(assembler_job)
                db.commit()
                logger.info("All nodes drafted, enqueued assembler job")

        elif job.agent == "assembler":
            # Mark run as completed
            run = db.query(Run).filter(Run.run_id == run_id).first()
            if run:
                run.status = "completed"
                db.commit()
                logger.info(f"Run {run_id} completed")


def worker_loop(stop_event=None):
    """Run worker loop (for use as background thread).

    Args:
        stop_event: Optional threading.Event to signal worker to stop
    """
    worker = Worker()
    worker.run(stop_event=stop_event)


def main():
    """Entry point for standalone worker."""
    worker = Worker()
    worker.run()


if __name__ == "__main__":
    main()
