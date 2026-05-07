"""
Telegram Stars payment flow for 1-week Premium access.
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    LabeledPrice, Message, PreCheckoutQuery,
)
from aiogram.utils.i18n import gettext as _
from aiogram.utils.i18n import lazy_gettext as __

from bot.functions import UserStates
from database.functions import (
    get_premium_expiry,
    grant_premium,
    is_user_premium,
    set_custom_slug,
    get_or_create_settings,
)
from database.session import get_db_session
from utils.config import MainConfig

premium_router = Router()

PRICE = MainConfig.premium.STARS_PRICE
PAYLOAD_PREFIX = "premium_1w_"


def _premium_features_text() -> str:
    return _(
        "⭐ <b>AnonBot Premium — 1 Week</b>\n\n"
        "Unlock all features:\n\n"
        "🔗 <b>Custom link slug</b> — set a personal link like "
        "<code>t.me/bot?start=yourname</code>\n\n"
        "📥 <b>Unlimited inbox</b> — browse your full message history "
        "(free users: last 10 only)\n\n"
        "❤️ <b>Reactions</b> — react to messages you receive and "
        "let senders know (❤️🔥😂😮😢)\n\n"
        "👁 <b>Read receipts</b> — senders get notified when you read "
        "their message\n\n"
        "⭐ <b>Premium badge</b> — shown on every message you send\n\n"
        "Price: <b>{price} ⭐ Telegram Stars</b> / week"
    ).format(price=PRICE)


@premium_router.message(F.text == __("⭐ Premium"))
@premium_router.message(Command("premium"))
async def premium_menu_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    code = data.get("locale")
    await state.clear()
    await state.update_data(user_id=message.from_user.id, locale=code)

    session = await get_db_session()
    user_id = message.from_user.id
    is_premium = await is_user_premium(session, user_id)
    expiry = await get_premium_expiry(session, user_id)
    await session.close()

    if is_premium and expiry:
        expiry_str = expiry.strftime("%d %b %Y %H:%M UTC")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=_("🔄 Extend for {price} ⭐").format(price=PRICE),
                callback_data="buy_premium",
            )
        ], [
            InlineKeyboardButton(
                text=_("🔗 Set Custom Slug"),
                callback_data="set_slug",
            )
        ]])
        await message.answer(
            _("✅ <b>You have Premium!</b>\n\nExpires: <b>{expiry}</b>\n\n{features}").format(
                expiry=expiry_str,
                features=_premium_features_text(),
            ),
            reply_markup=keyboard,
        )
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=_("🛒 Buy Premium — {price} ⭐ Stars").format(price=PRICE),
                callback_data="buy_premium",
            )
        ]])
        await message.answer(
            _premium_features_text(),
            reply_markup=keyboard,
        )


@premium_router.callback_query(F.data == "buy_premium")
async def send_premium_invoice(callback, state: FSMContext):
    user_id = callback.from_user.id
    await callback.answer()

    await callback.bot.send_invoice(
        chat_id=user_id,
        title=_("⭐ AnonBot Premium — 1 Week"),
        description=_(
            "Custom link slug, unlimited inbox, reactions, read receipts, premium badge."
        ),
        payload=f"{PAYLOAD_PREFIX}{user_id}",
        currency="XTR",
        prices=[LabeledPrice(label=_("1 Week Premium"), amount=PRICE)],
    )


@premium_router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout: PreCheckoutQuery):
    if pre_checkout.invoice_payload.startswith(PAYLOAD_PREFIX):
        await pre_checkout.answer(ok=True)
    else:
        await pre_checkout.answer(ok=False, error_message="Invalid payment.")


@premium_router.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    stars_paid = message.successful_payment.total_amount
    user_id = message.from_user.id

    session = await get_db_session()
    await grant_premium(session, user_id, stars_paid)
    await session.close()

    await message.answer(
        _("🎉 <b>Welcome to Premium!</b>\n\n"
          "You now have full access for 7 days.\n\n"
          "• Use /setslug to set your custom link\n"
          "• Your inbox now shows full history\n"
          "• Reaction buttons appear on received messages\n\n"
          "Thank you for supporting AnonBot! ⭐")
    )


# ── Custom slug ────────────────────────────────────────────────────────────────

@premium_router.callback_query(F.data == "set_slug")
async def set_slug_prompt(callback, state: FSMContext):
    session = await get_db_session()
    if not await is_user_premium(session, callback.from_user.id):
        await session.close()
        await callback.answer(_("⭐ Custom slugs are a Premium feature!"), show_alert=True)
        return
    await session.close()

    await callback.answer()
    await callback.message.answer(
        _("✏️ Send your desired custom slug.\n\n"
          "Rules:\n"
          "• 3–30 characters\n"
          "• Only letters, numbers, and underscores\n"
          "• No spaces\n\n"
          "Example: <code>sara</code> → your link becomes "
          "<code>t.me/bot?start=sara</code>")
    )
    await state.set_state(UserStates.waiting_for_custom_slug)


@premium_router.message(Command("setslug"))
async def setslug_command(message: Message, state: FSMContext):
    session = await get_db_session()
    if not await is_user_premium(session, message.from_user.id):
        await session.close()
        await message.answer(_("⭐ Custom slugs require Premium. Use /premium to upgrade."))
        return
    await session.close()

    await message.answer(
        _("✏️ Send your desired custom slug (3–30 chars, letters/numbers/underscore).")
    )
    await state.set_state(UserStates.waiting_for_custom_slug)


@premium_router.message(UserStates.waiting_for_custom_slug)
async def save_slug(message: Message, state: FSMContext):
    slug = (message.text or "").strip().lower()

    if not slug.replace("_", "").isalnum() or not (3 <= len(slug) <= 30):
        await message.answer(
            _("❌ Invalid slug. Use 3–30 letters, numbers, or underscores only.")
        )
        return

    session = await get_db_session()
    saved = await set_custom_slug(session, message.from_user.id, slug)
    await session.close()

    await state.clear()
    await state.update_data(user_id=message.from_user.id)

    if saved:
        bot_username = (await message.bot.get_me()).username
        await message.answer(
            _("✅ Custom slug set!\n\n"
              "Your new link: <code>https://t.me/{bot}?start={slug}</code>").format(
                bot=bot_username, slug=slug
            )
        )
    else:
        await message.answer(_("❌ That slug is already taken. Try another one."))
