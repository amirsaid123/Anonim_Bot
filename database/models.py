from datetime import datetime
from typing import List
from typing import Optional
from sqlalchemy import BIGINT, Boolean, Integer, Text, DateTime, ForeignKey, func
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(
        BIGINT, primary_key=True, autoincrement=False
    )

    user_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    welcome_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    locale: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)

    joined_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    comments: Mapped[List["Comment"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )

    sent_messages: Mapped[List["Message"]] = relationship(
        "Message", back_populates="sender", foreign_keys="Message.sender_id"
    )

    received_messages: Mapped[List["Message"]] = relationship(
        "Message", back_populates="receiver", foreign_keys="Message.receiver_id"
    )



class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        BIGINT,
        ForeignKey("users.telegram_id", ondelete="SET NULL"),
        nullable=True
    )
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    user: Mapped[Optional["User"]] = relationship(back_populates="comments")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)

    sender_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("users.telegram_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    receiver_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("users.telegram_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    telegram_message_id: Mapped[Optional[int]] = mapped_column(BIGINT, nullable=True)

    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )

    sender: Mapped["User"] = relationship(
        "User",
        foreign_keys=[sender_id],
        back_populates="sent_messages"
    )

    receiver: Mapped["User"] = relationship(
        "User",
        foreign_keys=[receiver_id],
        back_populates="received_messages"
    )


class Admin(Base):
    __tablename__ = "admins"

    telegram_id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=False)


class Block(Base):
    __tablename__ = "blocks"

    blocker_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("users.telegram_id", ondelete="CASCADE"),
        primary_key=True,
    )
    blocked_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("users.telegram_id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class LinkToken(Base):
    __tablename__ = "link_tokens"

    token: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("users.telegram_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    hits: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
