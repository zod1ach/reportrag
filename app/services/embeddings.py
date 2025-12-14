"""Embedding service using Ollama."""

import logging
from typing import List

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings using Ollama."""

    def __init__(self):
        """Initialize the embedding service."""
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL
        self.embed_dim = settings.EMBED_DIM

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors

        Raises:
            httpx.HTTPError: On API errors
            ValueError: On dimension mismatch
        """
        embeddings = []

        with httpx.Client(timeout=60.0) as client:
            for idx, text in enumerate(texts):
                logger.info(f"Generating embedding {idx + 1}/{len(texts)}")

                payload = {
                    "model": self.model,
                    "prompt": text,
                }

                response = client.post(
                    f"{self.base_url}/api/embeddings",
                    json=payload,
                )

                response.raise_for_status()
                result = response.json()

                embedding = result["embedding"]

                # Validate dimension
                if len(embedding) != self.embed_dim:
                    raise ValueError(
                        f"Embedding dimension mismatch: expected {self.embed_dim}, got {len(embedding)}"
                    )

                embeddings.append(embedding)

        return embeddings

    def accept_client_embeddings(
        self, chunk_count: int, embeddings: List[List[float]]
    ) -> None:
        """
        Validate client-provided embeddings.

        Args:
            chunk_count: Expected number of embeddings
            embeddings: Client-provided embedding vectors

        Raises:
            ValueError: If validation fails
        """
        if len(embeddings) != chunk_count:
            raise ValueError(
                f"Embedding count mismatch: expected {chunk_count}, got {len(embeddings)}"
            )

        for idx, embedding in enumerate(embeddings):
            if len(embedding) != self.embed_dim:
                raise ValueError(
                    f"Embedding {idx} dimension mismatch: expected {self.embed_dim}, got {len(embedding)}"
                )

        logger.info(f"Validated {len(embeddings)} client-provided embeddings")
