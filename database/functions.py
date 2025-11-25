from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Comment, Message, User


async def insert_user(
        session: AsyncSession,
        telegram_id: int,
        username: str,
        first_name: str,
        last_name: str,
        joined_date: datetime,
):
    stmt = select(User).filter(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if not existing_user:
        new_user = User(
            telegram_id=telegram_id,
            user_name=username,
            first_name=first_name,
            last_name=last_name,
            joined_date=joined_date
        )
        session.add(new_user)
        await session.commit()
        return new_user

    return existing_user


async def insert_comment(
        session: AsyncSession,
        user_id: Optional[int],
        comment_text: str,
        created_at: Optional[datetime] = None
):
    new_comment = Comment(
        user_id=user_id,
        comment=comment_text,
        created_at=created_at or datetime.utcnow()
    )

    session.add(new_comment)
    await session.commit()
    await session.refresh(new_comment)
    return new_comment


async def save_message(
        session: AsyncSession,
        sender_id: int,
        receiver_id: int,
        text: Optional[str] = None,
        telegram_message_id: Optional[int] = None,
        created_at: Optional[datetime] = None,
):
    new_message = Message(
        sender_id=sender_id,
        receiver_id=receiver_id,
        text=text,
        telegram_message_id=telegram_message_id,
        created_at=created_at or datetime.utcnow()
    )

    session.add(new_message)
    await session.commit()
    await session.refresh(new_message)
    return new_message


async def get_chat_partner(
        session: AsyncSession,
        telegram_message_id: int,
        current_user_id: int
) -> Optional[int]:
    result = await session.execute(
        select(Message.sender_id, Message.receiver_id)
        .where(Message.telegram_message_id == telegram_message_id)
    )
    row = result.first()

    if not row:
        return None

    sender_id, receiver_id = row

    if current_user_id == receiver_id:
        return sender_id
    elif current_user_id == sender_id:
        return receiver_id
    else:
        return None
