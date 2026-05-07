"""
Inbox: paginated list of received messages with nickname, date, preview.
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)
from aiogram.utils.i18n import gettext as _
from aiogram.utils.i18n import lazy_gettext as __

from bot.functions import InboxCB
from database.functions import (
    get_or_create_anon_session,
    get_recent_messages_for_user,
    get_received_count,
    is_user_premium,
)
from database.session import get_db_session

inbox_router = Router()

FREE_LIMIT = 10


async def _build_inbox_page(
    user_id: int, page: int, is_premium: bool
) -> tuple[str, InlineKeyboardMarkup]:
    """Returns (text, keyboard) for the given inbox page."""
    session = await get_db_session()
    limit = 999 if is_premium else FREE_LIMIT
    messages = await get_recent_messages_for_user(session, user_id, limit=limit)
    total = await get_received_count(session, user_id)

    page_size = 5
    start = page * page_size
    page_msgs = messages[start: start + page_size]

    if not page_msgs:
        await session.close()
        return _("📭 Your inbox is empty."), InlineKeyboardMarkup(inline_keyboard=[])

    lines = [_("📥 <b>Your Inbox</b>  (page {p}/{total_pages})\n").format(
        p=page + 1,
        total_pages=max(1, (len(messages) + page_size - 1) // page_size),
    )]

    for i, msg in enumerate(page_msgs, start=start + 1):
        nickname = await get_or_create_anon_session(session, msg.sender_id, user_id)
        preview = (msg.text or f"[{msg.message_type}]")[:50].replace("\n", " ")
        date_str = msg.created_at.strftime("%d %b %H:%M")
        read_icon = "✅" if msg.is_read else "🆕"
        lines.append(f"{read_icon} <b>{nickname}</b>\n   {preview}\n   <i>{date_str}</i>\n")

    await session.close()

    text = "\n".join(lines)

    if not is_premium and total > FREE_LIMIT:
        text += _("\n\n⭐ <i>Showing {shown} of {total} messages. "
                  "Upgrade to Premium to see all.</i>").format(shown=FREE_LIMIT, total=total)

    # Pagination buttons
    total_pages = max(1, (len(messages) + page_size - 1) // page_size)
    nav_row: list[InlineKeyboardButton] = []

    if page > 0:
        nav_row.append(
            InlineKeyboardButton(text="⬅️", callback_data=InboxCB(page=page - 1).pack())
        )
    if page < total_pages - 1:
        nav_row.append(
            InlineKeyboardButton(text="➡️", callback_data=InboxCB(page=page + 1).pack())
        )

    keyboard_rows: list[list[InlineKeyboardButton]] = []
    if nav_row:
        keyboard_rows.append(nav_row)

    keyboard_rows.append([
        InlineKeyboardButton(text=_("🔄 Refresh"), callback_data=InboxCB(page=page).pack())
    ])

    return text, InlineKeyboardMarkup(inline_keyboard=keyboard_rows)


@inbox_router.message(F.text == __("📥 Inbox"))
@inbox_router.message(Command("inbox"))
async def inbox_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    code = data.get("locale")
    await state.clear()
    await state.update_data(user_id=message.from_user.id, locale=code)

    session = await get_db_session()
    is_premium = await is_user_premium(session, message.from_user.id)
    await session.close()

    text, keyboard = await _build_inbox_page(message.from_user.id, page=0, is_premium=is_premium)
    await message.answer(text, reply_markup=keyboard)


@inbox_router.callback_query(InboxCB.filter())
async def inbox_page_callback(callback: CallbackQuery, callback_data: InboxCB):
    session = await get_db_session()
    is_premium = await is_user_premium(session, callback.from_user.id)
    await session.close()

    text, keyboard = await _build_inbox_page(
        callback.from_user.id, page=callback_data.page, is_premium=is_premium
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()
