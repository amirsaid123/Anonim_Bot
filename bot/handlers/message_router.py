"""
Anonymous message sending, reply handling, and per-message action buttons.
"""
from collections import defaultdict
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, Message,
)
from aiogram.utils.i18n import gettext as _
from aiogram.utils.markdown import hbold

from bot.functions import UserStates, MsgActionCB, ReactCB, REACT_MAP
from database.models import Message as MessageModel
from database.functions import (
    get_or_create_anon_session,
    is_nickname_blocked,
    is_user_banned,
    is_user_premium,
    list_admins,
    save_message,
    update_message_telegram_id,
    get_chat_partner,
    get_or_create_settings,
    mark_message_read,
)
from database.session import get_db_session
from utils.config import MainConfig

msg_router = Router()

# ── Simple in-memory rate limiter ─────────────────────────────────────────────
_rate_data: dict[int, list[datetime]] = defaultdict(list)
_RATE_LIMIT = 10
_RATE_WINDOW = 60  # seconds


def _is_rate_limited(user_id: int) -> bool:
    now = datetime.utcnow()
    cutoff = now - timedelta(seconds=_RATE_WINDOW)
    _rate_data[user_id] = [t for t in _rate_data[user_id] if t > cutoff]
    if len(_rate_data[user_id]) >= _RATE_LIMIT:
        return True
    _rate_data[user_id].append(now)
    return False


# ── Keyboard builders ─────────────────────────────────────────────────────────

def _action_keyboard(msg_db_id: int, premium_receiver: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    if premium_receiver:
        rows.append([
            InlineKeyboardButton(
                text=emoji,
                callback_data=ReactCB(msg_id=msg_db_id, emoji=code).pack(),
            )
            for code, emoji in REACT_MAP.items()
        ])
        rows.append([
            InlineKeyboardButton(
                text="👁 Mark Read",
                callback_data=MsgActionCB(action="read", msg_id=msg_db_id).pack(),
            )
        ])

    rows.append([
        InlineKeyboardButton(
            text="🚫 Block",
            callback_data=MsgActionCB(action="block", msg_id=msg_db_id).pack(),
        ),
        InlineKeyboardButton(
            text="⚠️ Report",
            callback_data=MsgActionCB(action="report", msg_id=msg_db_id).pack(),
        ),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Send anonymous message ─────────────────────────────────────────────────────

@msg_router.message(UserStates.waiting_for_message)
async def send_anon(message: Message, state: FSMContext):
    data = await state.get_data()
    receiver_id: int = data["receiver_id"]
    sender_id = message.from_user.id

    if _is_rate_limited(sender_id):
        await message.answer(_("⏳ Slow down! You're sending too fast. Try again in a minute."))
        return

    session = await get_db_session()

    if await is_user_banned(session, sender_id):
        await session.close()
        await message.answer(_("🚫 You are banned from using this bot."))
        return

    # Get or create persistent nickname for this sender→receiver pair
    nickname = await get_or_create_anon_session(session, sender_id, receiver_id)

    if await is_nickname_blocked(session, receiver_id, nickname):
        await session.close()
        await message.answer(
            _("🚫 This user has blocked your messages.")
        )
        return

    original_text = (message.caption or message.text or "").strip()
    msg_type = message.content_type

    # Check if receiver is premium for extra buttons
    receiver_premium = await is_user_premium(session, receiver_id)

    # Check receiver notification settings
    receiver_settings = await get_or_create_settings(session, receiver_id)
    disable_notif = not receiver_settings.notifications_enabled

    # Check if receiver is an admin (show sender info to admins)
    admins = await list_admins(session)
    admin_ids = {a.telegram_id for a in admins}
    is_admin_receiver = receiver_id in admin_ids or receiver_id in MainConfig.admin.SUPER_ADMIN_IDS

    # Check if sender is premium (badge)
    sender_premium = await is_user_premium(session, sender_id)
    premium_badge = "⭐ " if sender_premium else ""

    reply_hint = _("\n\n➡️ Swipe right on this message to reply anonymously")

    if is_admin_receiver:
        caption = (
            f"📨 {premium_badge}NEW ANONYMOUS MESSAGE\n"
            f"From: <b>{nickname}</b>\n\n"
            f"{original_text}\n\n"
            f"{hbold('👤 SENDER INFO')}\n"
            f"Name: {message.from_user.full_name}\n"
            f"Username: @{message.from_user.username or 'none'}\n"
            f"ID: <code>{sender_id}</code>\n"
            f"Profile: <a href='tg://user?id={sender_id}'>Open</a>"
            f"{reply_hint}"
        )
    else:
        caption = (
            f"💌 {premium_badge}ANONYMOUS MESSAGE\n"
            f"From: <b>{nickname}</b>\n\n"
            f"{original_text}"
            f"{reply_hint}"
        )

    # Save to DB first to get the ID for callback data
    db_msg = await save_message(session, sender_id, receiver_id, original_text, message_type=msg_type)
    keyboard = _action_keyboard(db_msg.id, receiver_premium)

    if msg_type == "text":
        sent = await message.bot.send_message(
            chat_id=receiver_id,
            text=caption,
            parse_mode="HTML",
            protect_content=True,
            disable_web_page_preview=True,
            disable_notification=disable_notif,
            reply_markup=keyboard,
        )
    else:
        sent = await message.bot.copy_message(
            chat_id=receiver_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            caption=caption,
            parse_mode="HTML",
            protect_content=True,
            disable_notification=disable_notif,
            reply_markup=keyboard,
        )

    await update_message_telegram_id(session, db_msg.id, sent.message_id)
    await session.close()

    await message.answer(_("💌 Sent anonymously! You can send another message anytime 😊"))


# ── Reply handler ─────────────────────────────────────────────────────────────

@msg_router.message(F.reply_to_message)
async def handle_reply(message: Message, state: FSMContext):
    # Don't interfere with states expecting input
    current_state = await state.get_state()
    if current_state is not None:
        return

    replied_msg_id = message.reply_to_message.message_id
    current_user_id = message.from_user.id

    session = await get_db_session()
    target_id = await get_chat_partner(session, replied_msg_id, current_user_id)

    if not target_id:
        await session.close()
        return

    if _is_rate_limited(current_user_id):
        await session.close()
        await message.answer(_("⏳ Slow down! Try again in a minute."))
        return

    original_text = (message.caption or message.text or "").strip()
    msg_type = message.content_type

    target_premium = await is_user_premium(session, target_id)
    target_settings = await get_or_create_settings(session, target_id)
    disable_notif = not target_settings.notifications_enabled

    admins = await list_admins(session)
    admin_ids = {a.telegram_id for a in admins}
    is_admin_target = target_id in admin_ids or target_id in MainConfig.admin.SUPER_ADMIN_IDS

    sender_premium = await is_user_premium(session, current_user_id)
    premium_badge = "⭐ " if sender_premium else ""

    footer = _("\n\n➡️ Swipe right on this message to reply anonymously")

    if is_admin_target:
        caption = (
            f"📨 {premium_badge}ANONYMOUS REPLY\n\n"
            f"{original_text}\n\n"
            f"{hbold('👤 REPLY FROM')}\n"
            f"Name: {message.from_user.full_name}\n"
            f"Username: @{message.from_user.username or 'none'}\n"
            f"ID: <code>{current_user_id}</code>\n"
            f"Profile: <a href='tg://user?id={current_user_id}'>Open</a>"
            f"{footer}"
        )
    else:
        caption = f"💬 {premium_badge}ANONYMOUS REPLY\n\n{original_text}{footer}"

    db_msg = await save_message(
        session, current_user_id, target_id, original_text, message_type=msg_type
    )
    keyboard = _action_keyboard(db_msg.id, target_premium)

    if msg_type == "text":
        sent = await message.bot.send_message(
            chat_id=target_id,
            text=caption,
            parse_mode="HTML",
            protect_content=True,
            disable_web_page_preview=True,
            disable_notification=disable_notif,
            reply_markup=keyboard,
        )
    else:
        sent = await message.bot.copy_message(
            chat_id=target_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            caption=caption,
            parse_mode="HTML",
            protect_content=True,
            disable_notification=disable_notif,
            reply_markup=keyboard,
        )

    await update_message_telegram_id(session, db_msg.id, sent.message_id)
    await session.close()

    await message.answer(_("💬 Reply sent anonymously! ✨"))


# ── Inline button handlers ────────────────────────────────────────────────────

@msg_router.callback_query(MsgActionCB.filter(F.action == "block"))
async def handle_block(callback, callback_data: MsgActionCB):
    session = await get_db_session()
    from database.functions import block_nickname
    msg = await session.get(MessageModel, callback_data.msg_id)

    if not msg or msg.receiver_id != callback.from_user.id:
        await session.close()
        await callback.answer(_("❌ Message not found."), show_alert=True)
        return

    nickname = await get_or_create_anon_session(session, msg.sender_id, msg.receiver_id)
    blocked = await block_nickname(session, receiver_id=callback.from_user.id, nickname=nickname)
    await session.close()

    if blocked:
        await callback.answer(_("🚫 Blocked! This sender can no longer message you."), show_alert=True)
    else:
        await callback.answer(_("Already blocked."), show_alert=True)


@msg_router.callback_query(MsgActionCB.filter(F.action == "report"))
async def handle_report(callback, callback_data: MsgActionCB):
    session = await get_db_session()
    from database.functions import report_message
    from bot.handlers.functions import send_report_to_admin_group

    msg = await session.get(MessageModel, callback_data.msg_id)
    if not msg or msg.receiver_id != callback.from_user.id:
        await session.close()
        await callback.answer("❌ Not found.", show_alert=True)
        return

    nickname = await get_or_create_anon_session(session, msg.sender_id, msg.receiver_id)
    reported = await report_message(session, reporter_id=callback.from_user.id, msg_db_id=callback_data.msg_id)
    await session.close()

    if reported:
        await send_report_to_admin_group(
            bot=callback.bot,
            reporter_id=callback.from_user.id,
            msg_db_id=callback_data.msg_id,
            nickname=nickname,
            text=msg.text or "[media]",
        )
        await callback.answer("⚠️ Reported to admins. Thank you!", show_alert=True)
    else:
        await callback.answer("You already reported this message.", show_alert=True)


@msg_router.callback_query(MsgActionCB.filter(F.action == "read"))
async def handle_mark_read(callback, callback_data: MsgActionCB):
    session = await get_db_session()
    msg = await session.get(MessageModel, callback_data.msg_id)

    if not msg or msg.receiver_id != callback.from_user.id:
        await session.close()
        await callback.answer("❌ Not found.", show_alert=True)
        return

    sender_id = await mark_message_read(session, callback_data.msg_id)
    await session.close()

    if sender_id:
        try:
            await callback.bot.send_message(
                chat_id=sender_id,
                text=_("👁 Your anonymous message was read!"),
            )
        except Exception:
            pass
        await callback.answer("✅ Marked as read.", show_alert=False)
    else:
        await callback.answer("Already marked as read.", show_alert=False)


@msg_router.callback_query(ReactCB.filter())
async def handle_reaction(callback, callback_data: ReactCB):
    session = await get_db_session()

    # Only premium receivers can react
    if not await is_user_premium(session, callback.from_user.id):
        await session.close()
        await callback.answer("⭐ Reactions are a Premium feature!", show_alert=True)
        return

    msg = await session.get(MessageModel, callback_data.msg_id)
    if not msg or msg.receiver_id != callback.from_user.id:
        await session.close()
        await callback.answer("❌ Not found.", show_alert=True)
        return

    sender_id = msg.sender_id
    await session.close()

    emoji = REACT_MAP.get(callback_data.emoji, "❤️")
    try:
        await callback.bot.send_message(
            chat_id=sender_id,
            text=_("✨ Your anonymous message got a {emoji} reaction!").format(emoji=emoji),
        )
    except Exception:
        pass

    await callback.answer(f"{emoji} Reaction sent!", show_alert=False)
