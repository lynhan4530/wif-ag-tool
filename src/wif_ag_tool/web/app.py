"""Flask app factory. Loads WIF unit catalogue + deck cache once at startup."""
from __future__ import annotations
from pathlib import Path

from flask import Flask, send_from_directory

from wif_ag_tool import config
from wif_ag_tool.parser.unit_parser import parse_wif_units
from wif_ag_tool.parser.icon_parser import parse_button_textures
from wif_ag_tool.pipeline import load_deck_cache
from wif_ag_tool.web.api import api_bp, set_state


STATIC_DIR = Path(__file__).parent / "static"


def create_app(load_data: bool = True) -> Flask:
    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")

    if load_data:
        units = (
            parse_wif_units(config.WIF_UNITE_DESCRIPTOR)
            if config.WIF_UNITE_DESCRIPTOR.exists()
            else {}
        )
        decks = load_deck_cache(config.CACHE_FILE)
        icons = (
            parse_button_textures(config.WIF_BUTTON_TEXTURES, config.WIF_ROOT)
            if config.WIF_BUTTON_TEXTURES.exists()
            else {}
        )
    else:
        units, decks, icons = {}, {}, {}

    set_state(units=units, decks=decks, icons=icons)

    app.register_blueprint(api_bp, url_prefix="/api")

    @app.route("/")
    def index():
        return send_from_directory(STATIC_DIR, "ui.html")

    return app
