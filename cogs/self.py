import inspect
from typing import Any, Generator

import discord
from discord import ui
from discord.ext import commands

import core
from core import navi, utils


async def setup(bot: core.Gobu):
    await bot.add_cog(SelfCog(bot))

def natural_join(*words: str, delimiter: str = ", ", last: str = "&") -> str:
    n = len(words)
    return (
        "" if n == 0
        else words[0] if n == 1
        else delimiter.join(words[:-1]) + f" {last} {words[-1]}"
    )

class BotHelpCommand(commands.HelpCommand):
    """shows this message."""

    @discord.utils.cached_property
    def safe_cogs(self) -> list[core.Cog]:
        modules = [mod for mod in self.bot.extensions if mod.startswith("cogs.")]
        return [
            cog for cog in self.bot.cogs.values()
            if any(cog.__module__.startswith(mod) for mod in modules)
        ] # type: ignore

    def recurse_commands(self, cmd: commands.Command | commands.Group, *, prefix: str = "") -> Generator[str, None, None]:
        yield f"{prefix}`{cmd.qualified_name}`: {cmd.short_doc}"
        if isinstance(cmd, commands.Group):
            for index, subcommand in enumerate(cmd.commands, start=1):
                prefix = "└" if index == len(cmd.commands) else "├"
                yield from self.recurse_commands(subcommand, prefix=prefix)

    def build_cog_help_embeds(self, cog: commands.Cog) -> list[discord.Embed]:
        cmds = [c for c in cog.get_commands() if not c.hidden]
        lines = [line for cmd in cmds for line in self.recurse_commands(cmd)]

        description = "{}\n\ntap the buttons to view info on all commands".format("\n".join(lines))
        embed = discord.Embed(title=cog.qualified_name, description=description)
        embed.set_footer(
            text=f"type {self.context.clean_prefix}help <command> for more information on a specific command.")

        embeds: list[discord.Embed] = []
        embeds.append(embed)
        embeds.extend([self.build_command_embed(c) for c in cmds])

        return embeds

    def build_command_embed(self, cmd: commands.Command) -> discord.Embed:
        prefix = self.context.clean_prefix
        signature = f"{prefix}{cmd.qualified_name} {cmd.signature}"

        cmd_help = cmd.help or "..."

        description, _, example = cmd_help.partition("EXAMPLE:")
        embed = discord.Embed(title=signature, description=description)

        # add aliases (but only if we have at least 2)
        if len(cmd.aliases) > 1:
            wrapped = [f"`{alias}`" for alias in cmd.aliases]
            embed.add_field(name="Aliases", value=natural_join(*wrapped), inline=False)

        # add flags field it has any
        for param in cmd.clean_params.values():
            converter = getattr(param.converter, "FlagConverter", param.converter)
            if (
                isinstance(converter, commands.FlagConverter)
                or inspect.isclass(converter) and issubclass(converter, commands.FlagConverter)
            ):
                descriptions: list[str] = []
                for name, flag in converter.get_flags().items():
                    brief: list[str] = []

                    if flag.annotation is utils.BooleanConverter and not isinstance(flag, utils.StoreTrueFlag):
                        brief.append("true/false.")

                    brief.append(flag.description or "undescribed flag.")
                    if flag.max_args != 1:
                        brief.append(
                            "(variadic)"
                            if flag.max_args < 0
                            else f"(limited to {flag.max_args} times)"
                        )

                    descriptions.append(f"`{name}:` {' '.join(brief)}")

                embed.add_field(name="Flags", value="\n".join(descriptions), inline=False)
                break

        if isinstance(cmd, commands.Group) and cmd.commands:
            embed.add_field(
                name="Subcommands",
                value="\n".join(f"`{subc.qualified_name}`: {subc.short_doc}" for subc in cmd.commands),
                inline=False
            )
            embed.set_footer(text=f"type {prefix}help <subcommand> for more information on a specific subcommand.")

        examples: list[str] = []

        if ex := example.strip():
            examples.extend(ex.splitlines())

        # also grab examples from any subcommands
        if isinstance(cmd, commands.Group):
            for subcmd in cmd.walk_commands():
                _, _, example = (subcmd.help or "").partition("EXAMPLE:")
                if ex := example.strip():
                    examples.extend(ex.splitlines())

        if examples:
            embed.add_field(
                name="Example" + ("s" if len(examples) > 1 else ""),
                value="\n".join([f"{prefix}{e}" for e in examples]),
                inline=False,
            )

        return embed

    async def command_callback(self, ctx: commands.Context, *, command: str | None = None):
        if not command:
            await self.send_bot_help(None)
            return

        cog = self.bot.get_cog(command)
        if cog and cog.qualified_name in self.safe_cogs:
            await self.send_cog_help(cog)
            return

        cmd = self.bot.get_command(command)
        if not cmd or cmd.hidden or cmd.cog not in self.safe_cogs:
            await ctx.send("dont have a command like that", ephemeral=True)
            return

        await self.send_command_help(cmd)

    async def send_bot_help(self, _):
        await NaviHelp(self.safe_cogs, self).send(self.context, ephemeral=True)

    async def send_cog_help(self, cog: commands.Cog):
        embeds = self.build_cog_help_embeds(cog)
        await navi.Navi(navi.proxy(embeds)).send(self.context, ephemeral=True)

    async def send_command_help(self, cmd: commands.Command):
        await self.context.send(embed=self.build_command_embed(cmd), ephemeral=True)

    send_group_help = send_command_help

    @property
    def bot(self) -> core.Gobu:
        return self.context.bot  # type: ignore


class NaviHelpCogSelect(ui.Select[navi.Navi]):
    def __init__(self, sources: dict[str, navi.proxy]):
        super().__init__(placeholder="Show help for a different category...", row=0)
        self.sources = sources

    async def callback(self, interaction: discord.Interaction):
        assert self.view

        prox = self.sources[self.values[0]]
        self.view.proxy = prox
        self.view.update_items()
        await interaction.response.edit_message(**self.view.prepare(prox.peek()))


class NaviHelp(navi.Navi, navi_row=1):
    def __init__(self, cogs: list[core.Cog], help_command: BotHelpCommand):
        sources: dict[str, navi.proxy] = {
            cog.qualified_name: navi.proxy(help_command.build_cog_help_embeds(cog))
            for cog in cogs
        }
        super().__init__(sources[next(iter(sources))])

        dropdown = NaviHelpCogSelect(sources)
        dropdown.options = [
            discord.SelectOption(
                label=cog.qualified_name,
                description=cog.description,
                emoji=cog.emoji
            )
            for cog in cogs
        ]
        self.add_item(dropdown)

    def update_items(self):
        super().update_items()
        self.next.style = (
            discord.ButtonStyle.green
            if self.proxy.index == 0
            else discord.ButtonStyle.grey
        )

class SelfCog(core.Cog, name="Self", emoji="\N{GEAR}"):
    """commands relating to the bot itself."""

    def __init__(self, bot: core.Gobu):
        super().__init__(bot)
        self._original_help_command = bot.help_command
        attrs: dict[str, Any] = {"help": "shows this message."}
        bot.help_command = BotHelpCommand(command_attrs=attrs)
        bot.help_command.cog = self

    async def cog_unload(self):
        self.bot.help_command = self._original_help_command
