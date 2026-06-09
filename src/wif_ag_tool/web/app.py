"""Flask app factory. Loads catalogues + caches once at startup."""
from __future__ import annotations
from pathlib import Path

from flask import Flask, send_from_directory

from wif_ag_tool import config
from wif_ag_tool.parser.unit_parser import parse_wif_units, load_wif_units, load_vanilla_units
from wif_ag_tool.parser.icon_parser import parse_button_textures
from wif_ag_tool.parser.pack_parser import parse_strategic_packs, load_vanilla_packs
from wif_ag_tool.parser.combatgroup_parser import parse_combat_groups, load_vanilla_combat_groups
from wif_ag_tool.parser.deck_parser import list_decks
from wif_ag_tool.parser.division_parser import parse_divisions, load_vanilla_divisions
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

        platoons_csv = {}
        vanilla_platoons_path = config.WARNO_MODS_DIR / "ExampleAssets" / "Localisation" / "PLATOONS.csv"
        if vanilla_platoons_path.exists():
            try:
                platoons_csv.update(load_units_csv(vanilla_platoons_path))
            except Exception as e:
                print(f"warn: failed to load vanilla platoons csv: {e}")
        wif_platoons_path = config.WIF_ROOT / "Localisation" / "A World in Flames" / "PLATOONS.csv"
        if wif_platoons_path.exists():
            try:
                platoons_csv.update(load_units_csv(wif_platoons_path))
            except Exception as e:
                print(f"warn: failed to load WIF platoons csv: {e}")
        units = load_wif_units(units_csv=units_csv)
        vanilla_units = load_vanilla_units(units_csv=units_csv)
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
        packs = load_vanilla_packs()
        combat_groups = load_vanilla_combat_groups()
        divisions = load_vanilla_divisions(units_csv=units_csv)
    else:
        units, decks, icons, packs, combat_groups = {}, {}, {}, {}, {}
        units_csv, vanilla_units, divisions = {}, {}, {}
        platoons_csv = {}

    # Ensure sessions/data dirs exist so the API can write immediately
    config.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    config.REPLICAS_FILE.parent.mkdir(parents=True, exist_ok=True)

    set_state(
        units=units, decks=decks, icons=icons,
        packs=packs, combat_groups=combat_groups,
        vanilla_units=vanilla_units, divisions=divisions, units_csv=units_csv,
        platoons_csv=platoons_csv,
    )

    app.register_blueprint(api_bp, url_prefix="/api")

    @app.route("/")
    def index():
        resp = send_from_directory(STATIC_DIR, "ui.html")
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

    return app
