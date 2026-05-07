from aiogram.filters.callback_data import CallbackData


class MsgActionCB(CallbackData, prefix="ma"):
    """Block or report a received message."""
    action: str   # "block" | "report" | "read"
    msg_id: int   # DB Message.id


class ReactCB(CallbackData, prefix="rc"):
    """Emoji reaction on a received message (premium receiver)."""
    msg_id: int
    emoji: str    # "h"=❤️  "f"=🔥  "l"=😂  "w"=😮  "s"=😢


class InboxCB(CallbackData, prefix="ib"):
    """Inbox pagination."""
    page: int


class AdminCB(CallbackData, prefix="ad"):
    """Admin panel actions."""
    action: str   # "add" | "remove" | "list" | "stats" | "bcast" | "ban" | "unban" | "reports"


REACT_MAP: dict[str, str] = {
    "h": "❤️",
    "f": "🔥",
    "l": "😂",
    "w": "😮",
    "s": "😢",
}
