from aiogram.utils.markdown import hbold, hcode
from aiogram import Bot

ADMIN_GROUP_ID = -5099315325


async def send_comment_to_admin_group(bot: Bot, user_id: int, username: str, first_name: str, last_name: str,
                                      comment_text: str):
    full_name = f"{first_name} {last_name or ''}".strip()
    username_part = f"@{username}" if username else "no username"

    message = (
        "NEW COMMENT / OFFER\n\n"
        f"{hbold('User')}\n"
        f"• Name: {full_name}\n"
        f"• Username: {username_part}\n"
        f"• ID: {hcode(user_id)}\n"
        f"• Profile: <a href='tg://user?id={user_id}'>Open</a>\n\n"
        f"{hbold('Comment')}\n"
        f"{comment_text.strip()}\n\n"
    )

    try:
        await bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=message,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"Failed to send comment to admin group: {e}")
