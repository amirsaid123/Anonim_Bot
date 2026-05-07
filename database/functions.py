from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select, func, desc, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    Admin, AnonymousSession, BlockedSession, Comment,
    Message, PremiumUser, Referral, Report, User, UserSettings,
)


# ── Users ─────────────────────────────────────────────────────────────────────

async def insert_user(
    session: AsyncSession,
    telegram_id: int,
    username: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str],
    joined_date: datetime,
) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    user = User(
        telegram_id=telegram_id,
        user_name=username,
        first_name=first_name,
        last_name=last_name,
        joined_date=joined_date,
    )
    session.add(user)
    await session.commit()
    return user


async def get_all_user_ids(session: AsyncSession) -> List[int]:
    result = await session.execute(select(User.telegram_id))
    return [row[0] for row in result.all()]


async def get_user_by_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
    return await session.get(User, telegram_id)


# ── Anonymous sessions (nicknames) ────────────────────────────────────────────

async def get_or_create_anon_session(
    session: AsyncSession, sender_id: int, receiver_id: int
) -> str:
    from bot.functions.nicknames import generate_nickname

    result = await session.execute(
        select(AnonymousSession).where(
            AnonymousSession.sender_id == sender_id,
            AnonymousSession.receiver_id == receiver_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing.nickname

    # Generate unique nickname for this receiver
    for _ in range(20):
        nickname = generate_nickname()
        taken = await session.execute(
            select(AnonymousSession).where(
                AnonymousSession.receiver_id == receiver_id,
                AnonymousSession.nickname == nickname,
            )
        )
        if not taken.scalar_one_or_none():
            break

    new = AnonymousSession(sender_id=sender_id, receiver_id=receiver_id, nickname=nickname)
    session.add(new)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        result = await session.execute(
            select(AnonymousSession).where(
                AnonymousSession.sender_id == sender_id,
                AnonymousSession.receiver_id == receiver_id,
            )
        )
        return result.scalar_one().nickname
    return nickname


# ── Messages ──────────────────────────────────────────────────────────────────

async def save_message(
    session: AsyncSession,
    sender_id: int,
    receiver_id: int,
    text: Optional[str] = None,
    telegram_message_id: Optional[int] = None,
    message_type: str = "text",
) -> Message:
    msg = Message(
        sender_id=sender_id,
        receiver_id=receiver_id,
        text=text,
        telegram_message_id=telegram_message_id,
        message_type=message_type,
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg


async def update_message_telegram_id(
    session: AsyncSession, msg_db_id: int, telegram_msg_id: int
) -> None:
    result = await session.execute(select(Message).where(Message.id == msg_db_id))
    msg = result.scalar_one_or_none()
    if msg:
        msg.telegram_message_id = telegram_msg_id
        await session.commit()


async def mark_message_read(session: AsyncSession, msg_db_id: int) -> Optional[int]:
    """Mark message as read, return sender_id for read receipt notification."""
    result = await session.execute(select(Message).where(Message.id == msg_db_id))
    msg = result.scalar_one_or_none()
    if msg and not msg.is_read:
        msg.is_read = True
        await session.commit()
        return msg.sender_id
    return None


async def get_chat_partner(
    session: AsyncSession, telegram_message_id: int, current_user_id: int
) -> Optional[int]:
    result = await session.execute(
        select(Message.sender_id, Message.receiver_id).where(
            Message.telegram_message_id == telegram_message_id
        )
    )
    row = result.first()
    if not row:
        return None
    sender_id, receiver_id = row
    if current_user_id == receiver_id:
        return sender_id
    elif current_user_id == sender_id:
        return receiver_id
    return None


async def get_message_by_id(session: AsyncSession, msg_db_id: int) -> Optional[Message]:
    return await session.get(Message, msg_db_id)


async def get_recent_messages_for_user(
    session: AsyncSession, user_id: int, limit: int = 10
) -> List[Message]:
    result = await session.execute(
        select(Message)
        .where(Message.receiver_id == user_id)
        .order_by(desc(Message.created_at))
        .limit(limit)
    )
    return result.scalars().all()


async def get_received_count(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.count(Message.id)).where(Message.receiver_id == user_id)
    )
    return result.scalar() or 0


async def get_sent_count(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.count(Message.id)).where(Message.sender_id == user_id)
    )
    return result.scalar() or 0


# ── Comments ──────────────────────────────────────────────────────────────────

async def insert_comment(
    session: AsyncSession,
    user_id: Optional[int],
    comment_text: str,
    created_at: Optional[datetime] = None,
) -> Comment:
    comment = Comment(
        user_id=user_id,
        comment=comment_text,
        created_at=created_at or datetime.utcnow(),
    )
    session.add(comment)
    await session.commit()
    await session.refresh(comment)
    return comment


# ── Block / Report ────────────────────────────────────────────────────────────

async def is_nickname_blocked(
    session: AsyncSession, receiver_id: int, nickname: str
) -> bool:
    result = await session.execute(
        select(BlockedSession).where(
            BlockedSession.receiver_id == receiver_id,
            BlockedSession.nickname == nickname,
        )
    )
    return result.scalar_one_or_none() is not None


async def block_nickname(
    session: AsyncSession, receiver_id: int, nickname: str
) -> bool:
    existing = await is_nickname_blocked(session, receiver_id, nickname)
    if existing:
        return False
    session.add(BlockedSession(receiver_id=receiver_id, nickname=nickname))
    await session.commit()
    return True


async def report_message(
    session: AsyncSession, reporter_id: int, msg_db_id: int
) -> bool:
    result = await session.execute(
        select(Report).where(
            Report.reporter_id == reporter_id,
            Report.message_id == msg_db_id,
        )
    )
    if result.scalar_one_or_none():
        return False  # already reported
    session.add(Report(reporter_id=reporter_id, message_id=msg_db_id))
    await session.commit()
    return True


async def get_recent_reports(session: AsyncSession, limit: int = 20) -> List[Report]:
    result = await session.execute(
        select(Report).order_by(desc(Report.created_at)).limit(limit)
    )
    return result.scalars().all()


# ── Premium ───────────────────────────────────────────────────────────────────

async def is_user_premium(session: AsyncSession, user_id: int) -> bool:
    result = await session.execute(
        select(PremiumUser).where(
            PremiumUser.telegram_id == user_id,
            PremiumUser.expires_at > datetime.utcnow(),
        )
    )
    return result.scalar_one_or_none() is not None


async def get_premium_expiry(session: AsyncSession, user_id: int) -> Optional[datetime]:
    result = await session.execute(
        select(PremiumUser.expires_at).where(PremiumUser.telegram_id == user_id)
    )
    return result.scalar_one_or_none()


async def grant_premium(session: AsyncSession, user_id: int, stars_paid: int) -> PremiumUser:
    existing = await session.get(PremiumUser, user_id)
    if existing:
        base = existing.expires_at if existing.expires_at > datetime.utcnow() else datetime.utcnow()
        existing.expires_at = base + timedelta(days=7)
        existing.stars_paid += stars_paid
        await session.commit()
        return existing
    premium = PremiumUser(
        telegram_id=user_id,
        expires_at=datetime.utcnow() + timedelta(days=7),
        stars_paid=stars_paid,
    )
    session.add(premium)
    await session.commit()
    return premium


# ── User settings ─────────────────────────────────────────────────────────────

async def get_or_create_settings(session: AsyncSession, user_id: int) -> UserSettings:
    settings = await session.get(UserSettings, user_id)
    if not settings:
        settings = UserSettings(telegram_id=user_id)
        session.add(settings)
        await session.commit()
    return settings


async def set_notifications(session: AsyncSession, user_id: int, enabled: bool) -> None:
    settings = await get_or_create_settings(session, user_id)
    settings.notifications_enabled = enabled
    await session.commit()


async def set_custom_slug(session: AsyncSession, user_id: int, slug: str) -> bool:
    """Returns False if slug is already taken."""
    taken = await session.execute(
        select(UserSettings).where(
            UserSettings.custom_slug == slug,
            UserSettings.telegram_id != user_id,
        )
    )
    if taken.scalar_one_or_none():
        return False
    settings = await get_or_create_settings(session, user_id)
    settings.custom_slug = slug
    await session.commit()
    return True


async def get_user_id_by_slug(session: AsyncSession, slug: str) -> Optional[int]:
    result = await session.execute(
        select(UserSettings.telegram_id).where(UserSettings.custom_slug == slug)
    )
    return result.scalar_one_or_none()


async def ban_user(session: AsyncSession, user_id: int) -> None:
    settings = await get_or_create_settings(session, user_id)
    settings.is_banned = True
    await session.commit()


async def unban_user(session: AsyncSession, user_id: int) -> None:
    settings = await get_or_create_settings(session, user_id)
    settings.is_banned = False
    await session.commit()


async def is_user_banned(session: AsyncSession, user_id: int) -> bool:
    settings = await session.get(UserSettings, user_id)
    return settings.is_banned if settings else False


# ── Referrals ─────────────────────────────────────────────────────────────────

async def save_referral(
    session: AsyncSession, referrer_id: int, referred_id: int
) -> bool:
    """Returns False if referred_id already has a referral."""
    existing = await session.execute(
        select(Referral).where(Referral.referred_id == referred_id)
    )
    if existing.scalar_one_or_none():
        return False
    if referrer_id == referred_id:
        return False
    session.add(Referral(referrer_id=referrer_id, referred_id=referred_id))
    try:
        await session.commit()
        return True
    except IntegrityError:
        await session.rollback()
        return False


async def get_referral_count(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.count(Referral.id)).where(Referral.referrer_id == user_id)
    )
    return result.scalar() or 0


# ── Admins ────────────────────────────────────────────────────────────────────

async def add_admin(session: AsyncSession, telegram_id: int) -> Admin:
    existing = await session.get(Admin, telegram_id)
    if existing:
        return existing
    admin = Admin(telegram_id=telegram_id)
    session.add(admin)
    await session.commit()
    return admin


async def remove_admin(session: AsyncSession, telegram_id: int) -> bool:
    admin = await session.get(Admin, telegram_id)
    if admin:
        await session.delete(admin)
        await session.commit()
        return True
    return False


async def list_admins(session: AsyncSession) -> List[Admin]:
    result = await session.execute(select(Admin))
    return result.scalars().all()


# ── Statistics ────────────────────────────────────────────────────────────────

async def get_total_users(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(User.telegram_id)))
    return result.scalar() or 0


async def get_users_today(session: AsyncSession) -> int:
    today = datetime.utcnow().date()
    result = await session.execute(
        select(func.count(User.telegram_id)).where(func.date(User.joined_date) == today)
    )
    return result.scalar() or 0


async def get_users_this_week(session: AsyncSession) -> int:
    week_ago = datetime.utcnow() - timedelta(days=7)
    result = await session.execute(
        select(func.count(User.telegram_id)).where(User.joined_date >= week_ago)
    )
    return result.scalar() or 0


async def get_total_messages(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(Message.id)))
    return result.scalar() or 0


async def get_messages_today(session: AsyncSession) -> int:
    today = datetime.utcnow().date()
    result = await session.execute(
        select(func.count(Message.id)).where(func.date(Message.created_at) == today)
    )
    return result.scalar() or 0


async def get_messages_this_week(session: AsyncSession) -> int:
    week_ago = datetime.utcnow() - timedelta(days=7)
    result = await session.execute(
        select(func.count(Message.id)).where(Message.created_at >= week_ago)
    )
    return result.scalar() or 0


async def get_most_active_sender(session: AsyncSession) -> Optional[dict]:
    result = await session.execute(
        select(Message.sender_id, func.count(Message.id).label("cnt"))
        .group_by(Message.sender_id)
        .order_by(desc("cnt"))
        .limit(1)
    )
    row = result.first()
    return {"sender_id": row.sender_id, "message_count": row.cnt} if row else None


async def get_total_comments(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(Comment.id)))
    return result.scalar() or 0


async def get_comments_today(session: AsyncSession) -> int:
    today = datetime.utcnow().date()
    result = await session.execute(
        select(func.count(Comment.id)).where(func.date(Comment.created_at) == today)
    )
    return result.scalar() or 0


async def get_total_premium_users(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count(PremiumUser.telegram_id)).where(
            PremiumUser.expires_at > datetime.utcnow()
        )
    )
    return result.scalar() or 0


async def get_total_reports(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(Report.id)))
    return result.scalar() or 0
