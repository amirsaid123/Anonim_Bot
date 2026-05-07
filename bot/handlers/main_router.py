from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.i18n import gettext as _
from aiogram.utils.i18n import lazy_gettext as __

from bot.functions import (
    UserStates, LanguageStates,
    make_reply_button, make_back_button, make_language_button,
)
from database.functions import insert_user, insert_comment, save_referral, get_user_id_by_slug
from database.session import get_db_session
from bot.handlers.functions import send_comment_to_admin_group
from datetime import datetime

main = Router()


def _main_menu() -> list[str]:
    return [
        _("🔗 Create a link"),
        _("📥 Inbox"),
        _("👤 Profile"),
        _("💬 Comments"),
        _("ℹ️ About"),
        _("⭐ Premium"),
        _("🌐 Language 🇺🇸/🇺🇿/🇷🇺"),
    ]


@main.message(CommandStart())
async def start_handler(message: Message, command: CommandStart.commands, state: FSMContext):
    session = await get_db_session()
    user = message.from_user

    await insert_user(
        session,
        user.id,
        user.username,
        user.first_name,
        user.last_name,
        datetime.now(),
    )

    args = command.args or ""

    # Referral link: ?start=ref_123456
    if args.startswith("ref_"):
        try:
            referrer_id = int(args[4:])
            await save_referral(session, referrer_id=referrer_id, referred_id=user.id)
        except ValueError:
            pass
        await session.close()
        await state.clear()
        keyboard = await make_reply_button(_main_menu(), [1, 2, 2, 1, 1])
        await message.answer(_("Welcome to Anonymous chat bot! 🎭"), reply_markup=keyboard)
        return

    # Message link: ?start=123456 (user_id) or ?start=myslug
    if args:
        receiver_id: int | None = None

        if args.isdigit():
            receiver_id = int(args)
        else:
            receiver_id = await get_user_id_by_slug(session, args)

        await session.close()

        if not receiver_id:
            await message.answer(_("❌ Invalid link!"))
            return

        if receiver_id == user.id:
            await message.answer(_("🙈 You can't send an anonymous message to yourself!"))
            return

        await state.update_data(receiver_id=receiver_id)
        await message.answer(
            _("You're about to send an anonymous message 💌\n\nType anything below:")
        )
        await state.set_state(UserStates.waiting_for_message)
        return

    await session.close()
    await state.clear()
    await state.update_data(telegram_id=user.id)

    keyboard = await make_reply_button(_main_menu(), [1, 2, 2, 1, 1])
    await message.answer(
        _("Welcome to <b>AnonBot</b> 🎭\n\nSend and receive anonymous messages, "
          "get random nicknames, and stay completely hidden!"),
        reply_markup=keyboard,
    )


@main.message(F.text == __("🔗 Create a link"))
async def create_link_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    code = data.get("locale")
    await state.clear()
    await state.update_data(user_id=message.from_user.id, locale=code)

    bot_username = (await message.bot.get_me()).username
    user_id = message.from_user.id
    unique_link = f"https://t.me/{bot_username}?start={user_id}"

    await message.answer(_("Your anonymous link 🔗"))
    await message.answer(unique_link)
    await message.answer(
        _("Share this link — anyone who opens it can send you an anonymous message 💌\n\n"
          "💡 <b>Tip:</b> Go to ⭐ Premium to set a custom link like "
          "<code>t.me/{bot}?start=yourname</code>").format(bot=bot_username)
    )


@main.message(F.text == __("ℹ️ About"))
async def about_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    code = data.get("locale")
    await state.clear()
    await state.update_data(user_id=message.from_user.id, locale=code)

    await message.answer(
        _("ℹ️ <b>About AnonBot</b>\n\n"
          "1️⃣ Create a personal link and share it with anyone\n\n"
          "2️⃣ Senders stay <b>completely anonymous</b> — each gets a random nickname\n\n"
          "3️⃣ Reply to messages directly in the chat\n\n"
          "4️⃣ Block or report any sender with one tap\n\n"
          "5️⃣ Upgrade to ⭐ Premium for a custom link, reactions, and more\n\n"
          "Have fun safely! 🥂")
    )


@main.message(F.text == __("💬 Comments"))
async def comment_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    code = data.get("locale")
    await state.clear()
    await state.update_data(user_id=message.from_user.id, locale=code)

    back_button = await make_back_button()
    await message.answer(
        _("Send us your feedback or suggestion 💬\n\nPress 'Back ◀️' to return."),
        reply_markup=back_button,
    )
    await state.set_state(UserStates.waiting_for_comment)


@main.message(UserStates.waiting_for_comment, F.text != __("Back ◀️"))
async def receive_comment(message: Message):
    session = await get_db_session()
    await insert_comment(session, message.from_user.id, message.text or "")
    await session.close()

    await send_comment_to_admin_group(
        bot=message.bot,
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        first_name=message.from_user.first_name or "",
        last_name=message.from_user.last_name or "",
        comment_text=message.text or "",
    )
    await message.answer(_("Thank you! Your feedback was sent 💬"))


@main.message(UserStates.waiting_for_comment, F.text == __("Back ◀️"))
async def comment_back_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    code = data.get("locale")
    await state.clear()
    await state.update_data(user_id=message.from_user.id, locale=code)

    keyboard = await make_reply_button(_main_menu(), [1, 2, 2, 1, 1])
    await message.answer(_("Welcome back to the Main Menu 🏠"), reply_markup=keyboard)


@main.message(F.text == __("🌐 Language 🇺🇸/🇺🇿/🇷🇺"))
async def language_handler(message: Message, state: FSMContext):
    keyboard = await make_language_button()
    await state.set_state(LanguageStates.language)
    await message.answer(_("🌐 Choose your language"), reply_markup=keyboard)


@main.message(LanguageStates.language, F.text != __("Back 🔙"))
async def change_language_handler(message: Message, state: FSMContext, i18n):
    lang = {
        "🇺🇸 English": "en",
        "🇷🇺 Русский": "ru",
        "🇺🇿 O'zbekcha": "uz",
    }
    code = lang.get(message.text.strip())
    if not code:
        await message.answer(_("❌ Unknown language. Please choose from the buttons."))
        return

    user_id = message.from_user.id
    await state.clear()
    await state.update_data(user_id=user_id, locale=code)
    i18n.current_locale = code

    keyboard = await make_reply_button(_main_menu(), [1, 2, 2, 1, 1])
    await message.answer(_("Language updated ✅"), reply_markup=keyboard)


@main.message(LanguageStates.language, F.text == __("Back 🔙"))
async def language_back_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    code = data.get("locale")
    await state.clear()
    await state.update_data(user_id=message.from_user.id, locale=code)

    keyboard = await make_reply_button(_main_menu(), [1, 2, 2, 1, 1])
    await message.answer(_("Welcome back 🏠"), reply_markup=keyboard)
