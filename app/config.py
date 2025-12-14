"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str

    # Embeddings
    EMBED_DIM: int = 768
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "nomic-embed-text"  # or mxbai-embed-large

    # OpenRouter
    OPENROUTER_API_KEY: str
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    SITE_URL: str = ""
    SITE_NAME: str = "Report-RAG"

    # Retrieval
    FTS_SHORTLIST_SIZE: int = 200
    VECTOR_RERANK_SIZE: int = 50
    MMR_LAMBDA: float = 0.7
    MAX_CHUNKS_PER_DOC: int = 3

    # Chunking
    CHUNK_TARGET_SIZE: int = 8000
    CHUNK_OVERLAP_PERCENT: float = 0.12

    # Worker
    WORKER_POLL_INTERVAL: int = 5
    MAX_JOB_RETRIES: int = 3

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


# Global settings instance
settings = Settings()
