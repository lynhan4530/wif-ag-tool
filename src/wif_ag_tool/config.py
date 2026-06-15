"""Path configuration for the WIF AG Tool.

All paths are resolved at import time from environment variables or hardcoded
Windows defaults. Tests override these by passing paths directly to parser functions
rather than using these constants.
"""

from __future__ import annotations
import os
from pathlib import Path

# ── Dynamic Mod configuration variables (can be overridden per session) ───────
MOD_UNIT_PREFIX = os.environ.get("MOD_UNIT_PREFIX", "WF_")
MOD_TAG = os.environ.get("MOD_TAG", "WIF")
MOD_LOC_FOLDER = os.environ.get("MOD_LOC_FOLDER", "A World in Flames")

# ── WIF source (read-only) ────────────────────────────────────────────────────
WIF_ROOT = Path(os.environ.get(
    "WIF_ROOT",
    r"G:\Project\A-World-In-Flames"
))
WIF_UNITE_DESCRIPTOR = WIF_ROOT / "Generated" / "Gameplay" / "Gfx" / "UniteDescriptor.ndf"
WIF_WEAPON_DESCRIPTOR = WIF_ROOT / "Generated" / "Gameplay" / "Gfx" / "WeaponDescriptor.ndf"
WIF_AMMO              = WIF_ROOT / "Generated" / "Gameplay" / "Gfx" / "Ammunition.ndf"
WIF_AMMO_MISSILES     = WIF_ROOT / "Generated" / "Gameplay" / "Gfx" / "AmmunitionMissiles.ndf"
WIF_BUTTON_TEXTURES  = WIF_ROOT / "Generated" / "UserInterface" / "Textures" / "ButtonTexturesUnites.ndf"
WIF_UNITS_CSV        = WIF_ROOT / "Localisation" / MOD_LOC_FOLDER / "UNITS.csv"

# ── Vanilla recon (read-only reference extracted from base.zip) ───────────────
VANILLA_ROOT = Path(os.environ.get(
    "VANILLA_ROOT",
    r"G:\Warno_mod\vanilla_recon\GameData"
))
VANILLA_DECKS_DIR        = VANILLA_ROOT / "Generated" / "Gameplay" / "Decks"
VANILLA_STRATEGIC_DECKS  = VANILLA_DECKS_DIR / "StrategicDecks.ndf"
VANILLA_STRATEGIC_PACKS  = VANILLA_DECKS_DIR / "StrategicPacks.ndf"
VANILLA_COMBAT_GROUPS    = VANILLA_DECKS_DIR / "StrategicCombatGroups.ndf"
VANILLA_DIVISIONS_NDF    = VANILLA_DECKS_DIR / "Divisions.ndf"
VANILLA_UNITE_DESCRIPTOR = VANILLA_ROOT / "Generated" / "Gameplay" / "Gfx" / "UniteDescriptor.ndf"
VANILLA_WEAPON_DESCRIPTOR = VANILLA_ROOT / "Generated" / "Gameplay" / "Gfx" / "WeaponDescriptor.ndf"
VANILLA_AMMO              = VANILLA_ROOT / "Generated" / "Gameplay" / "Gfx" / "Ammunition.ndf"
VANILLA_AMMO_MISSILES     = VANILLA_ROOT / "Generated" / "Gameplay" / "Gfx" / "AmmunitionMissiles.ndf"

# ── WARNO install + mod ───────────────────────────────────────────────────────
WARNO_MODS_DIR = Path(os.environ.get(
    "WARNO_MODS_DIR",
    r"G:\Program Files (x86)\Steam\steamapps\common\WARNO\Mods"
))

# ── Steam save files ──────────────────────────────────────────────────────────
SAVES_DIR = Path(os.environ.get(
    "WARNO_SAVES_DIR",
    r"G:\Program Files (x86)\Steam\userdata\142459089\1611600\remote"
))

# ── Tool working directory ────────────────────────────────────────────────────
TOOL_ROOT        = Path(__file__).parent.parent.parent   # G:\Project\wif-ag-tool
ASSIGNMENTS_FILE = TOOL_ROOT / "assignments.json"        # legacy; one-shot migrated on first run
CACHE_FILE       = TOOL_ROOT / ".deck_cache.json"        # refreshed after every patch

SESSIONS_DIR     = TOOL_ROOT / "sessions"                # one file per campaign
REPLICAS_FILE    = TOOL_ROOT / "data" / f"{MOD_TAG.lower()}_replicas.json"   # global per-deck WIF replicas
UNITS_CACHE_FILE = TOOL_ROOT / "data" / f"{MOD_TAG.lower()}_units_cache.json"   # WIF master units cache
VANILLA_UNITS_CACHE = TOOL_ROOT / "data" / "vanilla_units_cache.json" # Vanilla master units cache
VANILLA_COMBAT_GROUPS_CACHE = TOOL_ROOT / "data" / "vanilla_combat_groups_cache.json"   # Vanilla CGs cache
VANILLA_PACKS_CACHE = TOOL_ROOT / "data" / "vanilla_packs_cache.json"   # Vanilla Packs cache
VANILLA_DIVISIONS_CACHE = TOOL_ROOT / "data" / "vanilla_divisions_cache.json" # Vanilla Divisions cache
CAMPAIGN_DECKS_YAML = TOOL_ROOT / "configs" / "campaign_decks.yaml"   # optional, v1 unused

STATS_OVERRIDES_FILE = TOOL_ROOT / "data" / "unit_stats_overrides.json"
WIF_WEAPONS_CACHE     = TOOL_ROOT / "data" / f"{MOD_TAG.lower()}_weapons_cache.json"
WIF_AMMO_CACHE        = TOOL_ROOT / "data" / f"{MOD_TAG.lower()}_ammo_cache.json"
VANILLA_WEAPONS_CACHE = TOOL_ROOT / "data" / "vanilla_weapons_cache.json"
VANILLA_AMMO_CACHE    = TOOL_ROOT / "data" / "vanilla_ammo_cache.json"


def apply_session_config(session_dict: dict) -> None:
    """Update config paths and tags dynamically from active session's settings."""
    global WIF_ROOT, WIF_UNITE_DESCRIPTOR, WIF_WEAPON_DESCRIPTOR, WIF_AMMO, WIF_AMMO_MISSILES, WIF_BUTTON_TEXTURES
    global MOD_UNIT_PREFIX, MOD_TAG, MOD_LOC_FOLDER, WIF_UNITS_CSV, REPLICAS_FILE, UNITS_CACHE_FILE
    global WIF_WEAPONS_CACHE, WIF_AMMO_CACHE

    source_dir = session_dict.get("source_mod_dir", "").strip()
    if source_dir:
        WIF_ROOT = Path(source_dir)
        WIF_UNITE_DESCRIPTOR = WIF_ROOT / "Generated" / "Gameplay" / "Gfx" / "UniteDescriptor.ndf"
        WIF_WEAPON_DESCRIPTOR = WIF_ROOT / "Generated" / "Gameplay" / "Gfx" / "WeaponDescriptor.ndf"
        WIF_AMMO              = WIF_ROOT / "Generated" / "Gameplay" / "Gfx" / "Ammunition.ndf"
        WIF_AMMO_MISSILES     = WIF_ROOT / "Generated" / "Gameplay" / "Gfx" / "AmmunitionMissiles.ndf"
        WIF_BUTTON_TEXTURES  = WIF_ROOT / "Generated" / "UserInterface" / "Textures" / "ButtonTexturesUnites.ndf"

    loc_folder = session_dict.get("mod_loc_folder", "").strip()
    if loc_folder:
        MOD_LOC_FOLDER = loc_folder
    elif source_dir:
        # Fallback to search subdirectories under Localisation
        loc_dir = WIF_ROOT / "Localisation"
        if loc_dir.exists():
            for p in loc_dir.iterdir():
                if p.is_dir() and (p / "PLATOONS.csv").exists():
                    MOD_LOC_FOLDER = p.name
                    break

    WIF_UNITS_CSV = WIF_ROOT / "Localisation" / MOD_LOC_FOLDER / "UNITS.csv"

    prefix = session_dict.get("mod_unit_prefix", "").strip()
    if prefix:
        MOD_UNIT_PREFIX = prefix

    tag = session_dict.get("mod_tag", "").strip()
    if tag:
        MOD_TAG = tag

    if "PYTEST_CURRENT_TEST" in os.environ:
        parent = REPLICAS_FILE.parent
        REPLICAS_FILE = parent / f"{MOD_TAG.lower()}_replicas.json"
        UNITS_CACHE_FILE = parent / f"{MOD_TAG.lower()}_units_cache.json"
        WIF_WEAPONS_CACHE = parent / f"{MOD_TAG.lower()}_weapons_cache.json"
        WIF_AMMO_CACHE = parent / f"{MOD_TAG.lower()}_ammo_cache.json"
    else:
        REPLICAS_FILE = TOOL_ROOT / "data" / f"{MOD_TAG.lower()}_replicas.json"
        UNITS_CACHE_FILE = TOOL_ROOT / "data" / f"{MOD_TAG.lower()}_units_cache.json"
        WIF_WEAPONS_CACHE = TOOL_ROOT / "data" / f"{MOD_TAG.lower()}_weapons_cache.json"
        WIF_AMMO_CACHE = TOOL_ROOT / "data" / f"{MOD_TAG.lower()}_ammo_cache.json"
