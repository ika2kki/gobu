import logging
import tomllib
from logging.handlers import RotatingFileHandler

import discord
import jishaku

from core.bot import Gobu

discord.VoiceClient.warn_nacl = False

jishaku.Flags.NO_UNDERSCORE = True
jishaku.Flags.NO_DM_TRACEBACK = True
jishaku.Flags.HIDE = True

discord.utils.setup_logging(root=True)

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
logging.getLogger("discord.http").setLevel(logging.WARNING)

handler = RotatingFileHandler(
    filename="gobu.log",
    encoding="utf-8",
    maxBytes=32 * 1024 * 1024,
    backupCount=5
)

formatter = logging.Formatter(
    "[{asctime}] [{levelname:<8}] {name}: {message}",
    datefmt="%Y-%m-%d %H:%M:%S",
    style="{"
)
handler.setFormatter(formatter)
LOGGER.addHandler(handler)

with open("config.toml", "rb") as f:
    config = tomllib.load(f)

Gobu().run(config["bot"]["token"], log_handler=None)
