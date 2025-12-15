"""Claim agent."""

import json
import logging
from typing import Any, Dict

from app.agents.base import BaseAgent
from app.models.claim import Claim
from app.models.evidence import EvidenceItem
from app.schemas.agents import ClaimOutput

logger = logging.getLogger(__name__)


class ClaimAgent(BaseAgent):
    """Agent for generating claims from evidence."""

    MODEL = "google/gemini-2.0-flash-exp:free"

    def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generate claims from evidence."""
        run_id = payload["run_id"]
        node_id = payload["node_id"]

        # Load evidence
        evidence_items = self.db.query(EvidenceItem).filter(
            EvidenceItem.run_id == run_id,
            EvidenceItem.node_id == node_id,
        ).all()

        if not evidence_items:
            raise ValueError("No evidence found")

        # Build evidence summary
        evidence_str = "\n".join([
            f"- {e.ev_id}: \"{e.quote[:200]}...\" (tag: {e.tag})"
            for e in evidence_items
        ])

        prompt = f"""Generate claims from the following evidence.

Requirements:
1. Each claim must reference evidence IDs
2. Identify gaps, conflicts, and conditional claims
3. Classify claims as: fact, finding, or interpretation
4. Rate strength: strong, moderate, weak

Evidence:
{evidence_str}

Return JSON: {{"claims": [...]}}
Each claim: {{"claim_id": "...", "claim": "...", "type": "...", "strength": "...", "evidence_ev_ids": [...], "conflicts": [...]}}
"""

        messages = [{"role": "user", "content": prompt}]
        response = self.llm.chat_completion(
            model=self.MODEL,
            messages=messages,
            temperature=0.3,
            max_tokens=3000,
            json_mode=True,
        )

        result = json.loads(response)
        output = ClaimOutput(**result)

        # Persist
        for claim in output.claims:
            claim_obj = Claim(
                run_id=run_id,
                node_id=node_id,
                claim_id=claim.claim_id,
                claim=claim.claim,
                type=claim.type,
                strength=claim.strength,
                conditions=claim.conditions,
                evidence_ev_ids=claim.evidence_ev_ids,
                conflicts=claim.conflicts,
            )
            self.db.add(claim_obj)

        self.db.commit()

        return {
            "claims": [c.dict() for c in output.claims],
            "claim_count": len(output.claims)
        }

    def _validate(self, result: Dict[str, Any]) -> bool:
        """Validate claims exist and have evidence."""
        if "claims" not in result:
            return False
        for claim in result["claims"]:
            if not claim.get("evidence_ev_ids"):
                return False
        return True
