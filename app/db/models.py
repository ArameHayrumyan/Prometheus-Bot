"""Complete SQLAlchemy schema. Enums are stored as plain strings (see app.constants)."""
from datetime import date, datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB as JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DegreeLevel(Base):
    __tablename__ = "degree_levels"
    code: Mapped[str] = mapped_column(String(20), primary_key=True)  # undergrad/masters/phd
    name: Mapped[str] = mapped_column(String(50))


class Channel(Base):
    """A posting target: a channel, or a forum-supergroup topic (thread_id).

    audience: 'student' (the three degree channels), 'youth' (the youth
    channel), or 'free' (admin-added, never auto-selected)."""
    __tablename__ = "channels"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    degree_level_code: Mapped[str | None] = mapped_column(
        ForeignKey("degree_levels.code"), unique=True, nullable=True)
    tg_channel_id: Mapped[int] = mapped_column(BigInteger)
    thread_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str] = mapped_column(String(100), default="")
    audience: Mapped[str] = mapped_column(String(10), default="student")


class FieldTaxonomy(Base):
    __tablename__ = "field_taxonomy"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    keywords: Mapped[list] = mapped_column(JSON, default=list)  # lowercase match terms
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class User(Base):
    __tablename__ = "users"
    tg_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    language: Mapped[str] = mapped_column(String(5), default="en")
    degree_level_code: Mapped[str | None] = mapped_column(ForeignKey("degree_levels.code"), nullable=True)
    fields: Mapped[list] = mapped_column(JSON, default=list)  # FieldTaxonomy names
    gpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    english_test: Mapped[str | None] = mapped_column(String(10), nullable=True)  # TOEFL/IELTS
    english_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    english_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    documents: Mapped[list["Document"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(20))  # SourceType
    url: Mapped[str] = mapped_column(Text)  # url / feed url / mailbox marker / subreddit url
    category: Mapped[str] = mapped_column(String(50), default="general")
    country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    needs_js: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class SourceReputation(Base):
    __tablename__ = "source_reputation"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    domain: Mapped[str] = mapped_column(String(255), unique=True)
    score: Mapped[float] = mapped_column(Float, default=0.5)  # 0..1
    approved_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Opportunity(Base):
    __tablename__ = "opportunities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
    url: Mapped[str] = mapped_column(Text)
    raw_hash: Mapped[str] = mapped_column(String(64), unique=True)  # dedupe key
    title: Mapped[str] = mapped_column(Text)
    org: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    opportunity_type: Mapped[str] = mapped_column(String(20))  # OpportunityType
    audience: Mapped[str] = mapped_column(String(10), default="student")  # student/youth
    degree_levels: Mapped[list] = mapped_column(JSON, default=list)  # ["masters", "phd"]
    fields: Mapped[list] = mapped_column(JSON, default=list)  # taxonomy names matched
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    funding_tier: Mapped[str] = mapped_column(String(30), default="UNKNOWN")  # FundingTier
    armenian_eligibility: Mapped[str] = mapped_column(String(15), default="UNCERTAIN")  # Eligibility
    english_req_test: Mapped[str | None] = mapped_column(String(10), nullable=True)
    english_req_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    spots: Mapped[int | None] = mapped_column(Integer, nullable=True)
    acceptance_rate: Mapped[float | None] = mapped_column(Float, nullable=True)  # percent
    requirements: Mapped[str] = mapped_column(Text, default="")
    apply_url: Mapped[str] = mapped_column(Text, default="")
    legitimacy_score: Mapped[int] = mapped_column(Integer, default=0)  # 0..100
    chance_percent: Mapped[int] = mapped_column(Integer, default=0)  # 0..100 (generic)
    status: Mapped[str] = mapped_column(String(20), default="PENDING_REVIEW", index=True)
    discard_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_verdict: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    edited_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # admin free-edit body
    enrichment: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # AI tldr/competitiveness/req bullets
    image_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OpportunityEmbedding(Base):
    __tablename__ = "opportunity_embeddings"
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"), primary_key=True
    )
    embedding = mapped_column(Vector(384))


class ChannelPost(Base):
    __tablename__ = "channel_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"))
    tg_channel_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int] = mapped_column(BigInteger)
    __table_args__ = (UniqueConstraint("tg_channel_id", "message_id"),)


class SavedOpportunity(Base):
    """A user's saved item: drives deadline reminders and the application tracker."""
    __tablename__ = "saved_opportunities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_tg_id: Mapped[int] = mapped_column(ForeignKey("users.tg_id", ondelete="CASCADE"))
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"))
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    remind: Mapped[bool] = mapped_column(Boolean, default=True)
    reminders_sent: Mapped[list] = mapped_column(JSON, default=list)  # e.g. [7, 3]
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(20), nullable=True)  # accepted/rejected
    outcome_asked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("user_tg_id", "opportunity_id"),)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_tg_id: Mapped[int] = mapped_column(ForeignKey("users.tg_id", ondelete="CASCADE"))
    doc_type: Mapped[str] = mapped_column(String(20))  # resume / cover / note
    filename: Mapped[str] = mapped_column(String(255))
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="documents")


class SavedFilter(Base):
    __tablename__ = "saved_filters"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_tg_id: Mapped[int] = mapped_column(ForeignKey("users.tg_id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    notify: Mapped[bool] = mapped_column(Boolean, default=True)


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_tg_id: Mapped[int] = mapped_column(ForeignKey("users.tg_id", ondelete="CASCADE"))
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"))
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AdminAction(Base):
    __tablename__ = "admin_actions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_tg_id: Mapped[int] = mapped_column(BigInteger)
    opportunity_id: Mapped[int | None] = mapped_column(ForeignKey("opportunities.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(30))  # approve / reject / edit / source_add ...
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AppSetting(Base):
    """Live-tunable configuration (scoring weights, AI priority, noise rules...)."""
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict | list | str | int | float | None] = mapped_column(JSON, nullable=True)
