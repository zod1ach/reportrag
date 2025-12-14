"""Retrieval agent (pure code, no LLM)."""

import logging
from typing import Any, Dict

from app.agents.base import BaseAgent
from app.models.outline import OutlineNode
from app.services.embeddings import EmbeddingService
from app.services.retrieval import HybridRetrieval

logger = logging.getLogger(__name__)


class RetrievalAgent(BaseAgent):
    """Agent for hybrid retrieval (FTS + vector)."""

    def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Perform hybrid retrieval for a node."""
        run_id = payload["run_id"]
        node_id = payload["node_id"]

        # Load node from DB
        node = self.db.query(OutlineNode).filter(
            OutlineNode.run_id == run_id,
            OutlineNode.node_id == node_id,
        ).first()

        if not node:
            raise ValueError(f"Node {node_id} not found")

        # Build query text
        query_parts = []
        query_parts.extend(node.retrieval_queries or [])
        query_parts.extend(node.allowed_topics or [])
        query_parts.append(node.title)
        query_text = " ".join(query_parts)

        # Negative terms
        negative_terms = node.excluded_topics or []

        # Perform retrieval
        embedding_service = EmbeddingService()
        retrieval = HybridRetrieval(self.db, embedding_service)
        chunk_count = retrieval.retrieve(
            query_text=query_text,
            negative_terms=negative_terms,
            top_k=50,
            run_id=run_id,
            node_id=node_id,
        )

        # Update node status
        node.status = "retrieved"
        self.db.commit()

        return {"chunk_count": chunk_count}
