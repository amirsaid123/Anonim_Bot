"""
User profile: /me stats, notification settings, referral link.
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)
from aiogram.utils.i18n import gettext as _
from aiogram.utils.i18n import lazy_gettext as __

from database.functions import (
    get_or_create_settings,
    get_premium_expiry,
    get_received_count,
    get_referral_count,
    get_sent_count,
    is_user_premium,
    set_notifications,
)
from database.session import get_db_session

profile_router = Router()


@profile_router.message(F.text == __("👤 Profile"))
@profile_router.message(Command("me"))
async def profile_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    code = data.get("locale")
    await state.clear()
    await state.update_data(user_id=message.from_user.id, locale=code)

    user_id = message.from_user.id
    session = await get_db_session()

    received = await get_received_count(session, user_id)
    sent = await get_sent_count(session, user_id)
    referrals = await get_referral_count(session, user_id)
    is_premium = await is_user_premium(session, user_id)
    expiry = await get_premium_expiry(session, user_id)
    settings = await get_or_create_settings(session, user_id)
    await session.close()

    premium_line = ""
    if is_premium and expiry:
        premium_line = _("⭐ Premium until: <b>{date}</b>").format(
            date=expiry.strftime("%d %b %Y")
        )
    else:
        premium_line = _("⭐ Premium: <b>Inactive</b> — /premium to upgrade")

    notif_icon = "🔔" if settings.notifications_enabled else "🔕"
    slug_line = (
        _("🔗 Custom slug: <code>{slug}</code>").format(slug=settings.custom_slug)
        if settings.custom_slug else
        _("🔗 Custom slug: <i>not set</i>")
    )

    bot_username = (await message.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

    text = (
        _("👤 <b>Your Profile</b>\n\n"
          "📨 Messages received: <b>{recv}</b>\n"
          "💬 Messages sent: <b>{sent}</b>\n"
          "🤝 Referrals: <b>{refs}</b>\n\n"
          "{premium}\n"
          "{slug}\n\n"
          "{notif_icon} Notifications: <b>{notif}</b>\n\n"
          "🔗 <b>Your referral link:</b>\n"
          "<code>{ref_link}</code>\n\n"
          "<i>Share it — invite friends and grow together!</i>")
    ).format(
        recv=received,
        sent=sent,
        refs=referrals,
        premium=premium_line,
        slug=slug_line,
        notif_icon=notif_icon,
        notif=_("On") if settings.notifications_enabled else _("Off"),
        ref_link=ref_link,
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_("🔕 Mute") if settings.notifications_enabled else _("🔔 Unmute"),
                callback_data="toggle_notif",
            )
        ],
        [
            InlineKeyboardButton(
                text=_("🔗 Set Custom Slug"),
                callback_data="set_slug",
            )
        ],
    ])

    await message.answer(text, reply_markup=keyboard)


@profile_router.callback_query(F.data == "toggle_notif")
async def toggle_notifications(callback: CallbackQuery):
    session = await get_db_session()
    settings = await get_or_create_settings(session, callback.from_user.id)
    new_state = not settings.notifications_enabled
    await set_notifications(session, callback.from_user.id, new_state)
    await session.close()

    if new_state:
        await callback.answer(_("🔔 Notifications turned ON — tap 👤 Profile to refresh"), show_alert=True)
    else:
        await callback.answer(_("🔕 Notifications turned OFF — tap 👤 Profile to refresh"), show_alert=True)
