import asyncio
import html
import logging

from aiogram import F
from aiogram import Router
from aiogram.filters import Command
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import I18n
from aiogram.utils.i18n import gettext as _
from aiogram.utils.i18n import lazy_gettext as __
from aiogram.utils.markdown import hbold

from bot.functions import make_reply_button, make_back_button, UserStates, make_language_button, LanguageStates
from bot.functions.make_inline_button import make_inline_button
from bot.functions.nicknames import make_nickname
from bot.handlers.functions import send_comment_to_admin_group
from database.functions import *
from database.session import get_db_session

main = Router()
log = logging.getLogger(__name__)

SUPER_ADMIN = [7634998249]

WELCOME_MESSAGE_MAX_LEN = 300
BROADCAST_RATE_DELAY = 0.05  # seconds between sends (≈20 msg/s)


# ---------- Menu helpers ----------

async def _show_main_menu(message, state: FSMContext, greeting: str | None = None):
    """Clear state, preserve locale, and render the main menu keyboard."""
    data = await state.get_data()
    user_id = message.from_user.id
    code = data.get("locale")

    await state.clear()
    await state.update_data(user_id=user_id, locale=code)

    main_menu = [
        _("🔗 Create a link"),
        _("💬 Comments and Offers"),
        _("ℹ️ About bot"),
        _("⚙️ Settings"),
    ]
    keyboard = await make_reply_button(main_menu, [1, 2, 1])
    await message.answer(greeting or _("Welcome back to the Main Menu 🏠"), reply_markup=keyboard)


async def _show_settings_menu(message, state: FSMContext, greeting: str | None = None):
    """Render the settings sub-menu without altering FSM state."""
    settings_menu = [
        _("✏️ My welcome message"),
        _("📊 My stats"),
        _("🚫 Blocked users"),
        _("🌐 Language 🇺🇸/🇺🇿/🇷🇺"),
        _("🔙 Back to menu"),
    ]
    keyboard = await make_reply_button(settings_menu, [1, 2, 1, 1])
    await message.answer(greeting or _("⚙️ Settings"), reply_markup=keyboard)


# ---------- /start ----------

@main.message(CommandStart())
async def start_handler(message, command: CommandStart.commands, state: FSMContext):
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    joined_date = datetime.now(timezone.utc)

    async with get_db_session() as session:
        await insert_user(session, telegram_id, username, first_name, last_name, joined_date)
        db_locale = await get_user_locale(session, telegram_id)

    if db_locale:
        await state.update_data(locale=db_locale)

    if command.args:
        arg = command.args.strip()
        receiver_id: int | None = None

        if arg.isdigit():
            # Legacy bare-ID link — kept working so previously-shared URLs don't break.
            receiver_id = int(arg)
        else:
            async with get_db_session() as session:
                receiver_id = await resolve_link_token(session, arg)

        if receiver_id is None:
            await message.answer(_("❌ Invalid link!"))
            return

        async with get_db_session() as session:
            welcome = await get_welcome_message(session, receiver_id)

        await state.update_data(receiver_id=receiver_id)
        back_keyboard = await make_back_button()

        if welcome:
            await message.answer(
                _("💬 Welcome message from this user:\n\n{text}").format(
                    text=html.escape(welcome)
                ),
                reply_markup=back_keyboard,
            )
        else:
            await message.answer(
                _("You are now sending an anonymous message to this user 💌.\n"
                  "Type your message below:"),
                reply_markup=back_keyboard,
            )
        await state.set_state(UserStates.waiting_for_message)
    else:
        await _show_main_menu(message, state, greeting=_("Welcome to Anonymous chat bot!"))


@main.message(Command("cancel"))
async def cancel_handler(message, state: FSMContext):
    await _show_main_menu(message, state)


# ---------- Main menu items ----------

@main.message(F.text == __("🔗 Create a link"))
async def create_link_handler(message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    code = data.get("locale")
    await state.clear()
    await state.update_data(user_id=user_id, locale=code)

    async with get_db_session() as session:
        token = await get_or_create_default_link_token(session, user_id)

    bot_username = (await message.bot.get_me()).username
    unique_link = f"https://t.me/{bot_username}?start={token}"

    await message.answer(_("Your unique link has been created! 💫"))
    await message.answer(_("📎 Send this link to others so they can message you anonymously 💌✨:"))
    await message.answer(unique_link)


@main.message(F.text == __("ℹ️ About bot"))
async def about_handler(message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    code = data.get("locale")
    await state.clear()
    await state.update_data(user_id=user_id, locale=code)

    text = _("ℹ️ About This Bot\n\n"
             "1️⃣ This bot lets people send anonymous messages to others via a personal link 💌\n\n"
             "2️⃣ All sender information is kept private 👤\n\n"
             "3️⃣ Messages are delivered instantly and securely ⚡️🔒\n\n"
             "4️⃣ Please avoid offensive or curse words while sending messages 🤬\n\n"
             "5️⃣ Enjoy sending and receiving anonymous messages safely 🥂")

    await message.answer(text=text)


@main.message(F.text == __("💬 Comments and Offers"))
async def comment_handler(message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    code = data.get("locale")
    await state.clear()
    await state.update_data(user_id=user_id, locale=code)

    back_button = await make_back_button()
    await message.answer(
        _("Please type your comment below 💬. Press 'Back ◀️' to go to the main menu."),
        reply_markup=back_button,
    )

    await state.set_state(UserStates.waiting_for_comment)


@main.message(UserStates.waiting_for_comment, F.text != __("Back ◀️"))
async def receive_comment(message):
    telegram_id = message.from_user.id
    comment = message.text

    async with get_db_session() as session:
        await insert_comment(session, telegram_id, comment)

    await send_comment_to_admin_group(
        bot=message.bot,
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        first_name=message.from_user.first_name or "",
        last_name=message.from_user.last_name or "",
        comment_text=comment,
    )

    await message.answer(_("Thank you for your comment 💬! Feel free to add another one 😁."))


@main.message(UserStates.waiting_for_comment, F.text == __("Back ◀️"))
async def back_from_comment_handler(message, state: FSMContext):
    await _show_main_menu(message, state)


@main.message(UserStates.waiting_for_message, F.text == __("Back ◀️"))
async def back_from_sending_handler(message, state: FSMContext):
    await _show_main_menu(message, state)


# ---------- Settings sub-menu ----------

@main.message(F.text == __("⚙️ Settings"))
async def settings_handler(message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    code = data.get("locale")
    await state.clear()
    await state.update_data(user_id=user_id, locale=code)
    await _show_settings_menu(message, state)


@main.message(F.text == __("🔙 Back to menu"))
async def back_to_main_handler(message, state: FSMContext):
    await _show_main_menu(message, state)


# ---------- Welcome message editing ----------

@main.message(F.text == __("✏️ My welcome message"))
async def welcome_message_handler(message, state: FSMContext):
    user_id = message.from_user.id
    async with get_db_session() as session:
        current = await get_welcome_message(session, user_id)

    if current:
        preview = _("Current welcome:\n\n{text}\n\nSend new text to replace it, "
                    "tap 🗑 Clear to remove it, or 🔙 Back to menu to cancel.").format(
            text=html.escape(current)
        )
    else:
        preview = _("You don't have a welcome message yet. Send some text "
                    "(up to {n} chars) to set one, or 🔙 Back to menu to cancel.").format(
            n=WELCOME_MESSAGE_MAX_LEN
        )

    keyboard = await make_reply_button(
        [_("🗑 Clear"), _("🔙 Back to menu")],
        [2],
    )
    await message.answer(preview, reply_markup=keyboard)
    await state.set_state(UserStates.waiting_for_welcome_message)


@main.message(UserStates.waiting_for_welcome_message, F.text == __("🗑 Clear"))
async def clear_welcome_message(message, state: FSMContext):
    async with get_db_session() as session:
        await set_welcome_message(session, message.from_user.id, None)
    await _show_settings_menu(message, state, greeting=_("✅ Welcome message cleared."))
    data = await state.get_data()
    user_id = message.from_user.id
    code = data.get("locale")
    await state.clear()
    await state.update_data(user_id=user_id, locale=code)


@main.message(UserStates.waiting_for_welcome_message, F.text == __("🔙 Back to menu"))
async def cancel_welcome_message_edit(message, state: FSMContext):
    await _show_main_menu(message, state)


@main.message(UserStates.waiting_for_welcome_message)
async def save_welcome_message(message, state: FSMContext):
    text = (message.text or "").strip()
    if not text:
        await message.answer(_("❌ Please send text only (no media)."))
        return
    if len(text) > WELCOME_MESSAGE_MAX_LEN:
        await message.answer(_("❌ Too long. Max {n} characters.").format(n=WELCOME_MESSAGE_MAX_LEN))
        return

    async with get_db_session() as session:
        await set_welcome_message(session, message.from_user.id, text)

    data = await state.get_data()
    user_id = message.from_user.id
    code = data.get("locale")
    await state.clear()
    await state.update_data(user_id=user_id, locale=code)
    await _show_settings_menu(
        message,
        state,
        greeting=_("✅ Welcome message saved:\n\n{text}").format(text=html.escape(text)),
    )


# ---------- Personal stats ----------

@main.message(F.text == __("📊 My stats"))
async def my_stats_handler(message, state: FSMContext):
    user_id = message.from_user.id
    async with get_db_session() as session:
        received = await get_user_received_count(session, user_id)
        received_week = await get_user_received_this_week(session, user_id)
        sent = await get_user_sent_count(session, user_id)
        sent_week = await get_user_sent_this_week(session, user_id)
        unique_senders = await get_user_unique_senders_count(session, user_id)
        top_sender = await get_user_top_sender(session, user_id)

    if top_sender:
        top_handle = make_nickname(top_sender["sender_id"], user_id)
        top_sender_line = _("   └ Top sender: <b>{handle}</b> ({n} messages)").format(
            handle=top_handle, n=top_sender["count"]
        )
    else:
        top_sender_line = _("   └ Top sender: —")

    text = (
        _("📊 <b>Your stats</b>") + "\n"
        + "━━━━━━━━━━━━━━━━━━\n\n"
        + _("📥 <b>Received</b>") + "\n"
        + _("   ├ This week: <b>{n}</b>").format(n=received_week) + "\n"
        + _("   └ All time: <b>{n}</b>").format(n=received) + "\n\n"
        + _("📤 <b>Sent</b>") + "\n"
        + _("   ├ This week: <b>{n}</b>").format(n=sent_week) + "\n"
        + _("   └ All time: <b>{n}</b>").format(n=sent) + "\n\n"
        + _("👥 <b>People</b>") + "\n"
        + _("   ├ Unique senders: <b>{n}</b>").format(n=unique_senders) + "\n"
        + top_sender_line + "\n"
    )
    await message.answer(text, parse_mode="HTML")


# ---------- Blocked users ----------

@main.message(F.text == __("🚫 Blocked users"))
async def blocked_users_handler(message, state: FSMContext):
    blocker_id = message.from_user.id
    async with get_db_session() as session:
        blocked_ids = await list_blocks_for(session, blocker_id)

    if not blocked_ids:
        await message.answer(_("You haven't blocked anyone yet."))
        return

    rows = []
    for bid in blocked_ids:
        handle = make_nickname(bid, blocker_id)
        rows.append([InlineKeyboardButton(
            text=_("❎ Unblock {handle}").format(handle=handle),
            callback_data=f"unblk:{bid}",
        )])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await message.answer(_("Your blocked users:"), reply_markup=kb)


@main.callback_query(F.data.startswith("unblk:"))
async def unblock_callback(callback: CallbackQuery):
    try:
        blocked_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer(_("❌ Invalid action."), show_alert=True)
        return

    blocker_id = callback.from_user.id
    async with get_db_session() as session:
        removed = await remove_block(session, blocker_id, blocked_id)

    if removed:
        await callback.answer(_("✅ Unblocked."), show_alert=False)
        # Remove the row from the keyboard by editing it.
        try:
            old_kb = callback.message.reply_markup
            if old_kb:
                new_rows = [
                    row for row in old_kb.inline_keyboard
                    if not any(btn.callback_data == callback.data for btn in row)
                ]
                if new_rows:
                    await callback.message.edit_reply_markup(
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=new_rows)
                    )
                else:
                    await callback.message.edit_text(_("You haven't blocked anyone yet."))
        except Exception as e:
            log.warning("Failed to edit unblock keyboard: %s", e)
    else:
        await callback.answer(_("This user wasn't on your block list."), show_alert=True)


# ---------- Language (now under Settings, but still triggered by the same label) ----------

@main.message(F.text == __("🌐 Language 🇺🇸/🇺🇿/🇷🇺"))
async def language_handler(message, state: FSMContext):
    keyboard = await make_language_button()
    await state.set_state(LanguageStates.language)
    await message.answer(_("🌐 Please choose your preferred language"), reply_markup=keyboard)


@main.message(LanguageStates.language, F.text == __("Back 🔙"))
async def back_from_language_handler(message, state: FSMContext):
    await _show_main_menu(message, state)


@main.message(LanguageStates.language, F.text != __("Back 🔙"))
async def change_language_handler(message, state: FSMContext, i18n: I18n):
    lang = {
        "🇺🇸 English": "en",
        "🇷🇺 Русский": "ru",
        "🇺🇿 O'zbekcha": "uz",
    }
    code = lang.get((message.text or "").strip())

    if not code:
        await message.answer(_("❌ Invalid language selection! Please choose a valid language 🌐"))
        return

    await state.update_data(locale=code)
    async with get_db_session() as session:
        await set_user_locale(session, message.from_user.id, code)

    with i18n.use_locale(code):
        await _show_main_menu(message, state, greeting=_("Language has been changed 😀"))


# ---------- Admin panel ----------

@main.message(Command("admin"))
async def admin_panel_handler(message):
    user_id = message.from_user.id

    if user_id not in SUPER_ADMIN:
        await message.answer(_("⛔ You are not authorized."))
        return

    buttons = [
        _("➕ Add Admin"),
        _("➖ Remove Admin"),
        _("📋 See All Admins"),
        _("📊 Bot Statistics"),
        _("📢 Broadcast"),
    ]
    keyboard = await make_inline_button(buttons, [1, 2, 1, 1])
    await message.answer(_("Welcome to the Admin panel"), reply_markup=keyboard)


@main.callback_query(F.data == "➕")
async def add_admin_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in SUPER_ADMIN:
        await callback.answer(_("Not allowed"), show_alert=True)
        return

    await callback.message.answer(_("Send the id of the user you want to add as admin"))
    await state.set_state(UserStates.waiting_for_add_admin)
    await callback.answer()


@main.message(UserStates.waiting_for_add_admin)
async def add_admin_input_handler(message, state: FSMContext):
    admin_id = (message.text or "").strip()

    if not admin_id.isdigit():
        await message.answer(_("❌ Invalid ID! Please send a numeric Telegram ID."))
        return

    admin_id = int(admin_id)

    async with get_db_session() as session:
        await add_admin(session, telegram_id=admin_id)

    await message.answer(_("✅ Admin has been added successfully!"))
    await state.clear()


@main.callback_query(F.data == "➖")
async def remove_admin_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in SUPER_ADMIN:
        await callback.answer(_("Not allowed"), show_alert=True)
        return

    await callback.message.answer(_("Send the id of the user you want to remove as admin"))
    await state.set_state(UserStates.waiting_for_remove_admin)
    await callback.answer()


@main.message(UserStates.waiting_for_remove_admin)
async def remove_admin_input_handler(message, state: FSMContext):
    admin_id = (message.text or "").strip()

    if not admin_id.isdigit():
        await message.answer(_("❌ Invalid ID! Please send a numeric Telegram ID."))
        return

    admin_id = int(admin_id)

    async with get_db_session() as session:
        removed = await remove_admin(session, telegram_id=admin_id)

    if removed:
        await message.answer(_("✅ Admin has been removed successfully!"))
    else:
        await message.answer(_("❌ Admin does not exist."))

    await state.clear()


@main.callback_query(F.data == "📋")
async def show_admins_handler(callback: CallbackQuery):
    if callback.from_user.id not in SUPER_ADMIN:
        await callback.answer(_("Not allowed"), show_alert=True)
        return

    async with get_db_session() as session:
        admins = await list_admins(session)

    text = _("👑 <b>ADMIN PANEL</b>") + "\n\n"
    text += _("👑 <b>Super Admins:</b>") + "\n"
    for admin in SUPER_ADMIN:
        text += f"   └ <code>{admin}</code>\n"

    text += "\n" + _("🛡 <b>Admins:</b>") + "\n"
    if admins:
        for admin in admins:
            text += f"   └ <code>{admin.telegram_id}</code>\n"
    else:
        text += "   └ " + _("No additional admins") + "\n"

    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


def _stats_user_label(row: dict) -> str:
    first = row.get("first_name")
    uname = row.get("user_name")
    uid = row["user_id"]
    if first:
        uname_part = f" (@{html.escape(uname)})" if uname else ""
        return f"<b>{html.escape(first)}</b>{uname_part} <code>{uid}</code>"
    if uname:
        return f"<b>@{html.escape(uname)}</b> <code>{uid}</code>"
    return f"<code>{uid}</code>"


def _stats_pct(num: int, denom: int) -> int:
    return (num * 100 // denom) if denom else 0


@main.callback_query(F.data == "📊")
async def show_statistics_handler(callback: CallbackQuery):
    if callback.from_user.id not in SUPER_ADMIN:
        await callback.answer(_("Not allowed"), show_alert=True)
        return

    async with get_db_session() as session:
        total_users = await get_total_users(session)
        users_today = await get_users_today(session)
        users_week = await get_users_this_week(session)

        new_per_day = await get_new_users_per_day(session, days=7)
        activation = await get_activation_rate(session)
        cohort = await get_cohort_activation(session, days=7)

        total_messages = await get_total_messages(session)
        messages_today = await get_messages_today(session)
        messages_week = await get_messages_this_week(session)

        top_senders = await get_top_senders_week(session, limit=3)
        top_receivers = await get_top_receivers_week(session, limit=3)
        top_viral = await get_top_viral_users(session, limit=3)

        locales = await get_locale_distribution(session)

        total_comments = await get_total_comments(session)
        comments_today = await get_comments_today(session)

    # 7-day bar chart (monospace block)
    chart_counts = [c for (_d, c) in new_per_day]
    chart_max = max(chart_counts) if chart_counts else 0
    chart_rows = []
    for day, count in new_per_day:
        bar_len = int(round(count / chart_max * 10)) if chart_max else 0
        bar = "▮" * bar_len
        chart_rows.append(f"{day.strftime('%m-%d')}  {bar:<10}  {count}")
    chart_block = "<pre>" + "\n".join(chart_rows) + "</pre>"

    # Top-N renderer
    def render_top(items, count_key, count_word):
        if not items:
            return "   └ " + _("No data yet")
        return "\n".join(
            f"   {i + 1}. {_stats_user_label(row)} — <b>{row[count_key]}</b> {count_word}"
            for i, row in enumerate(items)
        )

    senders_block = render_top(top_senders, "count", _("msgs"))
    receivers_block = render_top(top_receivers, "count", _("msgs"))
    viral_block = render_top(top_viral, "hits", _("hits"))

    # Locale block
    flag_map = {"en": "🇬🇧", "ru": "🇷🇺", "uz": "🇺🇿"}
    if locales:
        locale_lines = [
            f"   ├ {flag_map.get(code, '🌐')} <b>{html.escape(code)}</b>: {n}"
            for code, n in locales
        ]
        locale_lines[-1] = locale_lines[-1].replace("├", "└", 1)
        locale_block = "\n".join(locale_lines)
    else:
        locale_block = "   └ " + _("No data yet")

    activation_pct = _stats_pct(activation["active"], activation["total"])
    cohort_pct = _stats_pct(cohort["activated"], cohort["cohort"])

    text = (
        _("📊 <b>BOT STATISTICS DASHBOARD</b>") + "\n"
        + "━━━━━━━━━━━━━━━━━━\n\n"
        + _("👥 <b>Users</b>") + "\n"
        + _("   ├ Total: <b>{n}</b>").format(n=total_users) + "\n"
        + _("   ├ Joined Today: <b>{n}</b>").format(n=users_today) + "\n"
        + _("   ├ Joined This Week: <b>{n}</b>").format(n=users_week) + "\n"
        + _("   └ Activation: <b>{a}</b>/<b>{t}</b> (<b>{p}%</b>)").format(
            a=activation["active"], t=activation["total"], p=activation_pct
        ) + "\n\n"
        + _("📈 <b>New Users (last 7 days)</b>") + "\n"
        + chart_block + "\n\n"
        + _("🌱 <b>Weekly Cohort Activation</b>") + "\n"
        + _("   └ Joined last 7d: <b>{c}</b>, activated: <b>{a}</b> (<b>{p}%</b>)").format(
            c=cohort["cohort"], a=cohort["activated"], p=cohort_pct
        ) + "\n\n"
        + _("💌 <b>Messages</b>") + "\n"
        + _("   ├ Total: <b>{n}</b>").format(n=total_messages) + "\n"
        + _("   ├ Sent Today: <b>{n}</b>").format(n=messages_today) + "\n"
        + _("   └ Sent This Week: <b>{n}</b>").format(n=messages_week) + "\n\n"
        + _("🔥 <b>Top Senders (this week)</b>") + "\n"
        + senders_block + "\n\n"
        + _("⭐ <b>Top Receivers (this week)</b>") + "\n"
        + receivers_block + "\n\n"
        + _("🦠 <b>Most Viral Links (all-time clicks)</b>") + "\n"
        + viral_block + "\n\n"
        + _("🌍 <b>Languages</b>") + "\n"
        + locale_block + "\n\n"
        + _("💬 <b>Comments</b>") + "\n"
        + _("   ├ Total: <b>{n}</b>").format(n=total_comments) + "\n"
        + _("   └ Today: <b>{n}</b>").format(n=comments_today) + "\n\n"
        + "━━━━━━━━━━━━━━━━━━"
    )

    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


# ---------- Broadcast flow ----------

@main.callback_query(F.data == "📢")
async def broadcast_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in SUPER_ADMIN:
        await callback.answer(_("Not allowed"), show_alert=True)
        return

    await callback.message.answer(_("Send the broadcast message text:"))
    await state.set_state(UserStates.waiting_for_broadcast)
    await callback.answer()


@main.message(UserStates.waiting_for_broadcast)
async def broadcast_input_handler(message, state: FSMContext):
    if message.from_user.id not in SUPER_ADMIN:
        await state.clear()
        return

    text = (message.text or message.caption or "").strip()
    if not text:
        await message.answer(_("❌ Please send text only."))
        return

    async with get_db_session() as session:
        all_ids = await get_all_user_ids(session)
    count = len(all_ids)

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=_("✅ Send"), callback_data="bcast:ok"),
        InlineKeyboardButton(text=_("❌ Cancel"), callback_data="bcast:no"),
    ]])
    await state.update_data(broadcast_text=text, broadcast_count=count)
    await message.answer(
        _("📢 <b>Broadcast preview:</b>\n\n{text}\n\nSend to <b>{n}</b> users?").format(
            text=html.escape(text), n=count
        ),
        parse_mode="HTML",
        reply_markup=confirm_kb,
    )
    await state.set_state(UserStates.confirming_broadcast)


@main.callback_query(UserStates.confirming_broadcast, F.data == "bcast:no")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(_("❌ Broadcast cancelled."))
    await callback.answer()


@main.callback_query(UserStates.confirming_broadcast, F.data == "bcast:ok")
async def broadcast_send(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in SUPER_ADMIN:
        await callback.answer(_("Not allowed"), show_alert=True)
        return

    data = await state.get_data()
    text = data.get("broadcast_text", "")
    await state.clear()

    if not text:
        await callback.message.edit_text(_("❌ No broadcast text found."))
        await callback.answer()
        return

    await callback.message.edit_text(_("📡 Broadcasting..."))
    await callback.answer()

    async with get_db_session() as session:
        all_ids = await get_all_user_ids(session)

    sent = failed = 0
    bot = callback.bot
    for uid in all_ids:
        try:
            await bot.send_message(chat_id=uid, text=text)
            sent += 1
        except Exception as e:
            failed += 1
            log.info("Broadcast to %s failed: %s", uid, e)
        await asyncio.sleep(BROADCAST_RATE_DELAY)

    await callback.message.answer(
        _("✅ Broadcast complete.\nSent: <b>{s}</b>\nFailed: <b>{f}</b>").format(s=sent, f=failed),
        parse_mode="HTML",
    )


# ---------- Anonymous send + reply ----------

def _block_button(blocked_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=_("🚫 Block this sender"),
            callback_data=f"blk:{blocked_id}",
        )
    ]])


@main.message(UserStates.waiting_for_message, F.reply_to_message.is_(None))
async def send_anon(message, state: FSMContext, i18n: I18n):
    data = await state.get_data()
    receiver_id = data["receiver_id"]
    sender_id = message.from_user.id

    if sender_id == receiver_id:
        await message.answer(_("❌ You can't send anonymous messages to yourself."))
        return

    async with get_db_session() as session:
        if await is_blocked(session, blocker_id=receiver_id, blocked_id=sender_id):
            await message.answer(_("🚫 This user has blocked anonymous messages from you."))
            return

        admins = await list_admins(session)
        admin_ids = {a.telegram_id for a in admins} | set(SUPER_ADMIN)
        receiver_locale = await get_user_locale(session, receiver_id) or "en"

        handle = make_nickname(sender_id, receiver_id)
        is_admin_receiver = receiver_id in admin_ids

        # Build the caption + reply markup in the RECEIVER's locale, since
        # those strings are shown to the receiver, not the sender.
        with i18n.use_locale(receiver_locale):
            original_text = (message.caption or message.text or _("Media message")).strip()
            text_footer = _("\n\n➡️ Swipe right on this message to reply anonymously")

            if is_admin_receiver:
                # Only the ID is wrapped in <code> (monospace tap-to-copy).
                # Name + username render as normal text but stay selectable
                # because protect_content is off for admin receivers.
                name_field = html.escape(message.from_user.full_name)
                if message.from_user.username:
                    username_field = html.escape(message.from_user.username)
                else:
                    username_field = _("none")
                admin_info = (
                    "\n\n" + hbold(_("👤 SENDER INFO"))
                    + "\n" + _("🎭 Anon handle: <b>{handle}</b>").format(handle=html.escape(handle))
                    + "\n" + _("👤 Name: {name}").format(name=name_field)
                    + "\n" + _("💻 Username: @{username}").format(username=username_field)
                    + "\n" + _("🆔 ID: <code>{id}</code>").format(id=sender_id)
                    + "\n" + _("🔗 Profile: <a href='tg://user?id={id}'>Open profile</a>").format(
                        id=sender_id
                    )
                )
                final_caption = _("📨 NEW ANONYMOUS MESSAGE\n\n{text}{info}{footer}").format(
                    text=original_text, info=admin_info, footer=text_footer
                )
            else:
                final_caption = _("💌 ANONYMOUS MESSAGE from <b>{handle}</b>\n\n{text}{footer}").format(
                    handle=handle, text=original_text, footer=text_footer
                )

            reply_markup = _block_button(sender_id)

        # Protect content for normal receivers; unprotect for admins so they can
        # copy the sender info (IDs/usernames) for moderation.
        protect = not is_admin_receiver

        if message.content_type == "text":
            sent = await message.bot.send_message(
                chat_id=receiver_id,
                text=final_caption,
                parse_mode="HTML",
                protect_content=protect,
                disable_web_page_preview=True,
                reply_markup=reply_markup,
            )
        else:
            sent = await message.bot.copy_message(
                chat_id=receiver_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                caption=final_caption,
                parse_mode="HTML",
                protect_content=protect,
                reply_markup=reply_markup,
            )

        await save_message(
            session=session,
            sender_id=sender_id,
            receiver_id=receiver_id,
            text=original_text,
            telegram_message_id=sent.message_id,
        )

    await message.answer(_("💌 Message sent anonymously! You can send another one 😁➡️"))


@main.message(F.reply_to_message)
async def handle_reply(message, i18n: I18n):
    replied_msg_id = message.reply_to_message.message_id
    current_user_id = message.from_user.id
    user = message.from_user

    async with get_db_session() as session:
        target_id = await get_chat_partner(session, replied_msg_id, current_user_id)

        if not target_id:
            return

        if await is_blocked(session, blocker_id=target_id, blocked_id=current_user_id):
            await message.answer(_("🚫 This user has blocked anonymous messages from you."))
            return

        admins = await list_admins(session)
        admin_ids = {a.telegram_id for a in admins} | set(SUPER_ADMIN)
        target_locale = await get_user_locale(session, target_id) or "en"

        handle = make_nickname(current_user_id, target_id)
        is_admin_target = target_id in admin_ids

        # Build the caption + reply markup in the RECEIVER's (target's) locale.
        with i18n.use_locale(target_locale):
            original_text = (message.caption or message.text or _("Media message")).strip()
            footer = _("\n\n➡️ Swipe right on this message to reply anonymously")

            if is_admin_target:
                # Only the ID is wrapped in <code>. Name + username are plain
                # text but stay selectable because protect_content is off here.
                name_field = html.escape(user.full_name)
                if user.username:
                    username_field = html.escape(user.username)
                else:
                    username_field = _("none")
                admin_info = (
                    "\n\n" + hbold(_("👤 REPLY FROM"))
                    + "\n" + _("🎭 Anon handle: <b>{handle}</b>").format(handle=html.escape(handle))
                    + "\n" + _("👤 Name: {name}").format(name=name_field)
                    + "\n" + _("💻 Username: @{username}").format(username=username_field)
                    + "\n" + _("🆔 ID: <code>{id}</code>").format(id=current_user_id)
                    + "\n" + _("🔗 Profile: <a href='tg://user?id={id}'>Open profile</a>").format(
                        id=current_user_id
                    )
                )
                final_caption = _("📨 ANONYMOUS REPLY\n\n{text}{info}{footer}").format(
                    text=original_text, info=admin_info, footer=footer
                )
            else:
                final_caption = _("💌 ANONYMOUS REPLY from <b>{handle}</b>\n\n{text}{footer}").format(
                    handle=handle, text=original_text, footer=footer
                )

            reply_markup = _block_button(current_user_id)

        protect = not is_admin_target

        if message.content_type == "text":
            sent_reply = await message.bot.send_message(
                chat_id=target_id,
                text=final_caption,
                parse_mode="HTML",
                protect_content=protect,
                disable_web_page_preview=True,
                reply_markup=reply_markup,
            )
        else:
            sent_reply = await message.bot.copy_message(
                chat_id=target_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                caption=final_caption,
                parse_mode="HTML",
                protect_content=protect,
                reply_markup=reply_markup,
            )

        await save_message(
            session=session,
            sender_id=current_user_id,
            receiver_id=target_id,
            text=original_text,
            telegram_message_id=sent_reply.message_id,
        )

    await message.answer(_("💌 Reply sent anonymously! 😁✨"))


@main.callback_query(F.data.startswith("blk:"))
async def block_callback(callback: CallbackQuery):
    try:
        blocked_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer(_("❌ Invalid action."), show_alert=True)
        return

    blocker_id = callback.from_user.id

    if blocker_id == blocked_id:
        await callback.answer(_("❌ You can't block yourself."), show_alert=True)
        return

    async with get_db_session() as session:
        added = await add_block(session, blocker_id, blocked_id)

    if added:
        handle = make_nickname(blocked_id, blocker_id)
        await callback.answer(
            _("✅ Blocked {handle}. They can no longer reach you here.").format(handle=handle),
            show_alert=True,
        )
    else:
        await callback.answer(_("Already blocked."), show_alert=False)
