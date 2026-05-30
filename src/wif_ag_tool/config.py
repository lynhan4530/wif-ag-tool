"""Path configuration for the WIF AG Tool.

All paths are resolved at import time from environment variables or hardcoded
Windows defaults. Tests override these by passing paths directly to parser functions
rather than using these constants.
"""

from __future__ import annotations
import os
from pathlib import Path

# ── WIF source (read-only) ────────────────────────────────────────────────────
WIF_ROOT = Path(os.environ.get(
    "WIF_ROOT",
    r"G:\Project\A-World-In-Flames"
))
WIF_UNITE_DESCRIPTOR = WIF_ROOT / "Generated" / "Gameplay" / "Gfx" / "UniteDescriptor.ndf"
WIF_BUTTON_TEXTURES  = WIF_ROOT / "Generated" / "UserInterface" / "Textures" / "ButtonTexturesUnites.ndf"
WIF_UNITS_CSV        = WIF_ROOT / "Localisation" / "A World in Flames" / "UNITS.csv"

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
REPLICAS_FILE    = TOOL_ROOT / "data" / "wif_replicas.json"   # global per-deck WIF replicas
UNITS_CACHE_FILE = TOOL_ROOT / "data" / "wif_units_cache.json"   # WIF master units cache
VANILLA_COMBAT_GROUPS_CACHE = TOOL_ROOT / "data" / "vanilla_combat_groups_cache.json"   # Vanilla CGs cache
VANILLA_PACKS_CACHE = TOOL_ROOT / "data" / "vanilla_packs_cache.json"   # Vanilla Packs cache
CAMPAIGN_DECKS_YAML = TOOL_ROOT / "configs" / "campaign_decks.yaml"   # optional, v1 unused
