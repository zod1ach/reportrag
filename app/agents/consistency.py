"""Global consistency agent."""

import json
import logging
from typing import Any, Dict

from app.agents.base import BaseAgent
from app.models.claim import Draft
from app.models.memory import GlobalMemory
from app.models.outline import OutlineNode

logger = logging.getLogger(__name__)


class GlobalConsistencyAgent(BaseAgent):
    """Agent for checking global consistency."""

    MODEL = "google/gemini-2.0-flash-exp:free"  # Gemini supports JSON mode (Nova doesn't)

    def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Check consistency across report."""
        run_id = payload["run_id"]

        # Load all drafts
        drafts = self.db.query(Draft).filter(Draft.run_id == run_id).all()
        draft_map = {d.node_id: d.latex for d in drafts}

        # Load memory
        memory = self.db.query(GlobalMemory).filter(
            GlobalMemory.run_id == run_id
        ).first()

        # Build summary
        drafts_summary = "\n\n".join([
            f"Node {nid}:\n{latex[:500]}..."
            for nid, latex in draft_map.items()
        ])

        memory_str = json.dumps({
            "definitions": memory.definitions if memory else {},
            "notation": memory.notation if memory else {},
        }, indent=2)

        prompt = f"""Review the full report for consistency issues.

Memory:
{memory_str}

Drafts:
{drafts_summary}

Identify:
1. Inconsistent terminology
2. Unresolved conflicts
3. Missing citations

Return JSON patch plan: {{"terminology_changes": {{}}, "conflicts_to_mention": [], "nodes_needing_rewrite": [], "reason": {{}}}}
"""

        messages = [{"role": "user", "content": prompt}]
        response = self.llm.chat_completion(
            model=self.MODEL,
            messages=messages,
            temperature=0.1,
            max_tokens=2000,
            json_mode=True,
        )

        result = json.loads(response)

        return {"patch_plan": result}
