"""Outline agent using Gemini Flash."""

import json
import logging
from typing import Any, Dict

from app.agents.base import BaseAgent
from app.models.outline import OutlineNode
from app.schemas.agents import OutlineInput, OutlineOutput

logger = logging.getLogger(__name__)


class OutlineAgent(BaseAgent):
    """Agent for generating hierarchical outline."""

    MODEL = "google/gemini-2.0-flash-exp:free"

    def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generate outline from topic and documents."""
        input_data = OutlineInput(**payload)

        # Build prompt
        doc_list = "\n".join([f"- {d['title']} ({d.get('author', 'Unknown')}, {d.get('year', 'N/A')})"
                              for d in input_data.documents])

        prompt = f"""Create a hierarchical outline for a 30-40 page technical report on: {input_data.topic}

Available sources:
{doc_list}

Requirements:
1. Create a structured outline with sections and subsections
2. Each node must specify:
   - Unique node_id (e.g., "1", "1.1", "1.1.1")
   - parent_id (null for top-level sections)
   - title (descriptive section title)
   - goal (what this section aims to accomplish)
   - allowed_topics (list of topics to include)
   - excluded_topics (list of topics to avoid)
   - retrieval_queries (list of search queries to find relevant content)
3. Do NOT make factual claims; only structure the report
4. Return valid JSON: {{"nodes": [...]}}
"""

        messages = [{"role": "user", "content": prompt}]
        response = self.llm.chat_completion(
            model=self.MODEL,
            messages=messages,
            temperature=0.3,
            max_tokens=4000,
            json_mode=True,
        )

        # Parse JSON
        result = json.loads(response)
        output = OutlineOutput(**result)

        # Persist nodes
        for node in output.nodes:
            outline_node = OutlineNode(
                run_id=payload["run_id"],
                node_id=node.node_id,
                parent_id=node.parent_id,
                title=node.title,
                goal=node.goal,
                allowed_topics=node.allowed_topics,
                excluded_topics=node.excluded_topics,
                retrieval_queries=node.retrieval_queries,
                status="pending",
            )
            self.db.add(outline_node)

        self.db.commit()

        return {"nodes": [n.dict() for n in output.nodes]}

    def _validate(self, result: Dict[str, Any]) -> bool:
        """Validate outline has nodes."""
        return "nodes" in result and len(result["nodes"]) > 0
