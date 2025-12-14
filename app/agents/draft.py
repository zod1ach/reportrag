"""Draft agent using Llama 70B."""

import json
import logging
import re
from typing import Any, Dict

from app.agents.base import BaseAgent
from app.models.claim import Claim, Draft
from app.models.document import Chunk
from app.models.memory import GlobalMemory

logger = logging.getLogger(__name__)


class DraftAgent(BaseAgent):
    """Agent for drafting LaTeX from claims."""

    MODEL = "meta-llama/llama-3.3-70b-instruct:free"

    def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Draft LaTeX content from claims."""
        run_id = payload["run_id"]
        node_id = payload["node_id"]
        node_title = payload["node_title"]

        # Load claims
        claims = self.db.query(Claim).filter(
            Claim.run_id == run_id,
            Claim.node_id == node_id,
        ).all()

        # Load global memory
        memory = self.db.query(GlobalMemory).filter(
            GlobalMemory.run_id == run_id
        ).first()

        # Build doc mapping (chunk_pk -> doc_id)
        evidence_chunks = set()
        for claim in claims:
            for ev_id in (claim.evidence_ev_ids or []):
                # Would need to join evidence_items to get chunk_pk
                pass

        # Simplified: get doc IDs from chunks
        doc_mapping = {}  # Would populate from evidence

        # Build claims table
        claims_str = "\n".join([
            f"- [{claim.claim_id}] {claim.claim} (evidence: {claim.evidence_ev_ids})"
            for claim in claims
        ])

        memory_str = json.dumps(memory.definitions if memory else {}, indent=2)

        prompt = f"""Write LaTeX content for section: {node_title}

Use ONLY the following claims (do not add new information):
{claims_str}

Available definitions/notation:
{memory_str}

Requirements:
1. Each paragraph MUST include at least one \\cite{{docX}}
2. Do not add new factual claims
3. Return JSON: {{"latex": "...", "citations": [...]}}
"""

        messages = [{"role": "user", "content": prompt}]
        response = self.llm.chat_completion(
            model=self.MODEL,
            messages=messages,
            temperature=0.5,
            max_tokens=4000,
            json_mode=True,
        )

        result = json.loads(response)
        latex = result["latex"]
        citations = result.get("citations", [])

        # Quality checks
        quality_flags = {}
        paragraphs = latex.split("\n\n")
        missing_citations = sum(1 for p in paragraphs if p.strip() and "\\cite" not in p)
        if missing_citations > 0:
            quality_flags["missing_citations"] = missing_citations

        # Persist
        draft = Draft(
            run_id=run_id,
            node_id=node_id,
            latex=latex,
            citations=citations,
            quality_flags=quality_flags,
        )
        self.db.merge(draft)
        self.db.commit()

        return {"latex": latex, "citations": citations, "quality_flags": quality_flags}
