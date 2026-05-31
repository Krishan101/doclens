"""Add hybrid search support — tsvector column and GIN index

Revision ID: 002
Revises: 001
Create Date: 2026-05-30
"""
from alembic import op

revision = "002"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add generated tsvector column for BM25 full-text search
    op.execute("""
        ALTER TABLE chunks
        ADD COLUMN IF NOT EXISTS content_tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
    """)
    # GIN index for fast full-text search
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_chunks_tsv
        ON chunks USING GIN(content_tsv)
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_chunks_tsv")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS content_tsv")
