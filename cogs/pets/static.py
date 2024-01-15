import json

from .types import MorphException, Pet, Talent

__all__ = (
    "PETS",
    "TALENTS",

    "PETS_BY_LOWERCASE_NAME",
    "PETS_BY_INTERNAL_NAME",

    "EGGS",

    "TALENTS_BY_INTERNAL_NAME",
    "TALENTS_SORTED_BY_PRIORITY",
    "TALENTS_BY_LOWERCASE_NAME",

    "MORPHS_BY_PET_INTERNAL_NAME",
    "HYBRIDS",

    "COMMON",
    "UNCOMMON",
    "RARE",
    "ULTRA_RARE",
    "EPIC",

    "RARITIES",
    "SHORT_RARITIES",
    "REVERSED_RARITIES",

    "ELEMENTALS",
    "SPIRITS",
    "SCHOOLS",
)

with open("resources/static/pets.json") as f:
    PETS: list[Pet] = json.load(f).get("pets", [])

with open("resources/static/talents.json") as f:
    TALENTS: list[Talent] = json.load(f)

PETS_BY_LOWERCASE_NAME = {pet["name"].lower(): pet for pet in PETS}
PETS_BY_INTERNAL_NAME = {pet["internal_name"]: pet for pet in PETS}

EGGS = frozenset(pet["egg"].lower() for pet in PETS)

TALENTS_BY_INTERNAL_NAME = {talent["internal_name"]: talent for talent in TALENTS}
TALENTS_SORTED_BY_PRIORITY = sorted(TALENTS, key=lambda t: t["priority"])

TALENTS_BY_LOWERCASE_NAME: dict[str, Talent] = {}

for talent in TALENTS:
    name = talent["name"].lower()

    unlocked = talent["unlocked"]
    if unlocked is not None:
        variant = "unlocked" if unlocked else "locked"
        # eg. frozen kraken trained
        for alias in (
                                      ## alias the following:
            f"{name} {variant}",   # unlocked frozen kraken trained
            f"{name} ({variant})", # frozen kraken trained unlocked
            f"{variant} {name}",   # frozen kraken trained (unlocked)
        ):
            TALENTS_BY_LOWERCASE_NAME[alias] = talent

    elif "-" in name:
        # support writing talents with/without hyphens
        # eg. death-dealer
        by_hyphen = name.split("-")
        for alias in (
            "".join(by_hyphen), # deathdealer
            " ".join(by_hyphen) # death dealer
        ):
            TALENTS_BY_LOWERCASE_NAME[alias] = talent

    elif "," in name:
        # eg. no pain, no gain
        # alias no pain no gain
        TALENTS_BY_LOWERCASE_NAME[name.replace(",", "")] = talent

    # i want 'frozen kraken trained' and others to always point to the
    # locked variant when locked/unlocked is not explicitly written
    if unlocked is None or not unlocked:
        TALENTS_BY_LOWERCASE_NAME[name] = talent

# its very common for people to type spell defy instead of the full spell defying
# so ill just special case this one here
spell_defying = TALENTS_BY_INTERNAL_NAME["Talent-Resist-All01"]
for alias in ("spelldefy", "spell defy", "spell-defy"):
    TALENTS_BY_LOWERCASE_NAME[alias] = spell_defying

MORPHS_BY_PET_INTERNAL_NAME: dict[str, list[MorphException]] = {}
for pet in PETS:
    morphs = MORPHS_BY_PET_INTERNAL_NAME.setdefault(pet["internal_name"], [])
    morphs.extend(pet["morphing_exceptions"])

    # this is kinda annoying,
    # morphing exceptions are displaced based on the "root" pet
    # take for example, a rain core and ghulture hatch to make a clamoring ghulture
    # the ghulture doesnt include the clamoring ghulture exception - only rain core does.
    # so we need to add the missing exceptions to the other pet's exceptions
    for morph in pet["morphing_exceptions"]:
        other_pets_morphs: list[MorphException] = MORPHS_BY_PET_INTERNAL_NAME.setdefault(morph["other"], [])
        pair = (morph["baby"], morph["other"])
        if pair not in ((m["baby"], m["other"]) for m in other_pets_morphs):
            # from the POV of the other pet, "other" is now this pet instead of itself
            copy = morph.copy()
            copy["other"] = pet["internal_name"]
            other_pets_morphs.append(copy)

HYBRIDS = frozenset([morph["baby"] for morphs in MORPHS_BY_PET_INTERNAL_NAME.values() for morph in morphs])

COMMON     = 1
UNCOMMON   = 2
RARE       = 3
ULTRA_RARE = 4
EPIC       = 5

RARITIES: dict[str, int] = {
    "common": COMMON,
    "uncommon": UNCOMMON,
    "rare": RARE,
    "ultra-rare": ULTRA_RARE,
    "epic": EPIC
}

SHORT_RARITIES: dict[int, str] = {
    COMMON: "C",
    UNCOMMON: "UC",
    RARE: "R",
    ULTRA_RARE: "UR",
    EPIC: "E"
}

REVERSED_RARITIES: dict[int, str] = {value: key for key, value in RARITIES.items()}

# for the error i want it to appear in this order
ELEMENTALS = ["fire", "ice", "storm"]
SPIRITS = ["life", "death", "myth"]
SCHOOLS = frozenset(ELEMENTALS + SPIRITS)