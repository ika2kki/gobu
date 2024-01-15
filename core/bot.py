import logging
import re

import discord
from discord import app_commands
from discord.ext import commands

LOGGER = logging.getLogger(__name__)


class Gobu(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix=commands.when_mentioned_or(">?"),
            intents=intents,
            help_command=None,
            strip_after_prefix=True
        )
        self.buckets: dict[int, app_commands.Cooldown] = {}

    async def on_message(self, message: discord.Message):
        assert self.user

        if message.author.bot:
            return
        if message.guild:
            if not message.channel.permissions_for(message.guild.me).send_messages:
                return

        if re.fullmatch(rf"<@!?{self.user.id}>", message.content):
            if message.guild:
                key = message.guild.id
                try:
                    bucket = self.buckets[key]
                except KeyError:
                    self.buckets[key] = bucket = app_commands.Cooldown(1, 10.0)

                remaining = bucket.update_rate_limit(message.created_at.timestamp())
                if remaining:
                    return

            await message.reply(f'my prefix is `>?` or you can mention me')
            return

        await self.process_commands(message)

    async def setup_hook(self):
        for ext in ("jishaku", "cogs.pets", "cogs.self"):
            await self.load_extension(ext)

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, (commands.CommandInvokeError, commands.ConversionError)):
            assert ctx.command
            LOGGER.error(f"Ignoring unknown exception in {ctx.command.qualified_name}", exc_info=error)
