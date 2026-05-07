"""
Admin panel: stats, broadcast, ban/unban, admin management, reports.
"""
import asyncio

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)
from aiogram.utils.i18n import gettext as _
from aiogram.utils.markdown import hbold, hcode

from bot.functions import AdminCB, AdminStates
from database.functions import (
    add_admin,
    ban_user,
    get_all_user_ids,
    get_comments_today,
    get_message_by_id,
    get_messages_this_week,
    get_messages_today,
    get_most_active_sender,
    get_recent_reports,
    get_total_comments,
    get_total_messages,
    get_total_premium_users,
    get_total_reports,
    get_total_users,
    get_user_by_id,
    get_users_this_week,
    get_users_today,
    list_admins,
    remove_admin,
    unban_user,
)
from database.session import get_db_session
from utils.config import MainConfig

admin_router = Router()
SUPER_ADMIN = MainConfig.admin.SUPER_ADMIN_IDS


def _is_super(user_id: int) -> bool:
    return user_id in SUPER_ADMIN


def _admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Stats", callback_data=AdminCB(action="stats").pack()),
            InlineKeyboardButton(text="📢 Broadcast", callback_data=AdminCB(action="bcast").pack()),
        ],
        [
            InlineKeyboardButton(text="➕ Add Admin", callback_data=AdminCB(action="add").pack()),
            InlineKeyboardButton(text="➖ Remove Admin", callback_data=AdminCB(action="remove").pack()),
        ],
        [
            InlineKeyboardButton(text="📋 List Admins", callback_data=AdminCB(action="list").pack()),
            InlineKeyboardButton(text="⚠️ Reports", callback_data=AdminCB(action="reports").pack()),
        ],
        [
            InlineKeyboardButton(text="🔨 Ban User", callback_data=AdminCB(action="ban").pack()),
            InlineKeyboardButton(text="✅ Unban User", callback_data=AdminCB(action="unban").pack()),
        ],
        [
            InlineKeyboardButton(text="🔍 User Lookup", callback_data=AdminCB(action="lookup").pack()),
        ],
    ])


@admin_router.message(Command("admin"))
async def admin_panel_handler(message: Message):
    if not _is_super(message.from_user.id):
        await message.answer("⛔ Not authorized.")
        return
    await message.answer(
        "👑 <b>Admin Panel</b>",
        reply_markup=_admin_panel_keyboard(),
    )


# ── Stats ─────────────────────────────────────────────────────────────────────

@admin_router.callback_query(AdminCB.filter(F.action == "stats"))
async def stats_handler(callback: CallbackQuery):
    if not _is_super(callback.from_user.id):
        await callback.answer("Not allowed.", show_alert=True)
        return

    session = await get_db_session()
    total_users = await get_total_users(session)
    users_today = await get_users_today(session)
    users_week = await get_users_this_week(session)
    total_msgs = await get_total_messages(session)
    msgs_today = await get_messages_today(session)
    msgs_week = await get_messages_this_week(session)
    most_active = await get_most_active_sender(session)
    total_comments = await get_total_comments(session)
    comments_today = await get_comments_today(session)
    total_premium = await get_total_premium_users(session)
    total_reports = await get_total_reports(session)
    await session.close()

    most_active_text = (
        f"🥇 <b>Most Active Sender</b>\n"
        f"   └ ID: {hcode(most_active['sender_id'])}\n"
        f"   └ Messages: <b>{most_active['message_count']}</b>\n"
    ) if most_active else "🥇 No data yet\n"

    text = (
        "📊 <b>BOT STATISTICS</b>\n"
        "━━━━━━━━━━━━━━━━\n\n"
        "👥 <b>Users</b>\n"
        f"   ├ Total: <b>{total_users}</b>\n"
        f"   ├ Today: <b>{users_today}</b>\n"
        f"   └ This week: <b>{users_week}</b>\n\n"
        "💌 <b>Messages</b>\n"
        f"   ├ Total: <b>{total_msgs}</b>\n"
        f"   ├ Today: <b>{msgs_today}</b>\n"
        f"   └ This week: <b>{msgs_week}</b>\n\n"
        f"{most_active_text}\n"
        "💬 <b>Comments</b>\n"
        f"   ├ Total: <b>{total_comments}</b>\n"
        f"   └ Today: <b>{comments_today}</b>\n\n"
        "⭐ <b>Premium users:</b> <b>{prem}</b>\n"
        "⚠️ <b>Total reports:</b> <b>{rep}</b>\n"
        "━━━━━━━━━━━━━━━━"
    ).format(prem=total_premium, rep=total_reports)

    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


# ── Broadcast ─────────────────────────────────────────────────────────────────

@admin_router.callback_query(AdminCB.filter(F.action == "bcast"))
async def broadcast_prompt(callback: CallbackQuery, state: FSMContext):
    if not _is_super(callback.from_user.id):
        await callback.answer("Not allowed.", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(
        "📢 Send the message you want to broadcast to all users.\n"
        "It will be forwarded as-is (text, photo, video, etc.).\n\n"
        "Type /cancel to abort."
    )
    await state.set_state(AdminStates.waiting_for_broadcast)


@admin_router.message(AdminStates.waiting_for_broadcast)
async def do_broadcast(message: Message, state: FSMContext):
    if not _is_super(message.from_user.id):
        return

    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("❌ Broadcast cancelled.")
        return

    await state.clear()
    session = await get_db_session()
    user_ids = await get_all_user_ids(session)
    await session.close()

    success = 0
    failed = 0
    status_msg = await message.answer(f"📢 Broadcasting to {len(user_ids)} users...")

    for uid in user_ids:
        try:
            await message.copy_to(chat_id=uid)
            success += 1
        except Exception:
            failed += 1
        if (success + failed) % 50 == 0:
            await asyncio.sleep(0.05)  # mild flood control

    await status_msg.edit_text(
        f"📢 Broadcast complete!\n✅ Delivered: {success}\n❌ Failed: {failed}"
    )


# ── Admin management ──────────────────────────────────────────────────────────

@admin_router.callback_query(AdminCB.filter(F.action == "add"))
async def add_admin_prompt(callback: CallbackQuery, state: FSMContext):
    if not _is_super(callback.from_user.id):
        await callback.answer("Not allowed.", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer("Send the Telegram ID of the user to add as admin.")
    await state.set_state(AdminStates.waiting_for_add_admin)


@admin_router.message(AdminStates.waiting_for_add_admin)
async def do_add_admin(message: Message, state: FSMContext):
    if not _is_super(message.from_user.id):
        return
    if not message.text or not message.text.strip().lstrip("-").isdigit():
        await message.answer("❌ Invalid ID.")
        return
    admin_id = int(message.text.strip())
    session = await get_db_session()
    await add_admin(session, admin_id)
    await session.close()
    await state.clear()
    await message.answer(f"✅ Admin {hcode(admin_id)} added.")


@admin_router.callback_query(AdminCB.filter(F.action == "remove"))
async def remove_admin_prompt(callback: CallbackQuery, state: FSMContext):
    if not _is_super(callback.from_user.id):
        await callback.answer("Not allowed.", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer("Send the Telegram ID of the admin to remove.")
    await state.set_state(AdminStates.waiting_for_remove_admin)


@admin_router.message(AdminStates.waiting_for_remove_admin)
async def do_remove_admin(message: Message, state: FSMContext):
    if not _is_super(message.from_user.id):
        return
    if not message.text or not message.text.strip().lstrip("-").isdigit():
        await message.answer("❌ Invalid ID.")
        return
    admin_id = int(message.text.strip())
    session = await get_db_session()
    removed = await remove_admin(session, admin_id)
    await session.close()
    await state.clear()
    if removed:
        await message.answer(f"✅ Admin {hcode(admin_id)} removed.")
    else:
        await message.answer("❌ Admin not found.")


@admin_router.callback_query(AdminCB.filter(F.action == "list"))
async def list_admins_handler(callback: CallbackQuery):
    if not _is_super(callback.from_user.id):
        await callback.answer("Not allowed.", show_alert=True)
        return

    session = await get_db_session()
    admins = await list_admins(session)
    await session.close()

    text = "👑 <b>Admin Panel</b>\n\n"
    text += "👑 <b>Super Admins:</b>\n"
    for aid in SUPER_ADMIN:
        text += f"   └ {hcode(aid)}\n"
    text += "\n🛡 <b>Admins:</b>\n"
    if admins:
        for a in admins:
            text += f"   └ {hcode(a.telegram_id)}\n"
    else:
        text += "   └ No additional admins\n"

    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


# ── Ban / Unban ───────────────────────────────────────────────────────────────

@admin_router.callback_query(AdminCB.filter(F.action == "ban"))
async def ban_prompt(callback: CallbackQuery, state: FSMContext):
    if not _is_super(callback.from_user.id):
        await callback.answer("Not allowed.", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer("Send the Telegram ID of the user to ban.")
    await state.set_state(AdminStates.waiting_for_ban)


@admin_router.message(AdminStates.waiting_for_ban)
async def do_ban(message: Message, state: FSMContext):
    if not _is_super(message.from_user.id):
        return
    if not message.text or not message.text.strip().lstrip("-").isdigit():
        await message.answer("❌ Invalid ID.")
        return
    target_id = int(message.text.strip())
    session = await get_db_session()
    await ban_user(session, target_id)
    await session.close()
    await state.clear()
    await message.answer(f"🔨 User {hcode(target_id)} banned.")
    try:
        await message.bot.send_message(
            chat_id=target_id,
            text="🚫 You have been banned from AnonBot.",
        )
    except Exception:
        pass


@admin_router.callback_query(AdminCB.filter(F.action == "unban"))
async def unban_prompt(callback: CallbackQuery, state: FSMContext):
    if not _is_super(callback.from_user.id):
        await callback.answer("Not allowed.", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer("Send the Telegram ID of the user to unban.")
    await state.set_state(AdminStates.waiting_for_unban)


@admin_router.message(AdminStates.waiting_for_unban)
async def do_unban(message: Message, state: FSMContext):
    if not _is_super(message.from_user.id):
        return
    if not message.text or not message.text.strip().lstrip("-").isdigit():
        await message.answer("❌ Invalid ID.")
        return
    target_id = int(message.text.strip())
    session = await get_db_session()
    await unban_user(session, target_id)
    await session.close()
    await state.clear()
    await message.answer(f"✅ User {hcode(target_id)} unbanned.")


# ── Reports ───────────────────────────────────────────────────────────────────

@admin_router.callback_query(AdminCB.filter(F.action == "reports"))
async def view_reports(callback: CallbackQuery):
    if not _is_super(callback.from_user.id):
        await callback.answer("Not allowed.", show_alert=True)
        return

    session = await get_db_session()
    reports = await get_recent_reports(session, limit=10)
    await session.close()

    if not reports:
        await callback.message.answer("⚠️ No reports yet.")
        await callback.answer()
        return

    text = "⚠️ <b>Recent Reports (last 10)</b>\n\n"
    for r in reports:
        text += (
            f"• ID {hcode(r.id)} — msg {hcode(r.message_id)} "
            f"— reporter {hcode(r.reporter_id)}\n"
            f"  <i>{r.created_at.strftime('%d %b %H:%M')}</i>\n"
        )

    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


# ── User lookup ───────────────────────────────────────────────────────────────

@admin_router.callback_query(AdminCB.filter(F.action == "lookup"))
async def lookup_prompt(callback: CallbackQuery, state: FSMContext):
    if not _is_super(callback.from_user.id):
        await callback.answer("Not allowed.", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer("Send the Telegram ID to look up.")
    await state.set_state(AdminStates.waiting_for_lookup)


@admin_router.message(AdminStates.waiting_for_lookup)
async def do_lookup(message: Message, state: FSMContext):
    if not _is_super(message.from_user.id):
        return
    if not message.text or not message.text.strip().lstrip("-").isdigit():
        await message.answer("❌ Invalid ID.")
        return
    target_id = int(message.text.strip())
    session = await get_db_session()
    user = await get_user_by_id(session, target_id)
    await session.close()
    await state.clear()

    if not user:
        await message.answer(f"❌ User {hcode(target_id)} not found.")
        return

    await message.answer(
        f"🔍 <b>User Info</b>\n\n"
        f"ID: {hcode(user.telegram_id)}\n"
        f"Name: {user.first_name or ''} {user.last_name or ''}\n"
        f"Username: @{user.user_name or 'none'}\n"
        f"Joined: {user.joined_date.strftime('%d %b %Y')}\n"
        f"Profile: <a href='tg://user?id={user.telegram_id}'>Open</a>",
        parse_mode="HTML",
    )
