"""AI enrichment column + saved_opportunities (reminders & application tracker)

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("opportunities", sa.Column("enrichment", postgresql.JSONB(), nullable=True))
    op.create_table(
        "saved_opportunities",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_tg_id", sa.BigInteger,
                  sa.ForeignKey("users.tg_id", ondelete="CASCADE"), nullable=False),
        sa.Column("opportunity_id", sa.Integer,
                  sa.ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("saved_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("remind", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("reminders_sent", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.String(20), nullable=True),
        sa.Column("outcome_asked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_tg_id", "opportunity_id"),
    )


def downgrade() -> None:
    op.drop_table("saved_opportunities")
    op.drop_column("opportunities", "enrichment")
