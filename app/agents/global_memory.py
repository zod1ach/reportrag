"""Global memory agent."""

import json
import logging
from typing import Any, Dict

from app.agents.base import BaseAgent
from app.models.memory import GlobalMemory
from app.models.claim import Claim

logger = logging.getLogger(__name__)


class GlobalMemoryAgent(BaseAgent):
    """Agent for managing global memory."""

    MODEL = "google/gemini-2.0-flash-exp:free"

    def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Update global memory from new claims."""
        run_id = payload["run_id"]
        node_id = payload.get("node_id")

        # Load new claims
        query = self.db.query(Claim).filter(Claim.run_id == run_id)
        if node_id:
            query = query.filter(Claim.node_id == node_id)
        new_claims = query.all()

        # Load current memory
        memory = self.db.query(GlobalMemory).filter(
            GlobalMemory.run_id == run_id
        ).first()

        current_memory = {
            "definitions": memory.definitions if memory else {},
            "notation": memory.notation if memory else {},
            "entities": memory.entities if memory else [],
            "assumptions": memory.assumptions if memory else [],
            "results": memory.results if memory else [],
        }

        # Build claims summary
        claims_str = "\n".join([f"- {c.claim}" for c in new_claims])

        prompt = f"""Extract and merge definitions, notation, entities, assumptions, results from new claims.

Current memory:
{json.dumps(current_memory, indent=2)}

New claims:
{claims_str}

Return JSON: {{"definitions": {{}}, "notation": {{}}, "entities": [], "assumptions": [], "results": []}}
Deduplicate and standardize with existing memory.
"""

        messages = [{"role": "user", "content": prompt}]
        response = self.llm.chat_completion(
            model=self.MODEL,
            messages=messages,
            temperature=0.2,
            max_tokens=2000,
            json_mode=True,
        )

        result = json.loads(response)

        # Upsert memory
        if memory:
            memory.definitions = result["definitions"]
            memory.notation = result["notation"]
            memory.entities = result["entities"]
            memory.assumptions = result["assumptions"]
            memory.results = result["results"]
        else:
            memory = GlobalMemory(
                run_id=run_id,
                definitions=result["definitions"],
                notation=result["notation"],
                entities=result["entities"],
                assumptions=result["assumptions"],
                results=result["results"],
            )
            self.db.add(memory)

        self.db.commit()

        return {"memory": result}
