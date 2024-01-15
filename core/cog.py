from typing import Any, ClassVar

from discord.ext import commands

from .bot import Gobu


class Cog(commands.Cog):
    emoji: ClassVar[str | None]

    def __init_subclass__(cls, **kwargs: Any):
        cls.emoji = kwargs.pop("emoji", None)
        super().__init_subclass__(**kwargs)

    def __init__(self, bot: Gobu):
        self.bot = bot
