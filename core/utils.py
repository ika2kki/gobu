from discord.ext import commands


class BadBooleanFlagArgument(commands.BadArgument): ...

class BooleanConverter(commands.Converter):
    async def convert(self, ctx: commands.Context, argument: str) -> bool:
        lower = argument.lower()
        if lower in ("true", "y", "yes"):
            return True
        if lower in ("false", "n", "no"):
            return False

        raise BadBooleanFlagArgument

class StoreTrueFlag(commands.Flag):
    """store true flag for help command purposes"""
