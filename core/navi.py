from typing import Any, Generic, TypeVar

import discord
from discord import ui
from discord.ext import commands

ItemT = TypeVar("ItemT")

# mini version of original navi

class proxy(Generic[ItemT]):
    def __init__(self, items: list[ItemT], *, index: int = 0):
        self.items = items
        self.index = index
        self.max_pages = len(self.items)

    def jump_first(self):
        self.index = 0

    def previous(self):
        self.index = max(self.index - 1, 0)

    def peek(self) -> ItemT:
        return self.items[self.index]

    def next(self):
        self.index = min(self.index + 1, self.max_pages - 1)

    def jump_last(self):
        self.index = self.max_pages - 1

VS15 = "\N{VARIATION SELECTOR-15}"

class Navi(ui.View, Generic[ItemT]):
    def __init_subclass__(cls, *, navi_row: int | None = None):
        super().__init_subclass__()
        if navi_row is not None:
            for index, fn in enumerate(cls.__view_children_items__):
                if index % 5 == 0:
                    navi_row += 1

                copy = fn.__discord_ui_model_kwargs__.copy() # type: ignore
                copy["row"] = navi_row
                fn.__discord_ui_model_kwargs__ = copy # type: ignore

    def __init__(self, prox: proxy[ItemT]):
        super().__init__()
        self.proxy = prox
        if self.proxy.max_pages == 1:
            self.clear_items()
            self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.owner_id

    def prepare(self, item: ItemT) -> dict[str, Any]:
        prepped = {}
        prepped["view"] = self
        if isinstance(item, discord.Embed):
            prepped["embed"] = item
        elif isinstance(item, str):
            prepped["content"] = item
        return prepped

    @ui.button(label=f"1 \N{BLACK LEFT-POINTING DOUBLE TRIANGLE}{VS15}")
    async def jump_first(self, interaction: discord.Interaction, button: ui.Button):
        self.proxy.jump_first()
        self.update_items()
        await interaction.response.edit_message(**self.prepare(self.proxy.peek()))

    @ui.button(label=F"\N{BLACK LEFT-POINTING TRIANGLE}{VS15}")
    async def previous(self, interaction: discord.Interaction, button: ui.Button):
        self.proxy.previous()
        self.update_items()
        await interaction.response.edit_message(**self.prepare(self.proxy.peek()))

    @ui.button(style=discord.ButtonStyle.blurple, disabled=True)
    async def page_number(self, interaction: discord.Interaction, button: ui.Button): ...

    @ui.button(label=f"\N{BLACK RIGHT-POINTING TRIANGLE}{VS15}")
    async def next(self, interaction: discord.Interaction, button: ui.Button):
        self.proxy.next()
        self.update_items()
        await interaction.response.edit_message(**self.prepare(self.proxy.peek()))

    @ui.button()
    async def jump_last(self, interaction: discord.Interaction, button: ui.Button):
        self.proxy.jump_last()
        self.update_items()
        await interaction.response.edit_message(**self.prepare(self.proxy.peek()))

    @ui.button(label=f"\N{EJECT SYMBOL}{VS15} Close pages", style=discord.ButtonStyle.red)
    async def close(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        await interaction.delete_original_response()

    def update_items(self):
        self.jump_first.disabled = self.previous.disabled = self.proxy.index == 0
        self.page_number.label = str(self.proxy.index + 1)
        self.jump_last.disabled = self.next.disabled = self.proxy.index == (self.proxy.max_pages - 1)
        self.jump_last.label = f"\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE}{VS15} {self.proxy.max_pages}"

    async def send(self, ctx: commands.Context, **extras: Any):
        self.owner_id = ctx.author.id
        self.update_items()
        await ctx.send(**self.prepare(self.proxy.peek()), **extras)
