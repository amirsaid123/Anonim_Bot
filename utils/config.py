from os import getenv
from dotenv import load_dotenv
from utils.path import ENV_PATH

load_dotenv(ENV_PATH)


class DBConfig:
    DB_USER = getenv("DB_USER")
    DB_PASSWORD = getenv("DB_PASSWORD")
    DB_NAME = getenv("DB_NAME")
    DB_HOST = getenv("DB_HOST")
    DB_PORT = getenv("DB_PORT")
    DB_CONFIG = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


class BotConfig:
    TOKEN = getenv("TOKEN")


class MainConfig:
    db = DBConfig()
    bot = BotConfig()
