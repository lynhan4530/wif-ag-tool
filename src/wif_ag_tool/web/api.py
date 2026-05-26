"""REST API for the WIF AG Tool web UI.

Endpoints are session-and-replica oriented:
 * /api/campaigns and /api/sessions  — campaign picker
 * /api/sessions/<slug>/...          — session lifecycle + scoped decks + extract
 * /api/decks/<deck>/vanilla|replica — center + right pane backing data
 * /api/export                        — zip download (scope = session | all)
"""
from __future__ import annotations
import io
import json
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from flask import Blueprint, abort, jsonify, request, send_file

from wif_ag_tool import config, session as session_mod, replicas as replicas_mod
from wif_ag_tool.models import DeckState, WifUnit
from wif_ag_tool.parser.deck_parser import list_decks
from wif_ag_tool.parser.save_parser import list_campaigns
from wif_ag_tool.pipeline import (
    export_from_replicas,
    refresh_deck_cache,
)
from wif_ag_tool.validator.unit_validator import validate_unit_exists, UnitNotFoundError

api_bp = Blueprint("api", __name__)

# In-process state (set by web.app.create_app)
_state: dict[str, Any] = {
    "units": {},
    "decks": {},
    "icons": {},
    "packs": {},           # name → StrategicPack
    "combat_groups": {},   # name → CombatGroup
    "vanilla_units": {},   # name → WifUnit (vanilla parse)
    "divisions": {},       # cfg_name → Division
    "units_csv": {},       # TOKEN → REFTEXT
}


def set_state(
    *,
    units: dict[str, WifUnit] | None = None,
    decks: dict[str, DeckState] | None = None,
    icons: dict[str, Path] | None = None,
    packs: dict | None = None,
    combat_groups: dict | None = None,
    vanilla_units: dict[str, WifUnit] | None = None,
    divisions: dict | None = None,
    units_csv: dict[str, str] | None = None,
) -> None:
    if units is not None:        _state["units"] = units
    if decks is not None:        _state["decks"] = decks
    if icons is not None:        _state["icons"] = icons
    if packs is not None:        _state["packs"] = packs
    if combat_groups is not None: _state["combat_groups"] = combat_groups
    if vanilla_units is not None: _state["vanilla_units"] = vanilla_units
    if divisions is not None:    _state["divisions"] = divisions
    if units_csv is not None:    _state["units_csv"] = units_csv


def _deck_label(deck_name: str) -> dict:
    """Resolve a deck name → friendly display label via Divisions.ndf + UNITS.csv.

    Returns ``{display_name, short, resolved}``. ``resolved=False`` means the LOC
    token did not land in any CSV — UI paints a ⚠ badge in that case.
    """
    short = deck_name.replace("Descriptor_Deck_pion_", "")
    deck = _state["decks"].get(deck_name)
    div = None
    if deck and deck.division_ref:
        div = _state["divisions"].get(deck.division_ref)
    if div and div.division_name_token:
        ref = _state["units_csv"].get(div.division_name_token)
        if ref:
            # Tail = part of deck name not covered by division ref
            # e.g. deck pion_RDA_10MSD_16MSR_2 / division RDA_10MSD_solo → "16MSR_2"
            tail = _deck_tail(short, deck.division_ref)
            label = f"{ref} — {tail}" if tail else ref
            return {"display_name": label, "short": short, "resolved": True}
    # Fallback: prettify the short deck id
    pretty = short.replace("_", " ")
    return {"display_name": pretty, "short": short, "resolved": False}


def _deck_tail(short: str, division_ref: str) -> str:
    """Strip the division-ref prefix from a deck's short name so only the unique tail remains.

    division_ref ``RDA_10MSD_solo`` → prefix ``RDA_10MSD_``;
    short ``RDA_10MSD_16MSR_2`` → tail ``16MSR_2``.
    """
    base = division_ref.replace("_solo", "").replace("_multi", "")
    if short.startswith(base + "_"):
        return short[len(base) + 1:].replace("_", " ")
    return short.replace("_", " ")


def _serialize_unit(u: WifUnit) -> dict:
    """Unit payload for API responses. Adds a pretty-id fallback for display_name."""
    d = asdict(u)
    if not d.get("display_name"):
        d["display_name"] = u.name.removeprefix("WF_").replace("_", " ")
        d["display_resolved"] = False
    else:
        d["display_resolved"] = True
    return d


def _lookup_unit(unit_id: str) -> WifUnit | None:
    """Look up *unit_id* in WIF then vanilla maps."""
    return _state["units"].get(unit_id) or _state["vanilla_units"].get(unit_id)


# ── campaigns + sessions picker ──────────────────────────────────────────────

@api_bp.get("/campaigns")
def campaigns():
    """Group .sav3 files by campaign name. Returns one entry per distinct campaign."""
    raw = list_campaigns(config.SAVES_DIR)
    grouped: dict[str, dict] = {}
    for c in raw:
        key = c.get("campaign") or "(unknown)"
        if key not in grouped:
            grouped[key] = {
                "campaign": key,
                "slug": session_mod.slugify(key),
                "factions_from_save": [],
                "missions_seen": [],
                "save_count": 0,
            }
        g = grouped[key]
        g["save_count"] += 1
        for f in c.get("factions") or []:
            if f not in g["factions_from_save"]:
                g["factions_from_save"].append(f)
        m = c.get("mission")
        if m and m not in g["missions_seen"]:
            g["missions_seen"].append(m)
    return jsonify(sorted(grouped.values(), key=lambda x: x["campaign"]))


@api_bp.get("/sessions")
def sessions_list():
    return jsonify(session_mod.list_sessions())


@api_bp.post("/sessions")
def sessions_create():
    body = request.get_json(force=True) or {}
    campaign = (body.get("campaign") or "").strip()
    if not campaign:
        return jsonify({"error": "campaign name required"}), 400
    factions = body.get("factions") or []
    missions = body.get("missions") or []
    slug = body.get("slug")
    payload = session_mod.create_session(campaign, factions, missions, slug=slug)
    return jsonify(payload), 201


@api_bp.get("/sessions/<slug>")
def sessions_get(slug: str):
    s = session_mod.load_session(slug)
    if s is None:
        return jsonify({"error": "session not found"}), 404
    return jsonify(s)


@api_bp.patch("/sessions/<slug>")
def sessions_patch(slug: str):
    s = session_mod.load_session(slug)
    if s is None:
        return jsonify({"error": "session not found"}), 404
    body = request.get_json(force=True) or {}
    if "nation_scope" in body:
        s["nation_scope"] = list(body["nation_scope"])
    if "missions_seen" in body:
        s["missions_seen"] = list(body["missions_seen"])
    if "campaign" in body and body["campaign"]:
        s["campaign"] = body["campaign"]
    saved = session_mod.save_session(s)
    return jsonify(saved)


@api_bp.delete("/sessions/<slug>")
def sessions_delete(slug: str):
    ok = session_mod.delete_session(slug)
    if not ok:
        return jsonify({"error": "session not found"}), 404
    return jsonify({"ok": True})


@api_bp.get("/sessions/<slug>/decks")
def sessions_decks(slug: str):
    s = session_mod.load_session(slug)
    if s is None:
        return jsonify({"error": "session not found"}), 404
    decks_map: dict[str, DeckState] = _state["decks"]
    scoped = session_mod.scope_decks(s.get("nation_scope") or [], decks_map.keys())
    store = replicas_mod.load_replicas()
    return jsonify([
        {
            "name": name,
            "pack_count": len(decks_map[name].pack_list),
            "next_index": decks_map[name].next_index,
            "has_replica": bool(store.get(name, {}).get("saved")),
            "replica_unit_count": len(store.get(name, {}).get("units", [])),
            **_deck_label(name),
        }
        for name in scoped
    ])


@api_bp.post("/sessions/<slug>/extract")
def sessions_extract(slug: str):
    s = session_mod.load_session(slug)
    if s is None:
        return jsonify({"error": "session not found"}), 404
    decks_map: dict[str, DeckState] = _state["decks"]
    scoped = set(session_mod.scope_decks(s.get("nation_scope") or [], decks_map.keys()))
    store = replicas_mod.load_replicas()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("session.json", json.dumps(s, indent=2))
        for name, entry in store.items():
            if name in scoped and entry.get("saved"):
                zf.writestr(f"replicas/{name}.json", json.dumps(entry, indent=2))
    buf.seek(0)
    fname = f"wif_session_{slug}.zip"
    return send_file(buf, mimetype="application/zip", as_attachment=True, download_name=fname)


# ── decks ────────────────────────────────────────────────────────────────────

@api_bp.get("/decks/<deck_name>/vanilla")
def decks_vanilla(deck_name: str):
    """Center pane: vanilla deck contents grouped by combat group."""
    decks_map: dict[str, DeckState] = _state["decks"]
    if deck_name not in decks_map:
        return jsonify({"error": "deck not found"}), 404
    deck = decks_map[deck_name]
    packs = _state["packs"]
    combat_groups = _state["combat_groups"]

    def resolve(idx: int) -> dict:
        if idx < 0 or idx >= len(deck.pack_list):
            return {"index": idx, "pack_name": None, "unit": None, "xp": None}
        pack_name = deck.pack_list[idx]
        pk = packs.get(pack_name)
        return {
            "index": idx,
            "pack_name": pack_name,
            "unit": _unit_short(pk.unit) if pk else None,
            "transport": _unit_short(pk.transport) if pk and pk.transport else None,
            "xp": getattr(pk, "xp", None) if pk else None,
        }

    cg_tree: list[dict] = []
    for cg_ref in deck.combat_group_list:
        cg = combat_groups.get(cg_ref)
        if cg is None:
            cg_tree.append({"name": cg_ref, "token": "", "smart_groups": [], "missing": True})
            continue
        cg_tree.append({
            "name": cg.name,
            "token": cg.token,
            "smart_groups": [
                {
                    "name": sg.name,
                    "is_hq": sg.is_hq,
                    "packs": [
                        {**resolve(idx), "count": count}
                        for (idx, count) in sg.pack_indices
                    ],
                }
                for sg in cg.smart_groups
            ],
        })
    return jsonify({
        "name": deck.name,
        "pack_count": len(deck.pack_list),
        "combat_groups": cg_tree,
        **_deck_label(deck.name),
    })


@api_bp.get("/decks/<deck_name>/replica")
def decks_replica(deck_name: str):
    decks_map: dict[str, DeckState] = _state["decks"]
    if deck_name not in decks_map:
        return jsonify({"error": "deck not found"}), 404
    store = replicas_mod.load_replicas()
    entry = store.get(deck_name) or {"saved": False, "units": []}
    return jsonify({"deck_name": deck_name, **entry})


@api_bp.put("/decks/<deck_name>/replica")
def decks_replica_save(deck_name: str):
    decks_map: dict[str, DeckState] = _state["decks"]
    if deck_name not in decks_map:
        return jsonify({"error": "deck not found"}), 404
    body = request.get_json(force=True) or {}
    raw_units = body.get("units") or []
    if not raw_units:
        return jsonify({"error": "units list must be non-empty"}), 400
    # Validate every unit_id exists in the WIF catalogue
    units = _state["units"]
    for row in raw_units:
        try:
            validate_unit_exists(row.get("unit_id", ""), units)
        except UnitNotFoundError as e:
            return jsonify({"error": str(e)}), 400
        tid = row.get("transport_id")
        if tid:
            if tid not in _state["units"] and tid not in _state["vanilla_units"]:
                return jsonify({"error": f"Transport unit not found: {tid}"}), 400
    try:
        entry = replicas_mod.save_replica(deck_name, raw_units)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"deck_name": deck_name, **entry})


@api_bp.delete("/decks/<deck_name>/replica")
def decks_replica_delete(deck_name: str):
    ok = replicas_mod.delete_replica(deck_name)
    if not ok:
        return jsonify({"error": "no replica to delete"}), 404
    return jsonify({"ok": True})


# ── wif units (modal source) ────────────────────────────────────────────────

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
        if q and q not in u.name.lower() and q not in (u.display_name or "").lower():
            continue
        out.append(_serialize_unit(u))
    return jsonify(out)


@api_bp.get("/vanilla_units")
def vanilla_units():
    """Mirror of /wif_units for vanilla. The SPA loads this once for tooltip lookups."""
    nation = request.args.get("nation")
    role = request.args.get("role")
    q = (request.args.get("q") or "").lower()
    units: dict[str, WifUnit] = _state["vanilla_units"]
    out = []
    for u in units.values():
        if nation and u.nation != nation:
            continue
        if role and role != "all" and u.role != role:
            continue
        if q and q not in u.name.lower() and q not in (u.display_name or "").lower():
            continue
        out.append(_serialize_unit(u))
    return jsonify(out)


@api_bp.get("/unit_icon/<unit_id>")
def unit_icon(unit_id: str):
    icons: dict[str, Path] = _state["icons"]
    unit = _lookup_unit(unit_id)
    if not unit or not unit.button_texture:
        abort(404)
    png = icons.get(unit.button_texture)
    if not png or not png.exists():
        abort(404)
    resp = send_file(str(png), mimetype="image/png")
    # Icons are stable per build; allow the browser to cache for a week so hover
    # storms don't hammer the dev server.
    resp.headers["Cache-Control"] = "public, max-age=604800"
    return resp


# ── refresh ──────────────────────────────────────────────────────────────────

@api_bp.post("/refresh")
def refresh():
    if not config.VANILLA_STRATEGIC_DECKS.exists():
        return jsonify({"error": f"missing {config.VANILLA_STRATEGIC_DECKS}"}), 500
    deck_names = list_decks(config.VANILLA_STRATEGIC_DECKS)
    decks_map = refresh_deck_cache(config.VANILLA_STRATEGIC_DECKS, deck_names, config.CACHE_FILE)
    _state["decks"] = decks_map
    return jsonify({"ok": True, "count": len(decks_map)})


# ── export NDF ───────────────────────────────────────────────────────────────

@api_bp.post("/export")
def export():
    body = request.get_json(silent=True) or {}
    scope = body.get("scope") or "all"
    decks_map = _state["decks"]
    units = _state["units"]
    if not decks_map:
        return jsonify({"error": "no deck cache loaded — run refresh"}), 400

    scope_decks_list: list[str] | None = None
    if scope == "session":
        slug = body.get("session_slug")
        if not slug:
            return jsonify({"error": "session_slug required for scope=session"}), 400
        s = session_mod.load_session(slug)
        if s is None:
            return jsonify({"error": "session not found"}), 404
        scope_decks_list = session_mod.scope_decks(s.get("nation_scope") or [], decks_map.keys())
    elif scope != "all":
        return jsonify({"error": f"unknown scope: {scope}"}), 400

    output_dir = config.TOOL_ROOT / "output"
    paths = export_from_replicas(
        decks_map, units, output_dir, scope_decks=scope_decks_list,
    )
    if not any(p.read_text(encoding="utf-8").strip() for p in paths.values()):
        return jsonify({"error": "no saved replicas in scope"}), 400

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in paths.values():
            zf.write(path, arcname=Path(path).name)
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True, download_name="wif_ag_export.zip")


# ── helpers ──────────────────────────────────────────────────────────────────

def _unit_short(unit_ref: str | None) -> str | None:
    """`$/GFX/Unit/Descriptor_Unit_<name>` → `<name>`."""
    if not unit_ref:
        return None
    return unit_ref.rsplit("Descriptor_Unit_", 1)[-1]


# Legacy /api/assign, /api/decks, /api/deck/<name> endpoints are gone.
# Old UI clients will see 404 from Flask, which is the intended cue to refresh.
