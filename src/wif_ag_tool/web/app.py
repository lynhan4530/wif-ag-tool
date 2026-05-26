"""Flask app factory. Loads catalogues + caches once at startup."""
from __future__ import annotations
from pathlib import Path

from flask import Flask, send_from_directory

from wif_ag_tool import config
from wif_ag_tool.parser.unit_parser import parse_wif_units
from wif_ag_tool.parser.icon_parser import parse_button_textures
from wif_ag_tool.parser.pack_parser import parse_strategic_packs
from wif_ag_tool.parser.combatgroup_parser import parse_combat_groups
from wif_ag_tool.parser.deck_parser import list_decks
from wif_ag_tool.parser.division_parser import parse_divisions
from wif_ag_tool.parser.localisation_csv import load_units_csv
from wif_ag_tool.pipeline import load_deck_cache, migrate_legacy_assignments, refresh_deck_cache
from wif_ag_tool.web.api import api_bp, set_state


STATIC_DIR = Path(__file__).parent / "static"


def create_app(load_data: bool = True) -> Flask:
    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")

    if load_data:
        # One-shot migration of any legacy flat assignments.json into the replicas store.
        try:
            migrate_legacy_assignments()
        except Exception:
            # Migration failures shouldn't block startup — fail visibly later via /api/export.
            pass

        units_csv = {}
        vanilla_csv_path = config.WARNO_MODS_DIR / "ExampleAssets" / "Localisation" / "UNITS.csv"
        if vanilla_csv_path.exists():
            try:
                units_csv.update(load_units_csv(vanilla_csv_path))
            except Exception as e:
                print(f"warn: failed to load vanilla units csv: {e}")
        if config.WIF_UNITS_CSV.exists():
            try:
                units_csv.update(load_units_csv(config.WIF_UNITS_CSV))
            except Exception as e:
                print(f"warn: failed to load WIF units csv: {e}")
        units = (
            parse_wif_units(config.WIF_UNITE_DESCRIPTOR, units_csv=units_csv)
            if config.WIF_UNITE_DESCRIPTOR.exists()
            else {}
        )
        vanilla_units = (
            parse_wif_units(
                config.VANILLA_UNITE_DESCRIPTOR, units_csv=units_csv, prefix=None,
            )
            if config.VANILLA_UNITE_DESCRIPTOR.exists()
            else {}
        )
        decks = load_deck_cache(config.CACHE_FILE)
        # First-run convenience: if no cache yet but the vanilla NDF is available,
        # build the cache automatically so the UI is usable out of the box.
        if not decks and config.VANILLA_STRATEGIC_DECKS.exists():
            try:
                names = list_decks(config.VANILLA_STRATEGIC_DECKS)
                decks = refresh_deck_cache(
                    config.VANILLA_STRATEGIC_DECKS, names, config.CACHE_FILE,
                )
            except Exception as exc:
                print(f"warn: auto-refresh failed: {exc}")
        # Auto-refresh once if cached decks lack division_ref (older cache from before this feature)
        if decks and not any(d.division_ref for d in decks.values()) and config.VANILLA_STRATEGIC_DECKS.exists():
            try:
                names = list_decks(config.VANILLA_STRATEGIC_DECKS)
                decks = refresh_deck_cache(
                    config.VANILLA_STRATEGIC_DECKS, names, config.CACHE_FILE,
                )
            except Exception as exc:
                print(f"warn: division-ref auto-refresh failed: {exc}")
        # Icons: WIF's ButtonTexturesUnites.ndf is the merged file (covers vanilla too).
        icons: dict = {}
        if config.WIF_BUTTON_TEXTURES.exists():
            icons.update(parse_button_textures(config.WIF_BUTTON_TEXTURES, config.WIF_ROOT))
        packs = (
            parse_strategic_packs(config.VANILLA_STRATEGIC_PACKS)
            if config.VANILLA_STRATEGIC_PACKS.exists()
            else {}
        )
        combat_groups = (
            parse_combat_groups(config.VANILLA_COMBAT_GROUPS)
            if config.VANILLA_COMBAT_GROUPS.exists()
            else {}
        )
        # Divisions: prefer vanilla (more complete); fall back to WIF mod's copy.
        divisions: dict = {}
        if config.VANILLA_DIVISIONS_NDF.exists():
            divisions = parse_divisions(config.VANILLA_DIVISIONS_NDF)
        elif (config.WIF_ROOT / "Generated/Gameplay/Decks/Divisions.ndf").exists():
            divisions = parse_divisions(
                config.WIF_ROOT / "Generated/Gameplay/Decks/Divisions.ndf"
            )
    else:
        units, decks, icons, packs, combat_groups = {}, {}, {}, {}, {}
        units_csv, vanilla_units, divisions = {}, {}, {}

    # Ensure sessions/data dirs exist so the API can write immediately
    config.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    config.REPLICAS_FILE.parent.mkdir(parents=True, exist_ok=True)

    set_state(
        units=units, decks=decks, icons=icons,
        packs=packs, combat_groups=combat_groups,
        vanilla_units=vanilla_units, divisions=divisions, units_csv=units_csv,
    )

    app.register_blueprint(api_bp, url_prefix="/api")

    @app.route("/")
    def index():
        return send_from_directory(STATIC_DIR, "ui.html")

    return app
