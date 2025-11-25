from bot.dispatcher import dp
from bot.handlers.main_router import main
dp.include_routers(*[main])