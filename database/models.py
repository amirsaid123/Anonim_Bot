from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BIGINT, Boolean, DateTime, ForeignKey, Integer,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=False)
    user_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    joined_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    comments: Mapped[List["Comment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    sent_messages: Mapped[List["Message"]] = relationship(
        "Message", back_populates="sender", foreign_keys="Message.sender_id"
    )
    received_messages: Mapped[List["Message"]] = relationship(
        "Message", back_populates="receiver", foreign_keys="Message.receiver_id"
    )
    premium: Mapped[Optional["PremiumUser"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    settings: Mapped[Optional["UserSettings"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    referrals_given: Mapped[List["Referral"]] = relationship(
        "Referral", back_populates="referrer", foreign_keys="Referral.referrer_id"
    )
    referral_received: Mapped[Optional["Referral"]] = relationship(
        "Referral", back_populates="referred", foreign_keys="Referral.referred_id", uselist=False
    )
    anon_sessions_sent: Mapped[List["AnonymousSession"]] = relationship(
        "AnonymousSession", back_populates="sender_user", foreign_keys="AnonymousSession.sender_id"
    )
    anon_sessions_received: Mapped[List["AnonymousSession"]] = relationship(
        "AnonymousSession", back_populates="receiver_user", foreign_keys="AnonymousSession.receiver_id"
    )


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        BIGINT, ForeignKey("users.telegram_id", ondelete="SET NULL"), nullable=True
    )
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    user: Mapped[Optional["User"]] = relationship(back_populates="comments")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    sender_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False, index=True
    )
    receiver_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False, index=True
    )
    telegram_message_id: Mapped[Optional[int]] = mapped_column(BIGINT, nullable=True)
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    message_type: Mapped[str] = mapped_column(String(20), default="text", nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    sender: Mapped["User"] = relationship(
        "User", foreign_keys=[sender_id], back_populates="sent_messages"
    )
    receiver: Mapped["User"] = relationship(
        "User", foreign_keys=[receiver_id], back_populates="received_messages"
    )
    reports: Mapped[List["Report"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )


class Admin(Base):
    __tablename__ = "admins"

    telegram_id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=False)


class AnonymousSession(Base):
    """Persistent nickname assigned to a sender for a specific receiver."""
    __tablename__ = "anonymous_sessions"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    sender_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False
    )
    receiver_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False
    )
    nickname: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sender_user: Mapped["User"] = relationship(
        "User", foreign_keys=[sender_id], back_populates="anon_sessions_sent"
    )
    receiver_user: Mapped["User"] = relationship(
        "User", foreign_keys=[receiver_id], back_populates="anon_sessions_received"
    )

    __table_args__ = (
        UniqueConstraint("sender_id", "receiver_id", name="uq_anon_sender_receiver"),
    )


class PremiumUser(Base):
    __tablename__ = "premium_users"

    telegram_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("users.telegram_id", ondelete="CASCADE"), primary_key=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stars_paid: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="premium")


class BlockedSession(Base):
    """A receiver has blocked a specific nickname from sending more messages."""
    __tablename__ = "blocked_sessions"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    receiver_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False, index=True
    )
    nickname: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("receiver_id", "nickname", name="uq_blocked_receiver_nickname"),
    )


class UserSettings(Base):
    __tablename__ = "user_settings"

    telegram_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("users.telegram_id", ondelete="CASCADE"), primary_key=True
    )
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    custom_slug: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, unique=True, index=True
    )
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped["User"] = relationship(back_populates="settings")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    reporter_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    message: Mapped["Message"] = relationship(back_populates="reports")


class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    referrer_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False, index=True
    )
    referred_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    referrer: Mapped["User"] = relationship(
        "User", foreign_keys=[referrer_id], back_populates="referrals_given"
    )
    referred: Mapped["User"] = relationship(
        "User", foreign_keys=[referred_id], back_populates="referral_received"
    )
