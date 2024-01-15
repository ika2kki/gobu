import enum
import logging
from typing import Annotated, List

import discord
from discord import ui
from discord.ext import commands
from discord.utils import MISSING
from typing_extensions import Self

import core
from core import navi, utils

from .static import *
from .types import *

LOGGER = logging.getLogger(__name__)

def escape(content: str, *, width: int = 45, suffix: str = " [...]") -> str:
    escaped = discord.utils.escape_markdown(content)
    if len(escaped) > width:
        escaped = escaped[: width - len(suffix)] + suffix
    return escaped

def pet_name_to_url(name: str) -> str:
    # doesnt work for all pets
    # for example some hybrid-type pets are suffixed with _(Hybrid)
    # i cant do anything about this since i have no idea when the wiki does it
    base = "https://www.wizard101central.com/wiki/Pet:"
    return base + "_".join(name.split())

def talent_name_to_url(name: str) -> str:
    # likewise
    base = "https://www.wizard101central.com/wiki/PetAbility:"
    return base + "_".join(name.split())

def delimited(string: str, *, delimiter: str = ","):
    for line in string.strip(delimiter).splitlines():
        for word in line.split(delimiter):
            if cleaned := word.strip():
                yield cleaned

class BlankPaginator(commands.Paginator):
    def __init__(self):
        super().__init__(prefix=None, suffix=None)


class PetConverter(commands.Converter):
    async def convert(self, ctx: commands.Context, argument: str) -> Pet:
        # looking up a pet by internal name is case-sensitive
        if argument in PETS_BY_INTERNAL_NAME:
            return PETS_BY_INTERNAL_NAME[argument]

        lower = argument.lower()
        if lower in PETS_BY_LOWERCASE_NAME:
            return PETS_BY_LOWERCASE_NAME[lower]

        raise PetNotFound(argument)


class SubstringPets(commands.Converter):
    async def convert(self, ctx: commands.Context, argument: str) -> list[Pet]:
        lower = argument.lower()
        pets: list[Pet] = []
        for name, pet in PETS_BY_LOWERCASE_NAME.items():
            if lower in name:
                pets.append(pet)
        if not pets:
            raise NoPetsFound(argument)
        return pets


class DelimitedPets(PetConverter):
    def __init__(self, *, bound: int | None = None, skip_duplicate: bool = True):
        self.bound = bound
        self.skip_duplicate = skip_duplicate

    async def convert(self, ctx: commands.Context, argument: str) -> list[Pet]:
        by_comma = [x for x in delimited(argument)]
        if self.bound is not None and len(by_comma) != self.bound:
            cls = TooManyPets if len(by_comma) > self.bound else NotEnoughPets
            raise cls(bound=self.bound)

        seen: set[str] = set()
        pets: list[Pet] = []

        for pet_name in by_comma:
            pet = await super().convert(ctx, pet_name)
            if self.skip_duplicate:
                internal_name = pet["internal_name"]
                if internal_name in seen:
                    continue
                seen.add(internal_name)
            pets.append(pet)

        return pets


class TalentConverter(commands.Converter):
    async def convert(self, ctx: commands.Context, argument: str) -> Talent:
        if argument in TALENTS_BY_INTERNAL_NAME:
            return TALENTS_BY_INTERNAL_NAME[argument]

        lower = argument.lower()
        if lower in TALENTS_BY_LOWERCASE_NAME:
            return TALENTS_BY_LOWERCASE_NAME[lower]

        raise TalentNotFound(argument)


class DelimitedTalents(TalentConverter):
    def __init__(self, *, bound: int | None = None):
        self.bound = bound

    async def convert(self, ctx: commands.Context, argument: str) -> list[Talent]:
        by_comma = [x for x in delimited(argument)]
        if self.bound is not None and len(by_comma) != self.bound:
            cls = TooManyTalents if len(by_comma) > self.bound else NotEnoughTalents
            raise cls(bound=self.bound)

        talents: list[Talent] = []
        seen: set[str] = set()

        for talent_name in by_comma:
            talent = await super().convert(ctx, talent_name)

            internal_name = talent["internal_name"]
            if internal_name not in seen:
                seen.add(internal_name)

                talents.append(talent)

        return talents


class RarityConverter(commands.Converter):
    # add some aliases
    RARITIES_ALIASED = RARITIES.copy()
    RARITIES_ALIASED["ultrarare"] = RARITIES_ALIASED["ultra rare"] = ULTRA_RARE
    RARITIES_ALIASED.update({v.lower(): k for k, v in SHORT_RARITIES.items()})

    async def convert(self, ctx: commands.Context, argument: str) -> int:
        lower = argument.lower()
        if lower not in self.RARITIES_ALIASED:
            raise RarityNotFound(argument)
        return self.RARITIES_ALIASED[lower]


class SchoolConverter(commands.Converter):
    async def convert(self, ctx: commands.Context, argument: str) -> str:
        lower = argument.lower()
        if lower not in SCHOOLS:
            raise SchoolNotFound(argument)
        return lower


class EggConverter(commands.Converter):
    async def convert(self, ctx: commands.Context, argument: str) -> str:
        lower = argument.lower()
        if not lower.endswith(" egg"):
            lower = f"{lower} egg"
        if lower not in EGGS:
            raise EggNotFound(argument)
        return lower


class PriorityType(enum.Enum):
    relative = 1
    absolute = 2

    @classmethod
    async def convert(cls, ctx: commands.Context, argument: str) -> Self:
        lower = argument.lower()
        if lower in ("rel", "relative"):
            return cls.relative # type: ignore
        if lower in ("abs", "absolute", "actual"):
            return cls.absolute # type: ignore

        raise BadPriorityStyle


class BaseFlags(commands.FlagConverter):
    # rip
    def empty(self, ctx: commands.Context) -> bool:
        ignored = {"format"} # passing any of these keys alone doesnt count
        for flag in self.get_flags().values():
            if flag.name in ignored:
                continue
            value = getattr(self, flag.attribute)
            default = flag.default
            if callable(default):
                default = default(ctx)
            if value != default:
                return False
        return True


class PetSearchFlags(BaseFlags):
    # dont really have a way of converting spell names
    spell: List[str] = commands.flag(default=lambda ctx: [],
                                     description="searches pet item cards (inaccurate).")

    talent: List[Talent] = commands.flag(converter=TalentConverter,
                                         max_args=-1,
                                         default=lambda ctx: [],
                                         description="searches first gen talent/derby pool.")

    wow_factor: int | None = commands.flag(name="wow-factor",
                                           converter=commands.Range[int, 0, 10],
                                           default=None,
                                           description="needs to be this wow factor.")

    rarity: int | None = commands.flag(converter=RarityConverter,
                                       default=None,
                                       description="needs to be this rarity.")

    school: str | None = commands.flag(converter=SchoolConverter,
                                       default=None,
                                       description="needs to belong to this school.")

    egg: str | None = commands.flag(converter=EggConverter,
                                    default=None,
                                    description="needs to be hatched from this egg.")

    exclusive: bool | None = commands.flag(converter=utils.BooleanConverter,
                                           default=None,
                                           description="whether the pet is exclusive.")

    tradeable: bool | None = commands.flag(converter=utils.BooleanConverter,
                                           default=None,
                                           description="whether the pet is tradeable between wizards.")

    hybrid: bool | None = commands.flag(converter=utils.BooleanConverter,
                                        default=None,
                                        description="whether the pet is a hybrid")


class SubstringPetsAndSearchFlags(commands.Converter):
    # help command has to "unwrap" the original flag converter one way or another
    FlagConverter = PetSearchFlags

    async def convert(self, ctx: commands.Context, argument: str):
        pattern = self.FlagConverter.__commands_flag_regex__
        match = pattern.search(argument)
        if not match:
            pets = await SubstringPets().convert(ctx, argument)
            return (pets, None)

        offset = match.start()
        before = argument[:offset].strip()
        after = argument[offset:].strip()

        pets = await SubstringPets().convert(ctx, before) if before else PETS
        flags = await self.FlagConverter().convert(ctx, after)
        return (pets, flags)


class TalentSearchFlags(BaseFlags):
    above: Talent | None = commands.flag(converter=TalentConverter,
                                         default=None,
                                         description="needs to be above this talent.")

    below: Talent | None = commands.flag(converter=TalentConverter,
                                         default=None,
                                         description="needs to be below this talent.")

    between: List[Talent] | None = commands.flag(converter=DelimitedTalents(bound=2),
                                                 default=None,
                                                 description=(
                                                     "only include talents between 2 others."
                                                     "\nmutually exclusive with `above` and `below` flags."
                                                 ))

    rarity: List[int] = commands.flag(converter=RarityConverter,
                                      max_args=-1,
                                      default=lambda ctx: [],
                                      description="only include talents of this rarity.")

    unlockable: bool | None = utils.StoreTrueFlag(annotation=utils.BooleanConverter,
                                                  default=None,
                                                  description="pass `false` to filter out locked/unlocked talents.",
                                                  aliases=["lockable"]) # type: ignore

    format: PriorityType = commands.flag(default=PriorityType.relative,
                                         description='relative or absolute')


class ShowHelp(ui.View):
    def __init__(self, context: commands.Context):
        super().__init__()
        self.ctx = context

    @ui.button(label="\N{RIGHTWARDS ARROW WITH HOOK} Show help", style=discord.ButtonStyle.blurple)
    async def show_help(self, interaction: discord.Interaction[commands.Bot], _):
        cmd = self.ctx.bot.help_command.copy()
        # t-t
        cmd.context = ctx = commands.Context(
            message=self.ctx.message,
            bot=self.ctx.bot,
            view=self.ctx.view,
            prefix=self.ctx.prefix,
            interaction=interaction
        )
        ctx.command = self.ctx.command
        await cmd.send_command_help(ctx.command)


class PetsCog(core.Cog, name="Pets", emoji="\N{RABBIT}"):
    """pet commands."""

    async def cog_command_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.MissingFlagArgument):
            await ctx.send(f"`{error.flag.name}` is missing a value")
            return

        elif isinstance(error, commands.TooManyFlags):
            name = error.flag.name
            max_args = error.flag.max_args  # max_args should never be <1 here

            await ctx.send(
                f"`{name}` can only be specified once"
                if max_args == 1
                else f"`{name}` can only be specified up to {max_args} times, not {len(error.values)} times",
                view=ShowHelp(ctx)
            )
            return

        if isinstance(error, commands.BadFlagArgument):
            if isinstance(error.original, utils.BadBooleanFlagArgument):
                await ctx.send(f"type true/false for the `{error.flag.name}` flag.", view=ShowHelp(ctx))
                return

            error = error.original

        if isinstance(error, PetCogException):
            view = ShowHelp(ctx) if error.show_help else MISSING
            await ctx.send(str(error), view=view, allowed_mentions=discord.AllowedMentions.none())

        elif isinstance(error, commands.RangeError):
            # only use range for wow factor
            await ctx.send("wow factors are between 0 and 10")

    async def paginate_pets(self, ctx: commands.Context, pets: list[Pet]):
        pg = BlankPaginator()

        nwidth = len(str(len(pets)))
        for index, pet in enumerate(pets, start=1):
            name = pet["name"]
            if pet["exclusive"]:
                name = f"`[exclusive]` {name}"

            rarity = SHORT_RARITIES[pet["rarity"]]
            url = pet_name_to_url(pet["name"])
            line = (
                f"[__`{index:<{nwidth}}`__]({url}): `{pet['wow_factor']:<2}` `{rarity:<2}` {name}"
                f" :: {pet['egg'].lower().removesuffix(' egg')}"
            )

            extras: list[str] = []
            if not pet["tradeable"]:
                extras.append("untradeable")
            if pet["school_only"]:
                extras.append(f"{pet['school']} school only")
            if extras:
                line = f"{line} ({' + '.join(extras)})"

            pg.add_line(line)

        src = navi.proxy([discord.Embed(description=p) for p in pg.pages])
        await navi.Navi(src).send(ctx)

    @commands.command(aliases=["pet"], usage="[pets] [flags]")
    async def pets(self, ctx: commands.Context, *, pair: SubstringPetsAndSearchFlags):
        """show full info on some pets.

        EXAMPLE:
        pets rain core
        pets levi school: storm
        pets wow-factor: 10 exclusive: yes
        pets spell: deathblade spell: feint talent: mighty wow-factor: 10
        """

        (pets, flags) = pair  # type: ignore

        if flags is not None:
            def predicate(pet: Pet):
                if flags.wow_factor is not None:
                    if pet["wow_factor"] != flags.wow_factor:
                        return False

                if flags.rarity is not None:
                    if pet["rarity"] != flags.rarity:
                        return False

                if flags.school:
                    if pet["school"].lower() != flags.school:
                        return False

                if flags.egg:
                    if pet["egg"].lower() != flags.egg:
                        return False

                if flags.tradeable is not None:
                    if pet["tradeable"] is not flags.tradeable:
                        return False

                if flags.exclusive is not None:
                    if pet["exclusive"] is not flags.exclusive:
                        return False

                if flags.hybrid is not None:
                    hybrid = pet["internal_name"] in HYBRIDS
                    if flags.hybrid is not hybrid:
                        return False

                if flags.spell:
                    spells = [s.lower() for s in pet["spells"]]
                    for spell in flags.spell:
                        if all(spell.lower() not in s for s in spells):
                            return False

                if flags.talent:
                    pool = pet["talents"] + pet["abilities"]
                    pool = [t.lower() for t in pool]
                    for talent in flags.talent:
                        if talent["name"].lower() not in pool:
                            return False

                return True

            pets = [pet for pet in pets if predicate(pet)]
            if not pets:
                await ctx.send("no pets found with those flags")
                return

        await self.paginate_pets(ctx, pets)

    async def paginate_talents(self,
        ctx: commands.Context,
        talents: list[Talent],
        *,
        reversed: bool = False,
        format: PriorityType = PriorityType.relative,
    ):
        pg = BlankPaginator()

        prioritymap = {
            PriorityType.relative: "priority",
            PriorityType.absolute: "absolute_priority"
        }
        try:
            key = prioritymap[format]
        except KeyError:
            raise ValueError(f"unknown priority type member {format}") \
                from None

        nwidth = len(str(talents[-1][key]))
        for talent in talents:
            name = talent["name"]
            hyperlink = f"[__`{talent[key]:<{nwidth}}`__]({talent_name_to_url(name)})"

            unlocked = talent["unlocked"]
            if unlocked is not None:
                emoji = "\N{OPEN LOCK}" if unlocked else "\N{LOCK}"
                emoji += "\N{VARIATION SELECTOR-16}"
                name = f"{name} `{emoji}`"

            rarity = SHORT_RARITIES[talent["rarity"]]
            pg.add_line(f"{hyperlink}: `{rarity:<2}` {name}")

        src = navi.proxy([discord.Embed(description=p) for p in pg.pages], index=reversed and len(pg.pages) - 1)
        await navi.Navi(src).send(ctx)

    @commands.group(invoke_without_command=True, aliases=["talent", "ta"])
    async def talents(self, ctx: commands.Context, *, flags: TalentSearchFlags):
        """search talents.
        lower priority talents are higher when looking at a pet's talent in-game.

        EXAMPLE:
        talents below: furnace above: balance-sniper
        talents between: mighty, storm-giver rarity: ultra-rare
        talents between: spell-proof, spell-defy rarity: common rarity: uncommon
        """

        assert ctx.command
        if flags.empty(ctx):
            await ctx.send("i dont know any of those flag or i didnt get enough.",
                            view=ShowHelp(ctx))
            return

        if (flags.above or flags.below) and flags.between:
            await ctx.send("between is mutually exclusive with above and below")
            return

        if flags.between:
            (below, above) = sorted(flags.between, key=lambda t: t["priority"])
        else:
            (below, above) = (flags.below, flags.above)

        if below and above:
            if below["internal_name"] == above["internal_name"]:
                return await ctx.send("um those are the same talent so there's nothing between them")

            elif below["priority"] > above["priority"]:
                return await ctx.send("both talents have to be in-range of each other")

        talents: list[Talent] = []
        rarities = set(flags.rarity)

        for talent in TALENTS_SORTED_BY_PRIORITY:
            name = talent["internal_name"]

            # always add boundaries if they were explicility specified
            if (below and name == below["internal_name"]
                or above and name == above["internal_name"]):
                talents.append(talent)
                continue

            if rarities and talent["rarity"] not in rarities:
                continue

            if flags.unlockable is False:
                # only valid value is unlockable: no
                if talent["unlocked"] is not None:
                    continue

            if above and above["priority"] < talent["priority"]:
                continue
            if below and below["priority"] > talent["priority"]:
                continue

            talents.append(talent)

        # only paginate talents if we actually found anything in-between
        found = len(talents) - bool(above) - bool(below)
        if found < 1:
            await ctx.send("no talents found")
            return

        await self.paginate_talents(ctx, talents, reversed=bool(above and not below), format=flags.format)

    @talents.command(name="firstgen", aliases=["fg", "pool"])
    async def talents_firstgen(self, ctx: commands.Context, *, pet: Annotated[Pet, PetConverter]):
        """show a pet's first gen pool."""

        embed = discord.Embed()
        # im extremely lazy
        embed.add_field(name="talents", value="\n".join(pet["talents"]))
        embed.add_field(name="abilities (derby talents)", value="\n".join(pet["abilities"]))
        await ctx.send(embed=embed)

    @talents.command(name="prioritise", aliases=["prioritize", "p"])
    async def talents_prioritise(self, ctx: commands.Context, *,
                                talents: Annotated[list[Talent], DelimitedTalents]):
        """sort a given list of talents by priority.

        EXAMPLE: talents prioritise death-dealer, spell-proof, mighty
        """
        talents.sort(key=lambda t: t["priority"])
        await self.paginate_talents(ctx, talents)

    @commands.command()
    async def hybrids(self, ctx: commands.Context, *, pet: Annotated[Pet, PetConverter]):
        """show pet's hybrids.

        EXAMPLE:
        hybrids ghulture
        hybrids rain core
        """

        morphs = MORPHS_BY_PET_INTERNAL_NAME.get(pet["internal_name"], [])
        if not morphs:
            await ctx.send("no hybrids for this pet")
            return

        pairs: set[tuple[str, str]] = set()
        for morph in morphs:
            other_pet = morph["other"]
            baby = morph["baby"]

            other_pet = PETS_BY_INTERNAL_NAME[other_pet]["name"]
            baby = PETS_BY_INTERNAL_NAME[baby]["name"]

            pairs.add((baby, other_pet))

        alphabetical = sorted(pairs)
        pg = BlankPaginator()
        for baby, other_pet in alphabetical:
            pg.add_line(
                f"[{baby}]({pet_name_to_url(baby)}) (hatched with [{other_pet}]({pet_name_to_url(other_pet)}))")

        await navi.Navi(navi.proxy(pg.pages)).send(ctx)

    @commands.command()
    async def hatch(self, ctx: commands.Context, *,
                    pets: Annotated[list[Pet], DelimitedPets(bound=2, skip_duplicate=False)]):
        """calculate baby chance from 2 pet hatch.

        EXAMPLE:
        hatch wraith, dark hound
        hatch rain core, ghulture
        """

        # thx TTA/lntrn
        def pet_hatch_chance(a: int, b: int) -> float:
            n = (11 - a) / (22 - (a + b))
            return round(n * 100, 2)

        (peta, petb) = pets
        (af, bf) = (peta["wow_factor"], petb["wow_factor"])
        (peta_chance, petb_chance) = (pet_hatch_chance(af, bf), pet_hatch_chance(bf, af))

        def describe(pet: Pet) -> str:
            description = f"{pet['name']} [{pet['wow_factor']}]"
            if pet["exclusive"]:
                description = f"[EXCLUSIVE] {description}"
            return description

        pg = BlankPaginator()

        pg.add_line(f"{describe(peta)}: {peta_chance}% ({peta['egg']})")
        pg.add_line(f"{describe(petb)}: {petb_chance}% ({petb['egg']})")

        # append potential hybrids
        morphs: list[MorphException] = MORPHS_BY_PET_INTERNAL_NAME.get(peta["internal_name"], [])
        hybrids = [
            PETS_BY_INTERNAL_NAME[m["baby"]]
            for m in morphs
            if m["other"] == petb["internal_name"]
        ]

        without_duplicate_generations = set(pet["name"] for pet in hybrids)
        if offspring := len(without_duplicate_generations):
            pg.add_line()
            if offspring == 1:
                pg.add_line(f"chance to get a {hybrids[0]['name']} from this hatch")
            else:
                pg.add_line(
                    f"chance to get any of these {offspring} pets from this hatch:")
                for pet in without_duplicate_generations:
                    pg.add_line(f"- {pet}")

        await navi.Navi(navi.proxy(pg.pages)).send(ctx)

## exceptions

class PetCogException(commands.BadArgument):
    def __init__(self, message: str, *, show_help: bool = True):
        super().__init__(message)
        self.show_help = show_help

class NotFoundError(PetCogException):
    def __init__(self, message: str):
        super().__init__(message, show_help=False)

class PetNotFound(NotFoundError):
    def __init__(self, argument: str):
        super().__init__(f'dont know a pet like "{escape(argument)}"')

class NoPetsFound(NotFoundError):
    def __init__(self, argument: str):
        super().__init__(f'no pets found for "{escape(argument)}"')

class NotEnoughPets(PetCogException):
    def __init__(self, *, bound: int):
        plural = "pet" if bound == 1 else "pets"
        super().__init__(f"need at least {bound} {plural}")

class TooManyPets(PetCogException):
    def __init__(self, *, bound: int):
        plural = "pet" if bound == 1 else "pets"
        super().__init__(f"only need {bound} {plural}")

class TalentNotFound(NotFoundError):
    def __init__(self, argument: str):
        super().__init__(f'dont know a talent like "{escape(argument)}"')

class NotEnoughTalents(PetCogException):
    def __init__(self, *, bound: int):
        plural = "talent" if bound == 1 else "talents"
        super().__init__(f"need at least {bound} {plural}")

class TooManyTalents(PetCogException):
    def __init__(self, *, bound: int):
        plural = "talent" if bound == 1 else "talents"
        super().__init__(f"only need {bound} {plural}")

class RarityNotFound(NotFoundError):
    def __init__(self, argument: str):
        super().__init__(
            f'dont know a rarity like "{escape(argument)}"'
            f'\ncan be any of this: {", ".join(RARITIES)}'
        )

class SchoolNotFound(NotFoundError):
    def __init__(self, argument: str):
        schools = ", ".join(ELEMENTALS + SPIRITS)
        super().__init__(f'dont know a school like "{escape(argument)}"\ncan be any of this: {schools}')

class EggNotFound(NotFoundError):
    def __init__(self, argument: str):
        super().__init__(f'dont know an egg like "{argument}"')

class BadPriorityStyle(PetCogException):
    def __init__(self):
        super().__init__('put "relative" or "absolute" for the format.')
