"""Database tables. Names and columns match the original schema, plus a few additions
(see MIGRATIONS in db.py), so an existing database keeps working."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow():
    """Naive UTC, matching the original TIMESTAMP (without time zone) columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class PostStatus:
    PENDING_APPROVAL = "pending_approval"  # written, waiting for someone to approve it
    SCHEDULED = "scheduled"  # will publish at scheduled_time
    POSTING = "posting"  # being published right now
    POSTED = "posted"
    FAILED = "failed"
    REJECTED = "rejected"

    ALL = (PENDING_APPROVAL, SCHEDULED, POSTING, POSTED, FAILED, REJECTED)


class Niche(Base):
    __tablename__ = "niches"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    primary_statement: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    hashtags: Mapped[list["Hashtag"]] = relationship(
        back_populates="niche", cascade="all, delete-orphan", order_by="Hashtag.id"
    )


class Hashtag(Base):
    __tablename__ = "hashtags"

    id: Mapped[int] = mapped_column(primary_key=True)
    niche_id: Mapped[int] = mapped_column(ForeignKey("niches.id", ondelete="CASCADE"))
    tag: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    niche: Mapped[Niche] = relationship(back_populates="hashtags")


class Account(Base):
    """A social media account. Token columns hold encrypted values ("enc:...").

    X uses api_key, api_secret, access_token and access_secret.
    LinkedIn uses access_token and author_urn (urn:li:person:... or urn:li:organization:...).
    """

    __tablename__ = "platform_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(50))
    name: Mapped[Optional[str]] = mapped_column(String(255))
    author_urn: Mapped[Optional[str]] = mapped_column(String(255))
    api_key: Mapped[Optional[str]] = mapped_column(Text)
    api_secret: Mapped[Optional[str]] = mapped_column(Text)
    access_token: Mapped[Optional[str]] = mapped_column(Text)
    access_secret: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Schedule(Base):
    """Post `posts_per_day` AI-written posts about a niche to an account."""

    __tablename__ = "schedule"

    id: Mapped[int] = mapped_column(primary_key=True)
    niche_id: Mapped[int] = mapped_column(ForeignKey("niches.id", ondelete="CASCADE"))
    account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("platform_accounts.id", ondelete="SET NULL"))
    posts_per_day: Mapped[int] = mapped_column(Integer)
    needs_approval: Mapped[int] = mapped_column(Integer, default=1)  # 0/1, as in the original schema
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    niche: Mapped[Niche] = relationship()
    account: Mapped[Optional[Account]] = relationship()


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    niche_id: Mapped[Optional[int]] = mapped_column(ForeignKey("niches.id", ondelete="CASCADE"))
    account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("platform_accounts.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(Text)
    media_url: Mapped[Optional[str]] = mapped_column(Text)  # not published yet; kept from the original schema
    scheduled_time: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)  # naive UTC
    status: Mapped[str] = mapped_column(String(50), default=PostStatus.PENDING_APPROVAL, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    external_id: Mapped[Optional[str]] = mapped_column(String(64))  # e.g. the tweet id

    niche: Mapped[Optional[Niche]] = relationship()
    account: Mapped[Optional[Account]] = relationship()
