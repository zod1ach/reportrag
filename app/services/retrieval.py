"""Hybrid FTS + vector retrieval with MMR diversification."""

import logging
from typing import List, Tuple
from uuid import UUID

import numpy as np
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models.document import Chunk
from app.models.outline import RetrievalResult
from app.services.embeddings import EmbeddingService

logger = logging.getLogger(__name__)


class HybridRetrieval:
    """Hybrid retrieval combining FTS and vector search with MMR."""

    def __init__(self, db: Session, embedding_service: EmbeddingService):
        """Initialize hybrid retrieval."""
        self.db = db
        self.embedding_service = embedding_service
        self.fts_shortlist_size = settings.FTS_SHORTLIST_SIZE
        self.vector_rerank_size = settings.VECTOR_RERANK_SIZE
        self.mmr_lambda = settings.MMR_LAMBDA
        self.max_chunks_per_doc = settings.MAX_CHUNKS_PER_DOC

    def retrieve(
        self,
        query_text: str,
        negative_terms: List[str],
        top_k: int,
        run_id: UUID,
        node_id: str,
    ) -> int:
        """
        Perform hybrid retrieval and store results.

        Args:
            query_text: Search query text
            negative_terms: Terms to exclude
            top_k: Number of results to return
            run_id: Run identifier
            node_id: Node identifier

        Returns:
            Number of chunks retrieved
        """
        logger.info(f"Starting hybrid retrieval for node {node_id}")

        # Step 1: FTS shortlist
        fts_results = self._fts_search(query_text, negative_terms)
        logger.info(f"FTS shortlist: {len(fts_results)} chunks")

        if not fts_results:
            logger.warning("No FTS results found")
            return 0

        # Step 2: Vector rerank within shortlist
        vector_results = self._vector_rerank(fts_results, query_text)
        logger.info(f"Vector rerank: {len(vector_results)} chunks")

        # Step 3: Score normalization
        normalized_results = self._normalize_scores(vector_results)

        # Step 4: MMR diversification
        mmr_results = self._mmr_diversification(normalized_results, top_k)
        logger.info(f"MMR diversification: {len(mmr_results)} chunks")

        # Step 5: Per-document cap
        final_results = self._apply_doc_cap(mmr_results)
        logger.info(f"After doc cap: {len(final_results)} chunks")

        # Step 6: Persist results
        self._persist_results(final_results, run_id, node_id)

        return len(final_results)

    def _fts_search(
        self, query_text: str, negative_terms: List[str]
    ) -> List[Tuple[int, float, str, List[float]]]:
        """
        Perform FTS search with negative terms.

        Returns:
            List of (chunk_pk, fts_score, text, embedding)
        """
        # Build query with negative terms
        query_parts = [query_text]
        for term in negative_terms:
            query_parts.append(f"!{term}")
        query_string = " ".join(query_parts)

        # Execute FTS query
        sql = text(
            """
            SELECT chunk_pk, ts_rank_cd(tsv, query) as fts_score, text, embedding
            FROM chunks, websearch_to_tsquery(:query) query
            WHERE tsv @@ query
            ORDER BY fts_score DESC
            LIMIT :limit
            """
        )

        result = self.db.execute(
            sql,
            {"query": query_string, "limit": self.fts_shortlist_size},
        )

        return [(row[0], row[1], row[2], row[3]) for row in result]

    def _vector_rerank(
        self, fts_results: List[Tuple[int, float, str, List[float]]], query_text: str
    ) -> List[Tuple[int, float, float, str, List[float]]]:
        """
        Rerank FTS results using vector similarity.

        Returns:
            List of (chunk_pk, fts_score, vec_score, text, embedding)
        """
        # Generate query embedding
        query_embedding = self.embedding_service.embed_texts([query_text])[0]
        query_vec = np.array(query_embedding)

        # Compute cosine similarities
        results_with_vec_score = []
        for chunk_pk, fts_score, text, embedding in fts_results:
            if embedding is None:
                logger.warning(f"Chunk {chunk_pk} missing embedding, skipping")
                continue

            chunk_vec = np.array(embedding)
            # Cosine similarity: 1 - cosine distance
            cosine_sim = np.dot(query_vec, chunk_vec) / (
                np.linalg.norm(query_vec) * np.linalg.norm(chunk_vec) + 1e-10
            )
            vec_score = float(cosine_sim)

            results_with_vec_score.append((chunk_pk, fts_score, vec_score, text, embedding))

        # Sort by vector score and take top K
        results_with_vec_score.sort(key=lambda x: x[2], reverse=True)
        return results_with_vec_score[: self.vector_rerank_size]

    def _normalize_scores(
        self, results: List[Tuple[int, float, float, str, List[float]]]
    ) -> List[Tuple[int, float, float, float, str, List[float]]]:
        """
        Normalize FTS and vector scores to [0, 1].

        Returns:
            List of (chunk_pk, fts_score, vec_score, combined_score, text, embedding)
        """
        if not results:
            return []

        # Extract scores
        fts_scores = [r[1] for r in results]
        vec_scores = [r[2] for r in results]

        # Min-max normalization
        fts_min, fts_max = min(fts_scores), max(fts_scores)
        vec_min, vec_max = min(vec_scores), max(vec_scores)

        fts_range = fts_max - fts_min if fts_max > fts_min else 1.0
        vec_range = vec_max - vec_min if vec_max > vec_min else 1.0

        normalized_results = []
        for chunk_pk, fts_score, vec_score, text, embedding in results:
            fts_norm = (fts_score - fts_min) / fts_range
            vec_norm = (vec_score - vec_min) / vec_range
            combined_score = 0.5 * fts_norm + 0.5 * vec_norm

            normalized_results.append(
                (chunk_pk, fts_score, vec_score, combined_score, text, embedding)
            )

        return normalized_results

    def _mmr_diversification(
        self, results: List[Tuple[int, float, float, float, str, List[float]]], top_k: int
    ) -> List[Tuple[int, float, float, float, int]]:
        """
        Apply MMR diversification.

        Returns:
            List of (chunk_pk, fts_score, vec_score, combined_score, rank)
        """
        if not results or top_k <= 0:
            return []

        selected = []
        remaining = list(results)
        selected_embeddings = []

        for rank in range(min(top_k, len(remaining))):
            if not remaining:
                break

            # Calculate MMR scores
            mmr_scores = []
            for i, (chunk_pk, fts_score, vec_score, combined_score, text, embedding) in enumerate(remaining):
                relevance = combined_score

                # Diversity: max similarity to already selected
                if selected_embeddings:
                    similarities = []
                    chunk_vec = np.array(embedding)
                    for sel_emb in selected_embeddings:
                        sel_vec = np.array(sel_emb)
                        sim = np.dot(chunk_vec, sel_vec) / (
                            np.linalg.norm(chunk_vec) * np.linalg.norm(sel_vec) + 1e-10
                        )
                        similarities.append(sim)
                    max_similarity = max(similarities)
                else:
                    max_similarity = 0.0

                mmr_score = self.mmr_lambda * relevance - (1 - self.mmr_lambda) * max_similarity
                mmr_scores.append((i, mmr_score))

            # Select chunk with highest MMR score
            best_idx, best_mmr = max(mmr_scores, key=lambda x: x[1])
            selected_chunk = remaining.pop(best_idx)

            chunk_pk, fts_score, vec_score, combined_score, text, embedding = selected_chunk
            selected.append((chunk_pk, fts_score, vec_score, combined_score, rank))
            selected_embeddings.append(embedding)

        return selected

    def _apply_doc_cap(
        self, results: List[Tuple[int, float, float, float, int]]
    ) -> List[Tuple[int, float, float, float, int]]:
        """
        Apply per-document cap (max N chunks per document).

        Returns:
            List of (chunk_pk, fts_score, vec_score, combined_score, rank)
        """
        # Get document IDs for each chunk
        chunk_pks = [r[0] for r in results]
        chunks = self.db.query(Chunk.chunk_pk, Chunk.doc_id).filter(Chunk.chunk_pk.in_(chunk_pks)).all()
        chunk_to_doc = {c.chunk_pk: c.doc_id for c in chunks}

        # Track counts per document
        doc_counts = {}
        final_results = []

        for chunk_pk, fts_score, vec_score, combined_score, rank in results:
            doc_id = chunk_to_doc.get(chunk_pk)
            if doc_id is None:
                continue

            count = doc_counts.get(doc_id, 0)
            if count < self.max_chunks_per_doc:
                final_results.append((chunk_pk, fts_score, vec_score, combined_score, rank))
                doc_counts[doc_id] = count + 1

        return final_results

    def _persist_results(
        self,
        results: List[Tuple[int, float, float, float, int]],
        run_id: UUID,
        node_id: str,
    ) -> None:
        """Persist retrieval results to database."""
        for chunk_pk, fts_score, vec_score, combined_score, rank in results:
            result = RetrievalResult(
                run_id=run_id,
                node_id=node_id,
                chunk_pk=chunk_pk,
                fts_score=fts_score,
                vec_score=vec_score,
                score=combined_score,
                rank=rank,
            )
            self.db.add(result)

        self.db.commit()
        logger.info(f"Persisted {len(results)} retrieval results for node {node_id}")
