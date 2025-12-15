"""Evidence agent with validation."""

import json
import logging
from typing import Any, Dict, List

from app.agents.base import BaseAgent
from app.models.evidence import EvidenceItem
from app.models.document import Chunk
from app.models.outline import RetrievalResult
from app.schemas.agents import EvidenceOutput
from app.services.validators import generate_corrective_prompt, validate_evidence_quote

logger = logging.getLogger(__name__)


class EvidenceAgent(BaseAgent):
    """Agent for extracting validated evidence."""

    MODEL = "amazon/nova-2-lite-v1:free"  # Switched from Gemini to spread rate limit load

    def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extract evidence from retrieved chunks."""
        run_id = payload["run_id"]
        node_id = payload["node_id"]

        # Load retrieved chunks
        results = self.db.query(RetrievalResult).filter(
            RetrievalResult.run_id == run_id,
            RetrievalResult.node_id == node_id,
        ).order_by(RetrievalResult.rank).limit(10).all()

        chunk_pks = [r.chunk_pk for r in results]
        chunks = self.db.query(Chunk).filter(Chunk.chunk_pk.in_(chunk_pks)).all()
        chunk_map = {c.chunk_pk: c for c in chunks}

        chunk_texts = [(r.chunk_pk, chunk_map[r.chunk_pk].text) for r in results if r.chunk_pk in chunk_map]

        # Build prompt
        chunks_str = "\n\n---\n\n".join([f"Chunk {pk}:\n{text[:1500]}" for pk, text in chunk_texts])

        prompt = f"""Extract key evidence from the following text chunks.

Requirements:
1. Return ONLY verbatim quotes with exact character offsets
2. Do NOT paraphrase; quotes must be exact substrings
3. Each evidence item must include: ev_id, chunk_pk, quote, start_in_chunk, end_in_chunk, tag

Chunks:
{chunks_str}

Return JSON: {{"evidence_items": [...]}}
"""

        messages = [{"role": "user", "content": prompt}]
        response = self.llm.chat_completion(
            model=self.MODEL,
            messages=messages,
            temperature=0.2,
            max_tokens=3000,
            json_mode=True,
        )

        result = json.loads(response)
        output = EvidenceOutput(**result)

        # Validate each evidence item
        validated_items = []
        for item in output.evidence_items:
            chunk_text = chunk_map[item.chunk_pk].text
            if validate_evidence_quote(chunk_text, item.quote, item.start_in_chunk, item.end_in_chunk):
                validated_items.append(item)
            else:
                logger.warning(f"Evidence item {item.ev_id} failed validation, skipping")

        if not validated_items:
            raise ValueError("No valid evidence items found")

        # Persist
        for item in validated_items:
            evidence = EvidenceItem(
                run_id=run_id,
                node_id=node_id,
                ev_id=item.ev_id,
                chunk_pk=item.chunk_pk,
                quote=item.quote,
                start_in_chunk=item.start_in_chunk,
                end_in_chunk=item.end_in_chunk,
                tag=item.tag,
                validated=True,
            )
            self.db.add(evidence)

        self.db.commit()

        return {
            "evidence_items": [i.dict() for i in validated_items],
            "evidence_count": len(validated_items)
        }

    def _validate(self, result: Dict[str, Any]) -> bool:
        """Validate we have evidence items."""
        return "evidence_items" in result and len(result["evidence_items"]) > 0
