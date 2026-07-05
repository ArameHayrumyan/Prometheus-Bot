"""initial schema (all tables + pgvector)

Revision ID: 0001
Revises:
Create Date: 2026-07-05
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "degree_levels",
        sa.Column("code", sa.String(20), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False),
    )
    op.create_table(
        "channels",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("degree_level_code", sa.String(20), sa.ForeignKey("degree_levels.code"), unique=True),
        sa.Column("tg_channel_id", sa.BigInteger, nullable=False),
    )
    op.create_table(
        "field_taxonomy",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("keywords", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
    )
    op.create_table(
        "users",
        sa.Column("tg_id", sa.BigInteger, primary_key=True),
        sa.Column("language", sa.String(5), nullable=False, server_default="en"),
        sa.Column("degree_level_code", sa.String(20), sa.ForeignKey("degree_levels.code"), nullable=True),
        sa.Column("fields", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("gpa", sa.Float, nullable=True),
        sa.Column("english_test", sa.String(10), nullable=True),
        sa.Column("english_score", sa.Float, nullable=True),
        sa.Column("english_expiry", sa.Date, nullable=True),
        sa.Column("onboarded", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("category", sa.String(50), nullable=False, server_default="general"),
        sa.Column("country", sa.String(80), nullable=True),
        sa.Column("needs_js", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta", postgresql.JSONB(), nullable=False, server_default="{}"),
    )
    op.create_table(
        "source_reputation",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("domain", sa.String(255), unique=True, nullable=False),
        sa.Column("score", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("approved_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "opportunities",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("sources.id"), nullable=True),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("raw_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("org", sa.Text, nullable=True),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("opportunity_type", sa.String(20), nullable=False),
        sa.Column("degree_levels", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("fields", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("country", sa.String(120), nullable=True),
        sa.Column("deadline", sa.Date, nullable=True),
        sa.Column("duration_days", sa.Integer, nullable=True),
        sa.Column("funding_tier", sa.String(30), nullable=False, server_default="UNKNOWN"),
        sa.Column("armenian_eligibility", sa.String(15), nullable=False, server_default="UNCERTAIN"),
        sa.Column("english_req_test", sa.String(10), nullable=True),
        sa.Column("english_req_score", sa.Float, nullable=True),
        sa.Column("spots", sa.Integer, nullable=True),
        sa.Column("acceptance_rate", sa.Float, nullable=True),
        sa.Column("requirements", sa.Text, nullable=False, server_default=""),
        sa.Column("apply_url", sa.Text, nullable=False, server_default=""),
        sa.Column("legitimacy_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("chance_percent", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING_REVIEW"),
        sa.Column("discard_reason", sa.Text, nullable=True),
        sa.Column("ai_verdict", postgresql.JSONB(), nullable=True),
        sa.Column("edited_text", sa.Text, nullable=True),
        sa.Column("image_file_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_opportunities_status", "opportunities", ["status"])
    op.create_table(
        "opportunity_embeddings",
        sa.Column(
            "opportunity_id",
            sa.Integer,
            sa.ForeignKey("opportunities.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("embedding", Vector(384)),
    )
    op.create_table(
        "channel_posts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("opportunity_id", sa.Integer, sa.ForeignKey("opportunities.id", ondelete="CASCADE")),
        sa.Column("tg_channel_id", sa.BigInteger, nullable=False),
        sa.Column("message_id", sa.BigInteger, nullable=False),
        sa.UniqueConstraint("tg_channel_id", "message_id"),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_tg_id", sa.BigInteger, sa.ForeignKey("users.tg_id", ondelete="CASCADE")),
        sa.Column("doc_type", sa.String(20), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("extracted_text", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "saved_filters",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_tg_id", sa.BigInteger, sa.ForeignKey("users.tg_id", ondelete="CASCADE")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("filters", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("notify", sa.Boolean, nullable=False, server_default="true"),
    )
    op.create_table(
        "analysis_results",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_tg_id", sa.BigInteger, sa.ForeignKey("users.tg_id", ondelete="CASCADE")),
        sa.Column("opportunity_id", sa.Integer, sa.ForeignKey("opportunities.id", ondelete="CASCADE")),
        sa.Column("result", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "admin_actions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("admin_tg_id", sa.BigInteger, nullable=False),
        sa.Column("opportunity_id", sa.Integer, sa.ForeignKey("opportunities.id"), nullable=True),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    for table in (
        "app_settings", "admin_actions", "analysis_results", "saved_filters",
        "documents", "channel_posts", "opportunity_embeddings", "opportunities",
        "source_reputation", "sources", "users", "field_taxonomy", "channels",
        "degree_levels",
    ):
        op.drop_table(table)
