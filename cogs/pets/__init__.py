import core

from .cog import PetsCog


async def setup(bot: core.Gobu):
    await bot.add_cog(PetsCog(bot))
