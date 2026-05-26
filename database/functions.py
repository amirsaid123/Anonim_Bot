from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.exc import IntegrityError

from bot.functions.tokens import generate_token
from database.models import Comment, Message, User, Admin, Block, LinkToken


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
        created_at=created_at or _utcnow()
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
        created_at=created_at or _utcnow()
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
        .where(
            Message.telegram_message_id == telegram_message_id,
            or_(
                Message.sender_id == current_user_id,
                Message.receiver_id == current_user_id,
            ),
        )
        .order_by(Message.id.desc())
        .limit(1)
    )
    row = result.first()

    if not row:
        return None

    sender_id, receiver_id = row
    return sender_id if current_user_id == receiver_id else receiver_id


async def get_total_users(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count(User.telegram_id))
    )
    return result.scalar() or 0


async def get_users_today(session: AsyncSession) -> int:
    today = _utcnow().date()

    result = await session.execute(
        select(func.count(User.telegram_id))
        .where(func.date(User.joined_date) == today)
    )
    return result.scalar() or 0


async def get_users_this_week(session: AsyncSession) -> int:
    week_ago = _utcnow() - timedelta(days=7)

    result = await session.execute(
        select(func.count(User.telegram_id))
        .where(User.joined_date >= week_ago)
    )
    return result.scalar() or 0


async def get_total_messages(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count(Message.id))
    )
    return result.scalar() or 0


async def get_messages_today(session: AsyncSession) -> int:
    today = _utcnow().date()

    result = await session.execute(
        select(func.count(Message.id))
        .where(func.date(Message.created_at) == today)
    )
    return result.scalar() or 0


async def get_messages_this_week(session: AsyncSession) -> int:
    week_ago = _utcnow() - timedelta(days=7)

    result = await session.execute(
        select(func.count(Message.id))
        .where(Message.created_at >= week_ago)
    )
    return result.scalar() or 0


async def get_most_active_sender(session: AsyncSession):
    result = await session.execute(
        select(
            Message.sender_id,
            func.count(Message.id).label("message_count")
        )
        .group_by(Message.sender_id)
        .order_by(desc("message_count"))
        .limit(1)
    )

    row = result.first()

    if not row:
        return None

    return {
        "sender_id": row.sender_id,
        "message_count": row.message_count
    }


async def get_total_comments(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count(Comment.id))
    )
    return result.scalar() or 0


async def get_comments_today(session: AsyncSession) -> int:
    today = _utcnow().date()

    result = await session.execute(
        select(func.count(Comment.id))
        .where(func.date(Comment.created_at) == today)
    )
    return result.scalar() or 0


async def add_admin(session: AsyncSession, telegram_id: int):
    existing = await session.get(Admin, telegram_id)
    if not existing:
        new_admin = Admin(telegram_id=telegram_id)
        session.add(new_admin)
        await session.commit()
        await session.refresh(new_admin)
        return new_admin
    return existing


async def remove_admin(session: AsyncSession, telegram_id: int):
    admin = await session.get(Admin, telegram_id)
    if admin:
        await session.delete(admin)
        await session.commit()
        return True
    return False


async def list_admins(session: AsyncSession):
    result = await session.execute(select(Admin))
    return result.scalars().all()


# --- Welcome message ---

async def set_welcome_message(session: AsyncSession, telegram_id: int, text: Optional[str]) -> None:
    user = await session.get(User, telegram_id)
    if user is None:
        return
    user.welcome_message = text
    await session.commit()


async def get_welcome_message(session: AsyncSession, telegram_id: int) -> Optional[str]:
    user = await session.get(User, telegram_id)
    return user.welcome_message if user else None


# --- Locale persistence ---

async def set_user_locale(session: AsyncSession, telegram_id: int, locale: str) -> None:
    user = await session.get(User, telegram_id)
    if user is None:
        return
    user.locale = locale
    await session.commit()


async def get_user_locale(session: AsyncSession, telegram_id: int) -> Optional[str]:
    user = await session.get(User, telegram_id)
    return user.locale if user else None


# --- Blocks ---

async def add_block(session: AsyncSession, blocker_id: int, blocked_id: int) -> bool:
    existing = await session.execute(
        select(Block).where(
            Block.blocker_id == blocker_id,
            Block.blocked_id == blocked_id,
        )
    )
    if existing.scalar_one_or_none():
        return False
    session.add(Block(blocker_id=blocker_id, blocked_id=blocked_id))
    await session.commit()
    return True


async def remove_block(session: AsyncSession, blocker_id: int, blocked_id: int) -> bool:
    result = await session.execute(
        select(Block).where(
            Block.blocker_id == blocker_id,
            Block.blocked_id == blocked_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        return False
    await session.delete(row)
    await session.commit()
    return True


async def is_blocked(session: AsyncSession, blocker_id: int, blocked_id: int) -> bool:
    result = await session.execute(
        select(Block.blocker_id).where(
            Block.blocker_id == blocker_id,
            Block.blocked_id == blocked_id,
        )
    )
    return result.first() is not None


async def list_blocks_for(session: AsyncSession, blocker_id: int):
    result = await session.execute(
        select(Block.blocked_id).where(Block.blocker_id == blocker_id)
    )
    return [row[0] for row in result.all()]


# --- Per-user stats ---

async def get_user_received_count(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.count(Message.id)).where(Message.receiver_id == user_id)
    )
    return result.scalar() or 0


async def get_user_sent_count(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.count(Message.id)).where(Message.sender_id == user_id)
    )
    return result.scalar() or 0


async def get_user_received_this_week(session: AsyncSession, user_id: int) -> int:
    week_ago = _utcnow() - timedelta(days=7)
    result = await session.execute(
        select(func.count(Message.id)).where(
            Message.receiver_id == user_id,
            Message.created_at >= week_ago,
        )
    )
    return result.scalar() or 0


async def get_user_sent_this_week(session: AsyncSession, user_id: int) -> int:
    week_ago = _utcnow() - timedelta(days=7)
    result = await session.execute(
        select(func.count(Message.id)).where(
            Message.sender_id == user_id,
            Message.created_at >= week_ago,
        )
    )
    return result.scalar() or 0


async def get_user_unique_senders_count(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.count(func.distinct(Message.sender_id))).where(
            Message.receiver_id == user_id
        )
    )
    return result.scalar() or 0


async def get_user_top_sender(session: AsyncSession, user_id: int) -> Optional[dict]:
    result = await session.execute(
        select(
            Message.sender_id,
            func.count(Message.id).label("message_count"),
        )
        .where(Message.receiver_id == user_id)
        .group_by(Message.sender_id)
        .order_by(desc("message_count"))
        .limit(1)
    )
    row = result.first()
    if not row:
        return None
    return {"sender_id": row.sender_id, "count": row.message_count}


# --- Broadcast ---

async def get_all_user_ids(session: AsyncSession) -> list[int]:
    result = await session.execute(select(User.telegram_id))
    return [row[0] for row in result.all()]


# --- Link tokens ---

_TOKEN_INSERT_RETRIES = 5


async def generate_link_token_for(
        session: AsyncSession,
        user_id: int,
        is_custom: bool = False,
        label: Optional[str] = None,
) -> str:
    """Insert a fresh random token for the user; retry on collision."""
    last_error: Optional[Exception] = None
    for _ in range(_TOKEN_INSERT_RETRIES):
        token = generate_token()
        new_row = LinkToken(token=token, user_id=user_id, is_custom=is_custom, label=label)
        session.add(new_row)
        try:
            await session.commit()
            return token
        except IntegrityError as exc:
            await session.rollback()
            last_error = exc
    raise RuntimeError("Could not generate a unique link token after retries") from last_error


async def get_or_create_default_link_token(session: AsyncSession, user_id: int) -> str:
    """Return the user's existing (oldest) token, creating one on first call."""
    result = await session.execute(
        select(LinkToken.token)
        .where(LinkToken.user_id == user_id)
        .order_by(LinkToken.created_at.asc())
        .limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    return await generate_link_token_for(session, user_id)


async def resolve_link_token(session: AsyncSession, token: str) -> Optional[int]:
    """Token -> user_id lookup. Returns None when the token doesn't exist."""
    if not token:
        return None
    result = await session.execute(
        select(LinkToken.user_id).where(LinkToken.token == token)
    )
    return result.scalar_one_or_none()


# --- Admin dashboard stats v2 ---

async def get_new_users_per_day(session: AsyncSession, days: int = 7) -> list[tuple]:
    """Returns [(date, count), ...] for the last `days` days, including zeros."""
    now = _utcnow()
    since_ts = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    since_date = since_ts.date()

    day_expr = func.date(User.joined_date)
    result = await session.execute(
        select(day_expr.label("d"), func.count(User.telegram_id).label("c"))
        .where(User.joined_date >= since_ts)
        .group_by(day_expr)
    )
    by_date = {row.d: row.c for row in result.all()}

    out = []
    for i in range(days):
        d = since_date + timedelta(days=i)
        out.append((d, by_date.get(d, 0)))
    return out


async def get_activation_rate(session: AsyncSession) -> dict:
    """% of users who have ever sent at least one message."""
    total = (await session.execute(select(func.count(User.telegram_id)))).scalar() or 0
    active = (await session.execute(select(func.count(func.distinct(Message.sender_id))))).scalar() or 0
    return {"total": total, "active": active}


async def get_cohort_activation(session: AsyncSession, days: int = 7) -> dict:
    """Of users who joined in the last `days` days, how many have sent ≥1 message."""
    since = _utcnow() - timedelta(days=days)

    cohort = (await session.execute(
        select(func.count(User.telegram_id)).where(User.joined_date >= since)
    )).scalar() or 0

    activated = (await session.execute(
        select(func.count(func.distinct(User.telegram_id)))
        .select_from(User)
        .join(Message, Message.sender_id == User.telegram_id)
        .where(User.joined_date >= since)
    )).scalar() or 0

    return {"cohort": cohort, "activated": activated}


async def get_top_senders_week(session: AsyncSession, limit: int = 3) -> list[dict]:
    week_ago = _utcnow() - timedelta(days=7)
    result = await session.execute(
        select(
            Message.sender_id,
            User.first_name,
            User.user_name,
            func.count(Message.id).label("c"),
        )
        .outerjoin(User, User.telegram_id == Message.sender_id)
        .where(Message.created_at >= week_ago)
        .group_by(Message.sender_id, User.first_name, User.user_name)
        .order_by(desc("c"))
        .limit(limit)
    )
    return [
        {
            "user_id": row.sender_id,
            "first_name": row.first_name,
            "user_name": row.user_name,
            "count": row.c,
        }
        for row in result.all()
    ]


async def get_top_receivers_week(session: AsyncSession, limit: int = 3) -> list[dict]:
    week_ago = _utcnow() - timedelta(days=7)
    result = await session.execute(
        select(
            Message.receiver_id,
            User.first_name,
            User.user_name,
            func.count(Message.id).label("c"),
        )
        .outerjoin(User, User.telegram_id == Message.receiver_id)
        .where(Message.created_at >= week_ago)
        .group_by(Message.receiver_id, User.first_name, User.user_name)
        .order_by(desc("c"))
        .limit(limit)
    )
    return [
        {
            "user_id": row.receiver_id,
            "first_name": row.first_name,
            "user_name": row.user_name,
            "count": row.c,
        }
        for row in result.all()
    ]


async def get_top_viral_users(session: AsyncSession, limit: int = 3) -> list[dict]:
    """Top users by total link hits. All-time — hits is a counter, no event log."""
    result = await session.execute(
        select(
            LinkToken.user_id,
            User.first_name,
            User.user_name,
            func.sum(LinkToken.hits).label("h"),
        )
        .outerjoin(User, User.telegram_id == LinkToken.user_id)
        .group_by(LinkToken.user_id, User.first_name, User.user_name)
        .having(func.sum(LinkToken.hits) > 0)
        .order_by(desc("h"))
        .limit(limit)
    )
    return [
        {
            "user_id": row.user_id,
            "first_name": row.first_name,
            "user_name": row.user_name,
            "hits": int(row.h or 0),
        }
        for row in result.all()
    ]


async def get_locale_distribution(session: AsyncSession) -> list[tuple]:
    """Returns [(locale, count), ...]. NULL locales grouped under 'unset'."""
    result = await session.execute(
        select(User.locale, func.count(User.telegram_id).label("c"))
        .group_by(User.locale)
        .order_by(desc("c"))
    )
    return [(row[0] or "unset", row[1]) for row in result.all()]