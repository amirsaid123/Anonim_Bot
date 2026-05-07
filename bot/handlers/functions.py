from aiogram import Bot
from aiogram.utils.markdown import hbold, hcode
from utils.config import MainConfig

ADMIN_GROUP_ID = MainConfig.admin.ADMIN_GROUP_ID


async def send_comment_to_admin_group(
    bot: Bot,
    user_id: int,
    username: str,
    first_name: str,
    last_name: str,
    comment_text: str,
) -> None:
    full_name = f"{first_name} {last_name or ''}".strip()
    username_part = f"@{username}" if username else "no username"

    text = (
        "💬 NEW COMMENT / OFFER\n\n"
        f"{hbold('User')}\n"
        f"• Name: {full_name}\n"
        f"• Username: {username_part}\n"
        f"• ID: {hcode(user_id)}\n"
        f"• Profile: <a href='tg://user?id={user_id}'>Open</a>\n\n"
        f"{hbold('Comment')}\n"
        f"{comment_text.strip()}"
    )
    try:
        await bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as e:
        print(f"[admin group] Failed to send comment: {e}")


async def send_report_to_admin_group(
    bot: Bot,
    reporter_id: int,
    msg_db_id: int,
    nickname: str,
    text: str,
) -> None:
    message = (
        "⚠️ MESSAGE REPORTED\n\n"
        f"Reporter ID: {hcode(reporter_id)}\n"
        f"Sender nickname: <b>{nickname}</b>\n"
        f"DB Message ID: {hcode(msg_db_id)}\n\n"
        f"{hbold('Message content')}\n{text[:500]}"
    )
    try:
        await bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=message,
            parse_mode="HTML",
        )
    except Exception as e:
        print(f"[admin group] Failed to send report: {e}")
