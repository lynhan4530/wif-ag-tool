"""REST API for the WIF AG Tool web UI."""
from __future__ import annotations
import io
import zipfile
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from flask import Blueprint, abort, jsonify, request, send_file

from wif_ag_tool import config
from wif_ag_tool.models import Assignment, DeckState, WifUnit
from wif_ag_tool.parser.deck_parser import list_decks
from wif_ag_tool.parser.save_parser import list_campaigns
from wif_ag_tool.pipeline import (
    load_assignments,
    save_assignments,
    run_export,
    refresh_deck_cache,
    load_deck_cache,
)

api_bp = Blueprint("api", __name__)

# In-process state (set by web.app.create_app)
_state: dict[str, Any] = {"units": {}, "decks": {}, "icons": {}}


def set_state(
    *,
    units: dict[str, WifUnit],
    decks: dict[str, DeckState],
    icons: dict[str, Path] | None = None,
) -> None:
    _state["units"] = units
    _state["decks"] = decks
    _state["icons"] = icons or {}


# ── campaigns ─────────────────────────────────────────────────────────────────

@api_bp.get("/campaigns")
def campaigns():
    items = list_campaigns(config.SAVES_DIR)
    return jsonify([{**c, "path": str(c["path"])} for c in items])


# ── decks ─────────────────────────────────────────────────────────────────────

@api_bp.get("/decks")
def decks():
    nation = request.args.get("nation")
    decks_map: dict[str, DeckState] = _state["decks"]
    out = []
    for name, d in decks_map.items():
        if nation:
            parts = name.split("_")
            if len(parts) < 4 or parts[3] != nation:
                continue
        out.append({"name": name, "next_index": d.next_index, "pack_count": len(d.pack_list)})
    return jsonify(out)


@api_bp.get("/deck/<deck_name>")
def deck(deck_name: str):
    decks_map: dict[str, DeckState] = _state["decks"]
    if deck_name not in decks_map:
        return jsonify({"error": "deck not found"}), 404
    d = decks_map[deck_name]
    assignments = [a for a in load_assignments(config.ASSIGNMENTS_FILE) if a.deck_name == deck_name]
    return jsonify({
        "name": d.name,
        "pack_list": d.pack_list,
        "combat_group_list": d.combat_group_list,
        "next_index": d.next_index,
        "assignments": [asdict(a) for a in assignments],
    })


# ── wif units ─────────────────────────────────────────────────────────────────

@api_bp.get("/wif_units")
def wif_units():
    nation = request.args.get("nation")
    role = request.args.get("role")
    q = (request.args.get("q") or "").lower()
    units: dict[str, WifUnit] = _state["units"]
    out = []
    for u in units.values():
        if nation and u.nation != nation:
            continue
        if role and role != "all" and u.role != role:
            continue
        if q and q not in u.name.lower():
            continue
        out.append(asdict(u))
    return jsonify(out)


# ── assignments ───────────────────────────────────────────────────────────────

@api_bp.post("/assign")
def assign():
    body = request.get_json(force=True)
    new_a = Assignment(**body)
    current = load_assignments(config.ASSIGNMENTS_FILE)
    # Replace any existing assignment for the same (deck, unit) pair
    current = [a for a in current if not (a.deck_name == new_a.deck_name and a.unit_id == new_a.unit_id)]
    current.append(new_a)
    save_assignments(config.ASSIGNMENTS_FILE, current)
    return jsonify({"ok": True, "assignment": asdict(new_a)})


@api_bp.delete("/assign/<deck>/<unit>")
def unassign(deck: str, unit: str):
    current = load_assignments(config.ASSIGNMENTS_FILE)
    kept = [a for a in current if not (a.deck_name == deck and a.unit_id == unit)]
    save_assignments(config.ASSIGNMENTS_FILE, kept)
    return jsonify({"ok": True, "removed": len(current) - len(kept)})


# ── export ────────────────────────────────────────────────────────────────────

@api_bp.post("/export")
def export():
    assignments = load_assignments(config.ASSIGNMENTS_FILE)
    if not assignments:
        return jsonify({"error": "no assignments"}), 400
    decks_map = _state["decks"]
    units = _state["units"]
    output_dir = config.TOOL_ROOT / "output"
    paths = run_export(assignments, decks_map, units, output_dir)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in paths.values():
            zf.write(path, arcname=Path(path).name)
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True, download_name="wif_ag_export.zip")


# ── unit icon ─────────────────────────────────────────────────────────────────

@api_bp.get("/unit_icon/<unit_id>")
def unit_icon(unit_id: str):
    units: dict[str, WifUnit] = _state["units"]
    icons: dict[str, Path] = _state["icons"]
    unit = units.get(unit_id)
    if not unit or not unit.button_texture:
        abort(404)
    png = icons.get(unit.button_texture)
    if not png or not png.exists():
        abort(404)
    return send_file(str(png), mimetype="image/png")


# ── refresh ───────────────────────────────────────────────────────────────────

@api_bp.post("/refresh")
def refresh():
    if not config.VANILLA_STRATEGIC_DECKS.exists():
        return jsonify({"error": f"missing {config.VANILLA_STRATEGIC_DECKS}"}), 500
    deck_names = list_decks(config.VANILLA_STRATEGIC_DECKS)
    decks_map = refresh_deck_cache(config.VANILLA_STRATEGIC_DECKS, deck_names, config.CACHE_FILE)
    _state["decks"] = decks_map
    return jsonify({"ok": True, "count": len(decks_map)})
