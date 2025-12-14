"""Initial schema with pgvector

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Check if tables already exist and skip if so
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "documents" in existing_tables:
        # Tables already exist, skip migration
        return

    # Create documents table
    op.create_table(
        "documents",
        sa.Column("doc_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("author", sa.Text),
        sa.Column("year", sa.Integer),
        sa.Column("content_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # Create chunks table
    op.create_table(
        "chunks",
        sa.Column("chunk_pk", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("doc_id", UUID(as_uuid=True), sa.ForeignKey("documents.doc_id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_id", sa.Text, nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("tsv", TSVECTOR),
        sa.Column("embedding", Vector(384)),
        sa.Column("char_start", sa.Integer),
        sa.Column("char_end", sa.Integer),
        sa.Column("text_hash", sa.String(64), nullable=False),
        sa.Column("token_estimate", sa.Integer),
        sa.UniqueConstraint("doc_id", "chunk_index"),
    )
    op.create_index("idx_chunks_doc_id", "chunks", ["doc_id"])
    op.create_index("idx_chunks_gin_tsv", "chunks", ["tsv"], postgresql_using="gin")
    # Note: ivfflat index requires data to train - create it manually after uploading documents:
    # CREATE INDEX idx_chunks_ivfflat_embedding ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
    op.create_index("idx_chunks_text_hash", "chunks", ["text_hash"])

    # Create runs table
    op.create_table(
        "runs",
        sa.Column("run_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("topic", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("model_config", JSONB),
    )

    # Create outline_nodes table
    op.create_table(
        "outline_nodes",
        sa.Column("node_pk", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", sa.Text, nullable=False),
        sa.Column("parent_id", sa.Text),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("goal", sa.Text),
        sa.Column("allowed_topics", JSONB),
        sa.Column("excluded_topics", JSONB),
        sa.Column("retrieval_queries", JSONB),
        sa.Column("status", sa.Text, nullable=False),
        sa.UniqueConstraint("run_id", "node_id"),
    )

    # Create retrieval_results table
    op.create_table(
        "retrieval_results",
        sa.Column("result_pk", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", sa.Text, nullable=False),
        sa.Column("chunk_pk", sa.Integer, sa.ForeignKey("chunks.chunk_pk")),
        sa.Column("fts_score", sa.Float),
        sa.Column("vec_score", sa.Float),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("rank", sa.Integer, nullable=False),
    )
    op.create_index("idx_retrieval_run_node", "retrieval_results", ["run_id", "node_id"])

    # Create evidence_items table
    op.create_table(
        "evidence_items",
        sa.Column("ev_pk", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", sa.Text, nullable=False),
        sa.Column("ev_id", sa.Text, nullable=False),
        sa.Column("chunk_pk", sa.Integer, sa.ForeignKey("chunks.chunk_pk")),
        sa.Column("quote", sa.Text, nullable=False),
        sa.Column("start_in_chunk", sa.Integer, nullable=False),
        sa.Column("end_in_chunk", sa.Integer, nullable=False),
        sa.Column("tag", sa.Text),
        sa.Column("validated", sa.Boolean, default=False),
        sa.UniqueConstraint("run_id", "node_id", "ev_id"),
    )

    # Create claims table
    op.create_table(
        "claims",
        sa.Column("claim_pk", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", sa.Text, nullable=False),
        sa.Column("claim_id", sa.Text, nullable=False),
        sa.Column("claim", sa.Text, nullable=False),
        sa.Column("type", sa.Text),
        sa.Column("strength", sa.Text),
        sa.Column("conditions", sa.Text),
        sa.Column("evidence_ev_ids", JSONB),
        sa.Column("conflicts", JSONB),
        sa.UniqueConstraint("run_id", "node_id", "claim_id"),
    )

    # Create drafts table
    op.create_table(
        "drafts",
        sa.Column("draft_pk", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", sa.Text, nullable=False, unique=True),
        sa.Column("latex", sa.Text, nullable=False),
        sa.Column("citations", JSONB),
        sa.Column("quality_flags", JSONB),
    )

    # Create global_memory table
    op.create_table(
        "global_memory",
        sa.Column("memory_pk", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("definitions", JSONB),
        sa.Column("notation", JSONB),
        sa.Column("entities", JSONB),
        sa.Column("assumptions", JSONB),
        sa.Column("results", JSONB),
    )

    # Create jobs table
    op.create_table(
        "jobs",
        sa.Column("job_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", sa.Text),
        sa.Column("agent", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("payload", JSONB),
        sa.Column("retries", sa.Integer, default=0),
        sa.Column("last_error", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("idx_jobs_status", "jobs", ["status"])
    op.create_index("idx_jobs_run_id", "jobs", ["run_id"])


def downgrade() -> None:
    op.drop_table("jobs")
    op.drop_table("global_memory")
    op.drop_table("drafts")
    op.drop_table("claims")
    op.drop_table("evidence_items")
    op.drop_table("retrieval_results")
    op.drop_table("outline_nodes")
    op.drop_table("runs")
    op.drop_table("chunks")
    op.drop_table("documents")
    op.execute("DROP EXTENSION IF EXISTS vector")
