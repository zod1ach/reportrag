"""Embedding service using HuggingFace sentence-transformers."""

import logging
from typing import List

from app.config import settings

logger = logging.getLogger(__name__)

# Lazy load to avoid import errors if not installed
_model = None


def get_model():
    """Lazy load the sentence transformer model."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
            _model = SentenceTransformer(settings.EMBEDDING_MODEL)
            logger.info("Embedding model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise
    return _model


class EmbeddingService:
    """Service for generating text embeddings using HuggingFace."""

    def __init__(self):
        """Initialize the embedding service."""
        self.model_name = settings.EMBEDDING_MODEL
        self.embed_dim = settings.EMBED_DIM

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors

        Raises:
            ValueError: On dimension mismatch
        """
        if not texts:
            return []

        try:
            model = get_model()
            logger.info(f"Generating embeddings for {len(texts)} texts")

            # Generate embeddings
            embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)

            # Convert to list of lists
            embeddings_list = [emb.tolist() for emb in embeddings]

            # Validate dimensions
            for idx, embedding in enumerate(embeddings_list):
                if len(embedding) != self.embed_dim:
                    raise ValueError(
                        f"Embedding dimension mismatch: expected {self.embed_dim}, got {len(embedding)}"
                    )

            logger.info(f"Successfully generated {len(embeddings_list)} embeddings")
            return embeddings_list

        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise

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
