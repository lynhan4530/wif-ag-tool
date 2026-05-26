"""Core data models for the WIF AG Tool."""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class WifUnit:
    """A WIF-added unit extracted from UniteDescriptor.ndf."""
    name: str           # e.g. "WF_M1A2_SEPV2_Abrams_US"  (no Descriptor_Unit_ prefix)
    guid: str           # raw GUID string e.g. "454ef2bc-ff1e-42fd-9c64-7988718c197d"
    nation: str         # "US", "RUS", "FR", "GER", "BEL", "NL", "UK", "DNR"
    attack: int         # UnitAttackValue from TStrategicDataModuleDescriptor
    defense: int        # UnitDefenseValue
    xp_bonus: int       # UnitBonusXpPerLevelValue
    role: str           # UnitRole: "armor", "ifv", "helicopter", "plane", etc.
    name_token: str     # NameToken for UNITS.csv localisation lookup
    specialties: list[str] = field(default_factory=list)
    button_texture: str = ""   # e.g. 'Texture_Button_Unit_M1A2_SEPV2' — resolves via icon_map
    display_name: str = ""     # human-readable, from UNITS.csv via name_token; "" → fallback to pretty ID

    @property
    def descriptor_name(self) -> str:
        """Full NDF descriptor name: Descriptor_Unit_WF_..."""
        return f"Descriptor_Unit_{self.name}"

    @property
    def unit_path(self) -> str:
        """NDF path reference used in DeckPackDescriptor."""
        return f"$/GFX/Unit/{self.descriptor_name}"


@dataclass
class DeckState:
    """Parsed state of a single TDeckDescriptor from StrategicDecks.ndf."""
    name: str                       # e.g. "Descriptor_Deck_pion_US_11ACR_4"
    pack_list: list[str]            # ordered ~/Descriptor_StrategicPack_* refs
    combat_group_list: list[str]    # ordered ~/Descriptor_CombatGroup_* refs
    division_ref: str = ""          # CfgName from DeckDivision, e.g. "RDA_10MSD_solo"
    superior_ref: str = ""          # CfgName from Superior, e.g. "RDA_3eBrig10MSD"

    @property
    def next_index(self) -> int:
        """Index at which new packs should be appended (= current length)."""
        return len(self.pack_list)


@dataclass
class StrategicPack:
    """A parsed DeckPackDescriptor from StrategicPacks.ndf."""
    name: str           # e.g. "Descriptor_StrategicPack_M2A2_Bradley_IFV_US_2"
    unit: str           # unit path $/GFX/Unit/...
    xp: int | None = None
    transport: str | None = None    # transport unit path, if present


@dataclass
class Assignment:
    """A user-configured assignment of a WIF unit to an AG deck."""
    deck_name: str          # full deck descriptor name
    unit_id: str            # WifUnit.name (no Descriptor_Unit_ prefix)
    xp_levels: list[int] = field(default_factory=lambda: [1])
    count: int = 1          # units per SmartGroup slot
    attack_override: int | None = None
    defense_override: int | None = None
    order: int = 0          # position within its deck's replica (drives output ordering)
    seq: int = 0            # disambiguates same unit added more than once to one deck (suffix _1/_2/_3)
    group_name: str = "A"   # combat group within the deck (e.g. "A", "B", "C", "HQ")
    transport_id: str | None = None

    def pack_name(self, xp: int) -> str:
        """Generated StrategicPack descriptor name for a given XP level.

        When seq>0, a sequence suffix is inserted before the XP token so duplicate
        unit rows in the same deck get distinct descriptor names.
        """
        suffix = f"_{self.seq}" if self.seq else ""
        return f"Descriptor_StrategicPack_{self.unit_id}{suffix}_{xp}"

    def combat_group_name(self) -> str:
        """Generated CombatGroup descriptor name based on group_name."""
        deck_short = self.deck_name.replace("Descriptor_Deck_pion_", "")
        return f"Descriptor_CombatGroup_{deck_short}_WIF_{self.group_name}"
