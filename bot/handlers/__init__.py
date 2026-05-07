from bot.dispatcher import dp
from bot.handlers.main_router import main
from bot.handlers.message_router import msg_router
from bot.handlers.premium_router import premium_router
from bot.handlers.inbox_router import inbox_router
from bot.handlers.admin_router import admin_router
from bot.handlers.profile_router import profile_router

# Registration order matters: more specific routers first
dp.include_routers(
    admin_router,    # /admin command — before general handlers
    premium_router,  # /premium, Stars payment, slug flow
    inbox_router,    # /inbox, pagination callbacks
    profile_router,  # /me, settings callbacks
    main,            # /start, language, comments, about
    msg_router,      # anonymous messages, replies, action callbacks
)
