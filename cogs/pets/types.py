from typing import TypedDict


class MorphException(TypedDict):
    other: str
    baby: str

class Pet(TypedDict):
    name: str
    internal_name: str
    wow_factor: int
    exclusive: bool
    rarity: int
    school: str
    school_only: bool
    egg: str
    talents: list[str]
    abilities: list[str]
    tradeable: bool
    spells: list[str]
    morphing_exceptions: list[MorphException]

class Talent(TypedDict):
    name: str
    internal_name: str
    priority: int
    absolute_priority: int
    rarity: int
    unlocked: bool | None
