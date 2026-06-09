"""REST API for the WIF AG Tool web UI.

Endpoints are session-and-replica oriented:
 * /api/campaigns and /api/sessions  — campaign picker
 * /api/sessions/<slug>/...          — session lifecycle + scoped decks + extract
 * /api/decks/<deck>/vanilla|replica — center + right pane backing data
 * /api/export                        — zip download (scope = session | all)
"""
from __future__ import annotations
import io
import os
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
from wif_ag_tool.role_normalize import bucket_matches, normalize_role
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
    "platoons_csv": {},    # TOKEN → REFTEXT
    "wif_weapons": {},
    "vanilla_weapons": {},
    "wif_ammo": {},
    "vanilla_ammo": {},
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
    platoons_csv: dict[str, str] | None = None,
    wif_weapons: dict | None = None,
    vanilla_weapons: dict | None = None,
    wif_ammo: dict | None = None,
    vanilla_ammo: dict | None = None,
) -> None:
    if units is not None:        _state["units"] = units
    if decks is not None:        _state["decks"] = decks
    if icons is not None:        _state["icons"] = icons
    if packs is not None:        _state["packs"] = packs
    if combat_groups is not None: _state["combat_groups"] = combat_groups
    if vanilla_units is not None: _state["vanilla_units"] = vanilla_units
    if divisions is not None:    _state["divisions"] = divisions
    if units_csv is not None:    _state["units_csv"] = units_csv
    if platoons_csv is not None: _state["platoons_csv"] = platoons_csv
    if wif_weapons is not None:    _state["wif_weapons"] = wif_weapons
    if vanilla_weapons is not None: _state["vanilla_weapons"] = vanilla_weapons
    if wif_ammo is not None:       _state["wif_ammo"] = wif_ammo
    if vanilla_ammo is not None:   _state["vanilla_ammo"] = vanilla_ammo


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
    if div:
        ref = div.display_name or _state["units_csv"].get(div.division_name_token)
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


def _serialize_unit(u: WifUnit, source: str = "wif") -> dict:
    """Unit payload for API responses. Adds a pretty-id fallback for display_name
    and tags the unit's source so the SPA can show WIF vs vanilla."""
    d = asdict(u)
    if not d.get("display_name"):
        d["display_name"] = u.name.removeprefix("WF_").replace("_", " ")
        d["display_resolved"] = False
    else:
        d["display_resolved"] = True
    d["source"] = source
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
    if "target_mod_dir" in body:
        s["target_mod_dir"] = str(body["target_mod_dir"]).strip()
    if "game_dir" in body:
        s["game_dir"] = str(body["game_dir"]).strip()
    if "export_dir" in body:
        s["export_dir"] = str(body["export_dir"]).strip()
    saved = session_mod.save_session(s)
    return jsonify(saved)


@api_bp.delete("/sessions/<slug>")
def sessions_delete(slug: str):
    ok = session_mod.delete_session(slug)
    if not ok:
        return jsonify({"error": "session not found"}), 404
    return jsonify({"ok": True})


@api_bp.post("/sessions/<slug>/export_direct")
def sessions_export_direct(slug: str):
    s = session_mod.load_session(slug)
    if s is None:
        return jsonify({"error": "session not found"}), 404

    target_mod_dir = s.get("target_mod_dir", "").strip()
    custom_export_dir = s.get("export_dir", "").strip()

    if custom_export_dir:
        export_path = Path(custom_export_dir)
    elif target_mod_dir:
        export_path = Path(target_mod_dir) / "GameData"
    else:
        export_path = config.TOOL_ROOT / "output"

    try:
        export_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return jsonify({"error": f"Failed to create export directory {export_path}: {str(e)}"}), 500

    if target_mod_dir:
        mod_name = Path(target_mod_dir).name
    else:
        mod_name = "CRM_ArmyGeneral"

    decks_map = _state["decks"]
    units = _state["units"]
    combat_groups = _state.get("combat_groups") or {}
    if not decks_map:
        return jsonify({"error": "No deck cache loaded — run refresh first"}), 400

    body = request.get_json(silent=True) or {}
    scope = request.args.get("scope") or body.get("scope") or "all"

    scoped = None
    if scope == "session":
        scoped = session_mod.scope_decks(s.get("nation_scope") or [], decks_map.keys())

    store = replicas_mod.load_replicas()
    assignments = replicas_mod.replicas_to_assignments(store, scope_decks=scoped)

    if not assignments:
        return jsonify({"error": "No saved replicas in scope to export. Create a replica deck first."}), 400

    decks_dir = export_path / "Generated" / "Gameplay" / "Decks"
    base_decks_ndf  = decks_dir / "StrategicDecks.ndf"
    base_packs_ndf  = decks_dir / "StrategicPacks.ndf"
    base_groups_ndf = decks_dir / "StrategicCombatGroups.ndf"
    base_csv        = export_path / "Localisation" / mod_name / "PLATOONS.csv"
    base_units_ndf  = export_path / "Generated" / "Gameplay" / "Gfx" / "UniteDescriptor.ndf"
    base_ammo_ndf   = export_path / "Generated" / "Gameplay" / "Gfx" / "Ammunition.ndf"
    direct_paths = {
        "summary": decks_dir / "StrategicDecks_patch_summary.txt",
        "csv": base_csv
    }

    for p in direct_paths.values():
        p.parent.mkdir(parents=True, exist_ok=True)
    decks_dir.mkdir(parents=True, exist_ok=True)

    # Older versions shipped sidecar files (StrategicPacks_additions.ndf,
    # StrategicCombatGroups_additions.ndf, StrategicDecks_patch.ndf). The
    # WARNO compiler only ingests the canonical base files, so the sidecars
    # were silently ignored — leaving deck refs dangling. Clean them out.
    for stale_name in (
        "StrategicPacks_additions.ndf",
        "StrategicCombatGroups_additions.ndf",
        "StrategicDecks_patch.ndf",
    ):
        stale = decks_dir / stale_name
        if stale.exists():
            try:
                stale.unlink()
            except Exception:
                pass

    base_files = [base_decks_ndf, base_packs_ndf, base_groups_ndf, base_csv]
    if base_units_ndf.exists():
        base_files.append(base_units_ndf)
    if base_ammo_ndf.exists():
        base_files.append(base_ammo_ndf)

    # Snapshot each base file to .orig on first export, then restore from .orig on
    # every subsequent export so repeated runs apply on a canvas instead of
    # accumulating duplicate definitions.
    for base in base_files:
        pristine = base.with_suffix(base.suffix + ".orig")
        
        if "PYTEST_CURRENT_TEST" not in os.environ:
            clean_source = None
            if base.name == "StrategicDecks.ndf":
                clean_source = config.VANILLA_STRATEGIC_DECKS
            elif base.name == "StrategicPacks.ndf":
                clean_source = config.VANILLA_STRATEGIC_PACKS
            elif base.name == "StrategicCombatGroups.ndf":
                clean_source = config.VANILLA_COMBAT_GROUPS

            pristine_bytes = None
            if clean_source and clean_source.exists():
                try:
                    pristine_bytes = clean_source.read_bytes()
                except Exception:
                    pass

            # Fall back to extracting from base.zip if clean_source isn't available
            if pristine_bytes is None and target_mod_dir:
                base_zip_path = Path(target_mod_dir) / "base.zip"
                if base_zip_path.exists():
                    try:
                        with zipfile.ZipFile(base_zip_path, 'r') as z:
                            zip_internal_path = f"GameData/Generated/Gameplay/Decks/{base.name}"
                            if base.name == "PLATOONS.csv":
                                zip_internal_path = "Localisation/CRM_ArmyGeneral/PLATOONS.csv"
                            pristine_bytes = z.read(zip_internal_path)
                    except Exception:
                        pass

            if pristine_bytes is not None:
                need_recreate = False
                if not pristine.exists():
                    need_recreate = True
                else:
                    try:
                        # If the .orig file bytes differ from the clean baseline, it is either dirty or outdated
                        if pristine.read_bytes() != pristine_bytes:
                            need_recreate = True
                    except Exception:
                        need_recreate = True
                
                if need_recreate:
                    pristine.write_bytes(pristine_bytes)

        if base.exists() and not pristine.exists():
            pristine.write_bytes(base.read_bytes())
        elif pristine.exists():
            base.write_bytes(pristine.read_bytes())

    # Full-replacement model: build the exact new lists for every replica'd deck.
    # Pack indices count from 0 (build_export_blocks seeds an empty DeckState per deck).
    from wif_ag_tool.pipeline import build_export_blocks
    from wif_ag_tool.generator.deck_patcher import (
        generate_deck_patch, replace_deck_lists, apply_combat_group_patches,
    )
    try:
        packs_blocks, groups_blocks, deck_lists = build_export_blocks(
            assignments, decks_map, units, combat_groups)
    except ValueError as e:
        # Pack-index invariant violated — would crash on pawn click. See NDF_REFERENCE.md §4.
        return jsonify({"error": str(e)}), 500

    deck_patches = []
    for deck_name, (pack_refs, group_refs) in deck_lists.items():
        # Replace the deck's two lists outright so the deck IS exactly the replica:
        # only these packs, only these combat groups. Decks without a replica never
        # appear here, so they stay untouched vanilla.
        try:
            replace_deck_lists(base_decks_ndf, deck_name, pack_refs, group_refs)
        except KeyError:
            # Deck not present in the base file (e.g. exporting against vanilla rather
            # than the WIF source). Fall back to a summary entry only.
            pass
        deck_patches.append(generate_deck_patch(deck_name, pack_refs, group_refs))

    from wif_ag_tool.generator.localisation import generate_platoons_rows
    csv_text = generate_platoons_rows(assignments, units, decks=decks_map, combat_groups=combat_groups)

    try:
        # Append new pack defs to the base StrategicPacks.ndf so the compiler picks
        # them up (sidecar _additions.ndf files are ignored by the WARNO compiler).
        if packs_blocks:
            with base_packs_ndf.open("a", encoding="utf-8") as f:
                f.write("\n\n// === WIF AG additions ===\n\n")
                f.write("\n\n".join(packs_blocks))
                f.write("\n")
        if groups_blocks:
            apply_combat_group_patches(base_groups_ndf, groups_blocks)
        direct_paths["summary"].write_text("\n\n".join(deck_patches) + "\n", encoding="utf-8")
        # PLATOONS.csv is the mod's full localisation table (thousands of vanilla +
        # WIF rows). generate_platoons_rows only emits our new AG tokens, so we must
        # APPEND them (dropping its leading "TOKEN";"REFTEXT" header) instead of
        # overwriting — otherwise every other platoon/unit name resolves to a missing
        # token in-game. This mirrors the append-in-place treatment of
        # StrategicPacks.ndf above; the .orig restore at the top keeps it idempotent.
        new_rows = csv_text.split("\n", 1)[1] if "\n" in csv_text else ""
        existing_csv = base_csv.read_text(encoding="utf-8") if base_csv.exists() else ""
        if existing_csv.strip():
            merged = existing_csv if existing_csv.endswith("\n") else existing_csv + "\n"
            if new_rows.strip():
                merged += new_rows if new_rows.endswith("\n") else new_rows + "\n"
            base_csv.write_text(merged, encoding="utf-8")
        else:
            base_csv.write_text(csv_text, encoding="utf-8")

        # Apply stats overrides to UniteDescriptor.ndf and Ammunition.ndf
        tactical_overrides = load_tactical_overrides()
        unit_overrides = {}
        
        # Populate with tactical unit overrides first
        for uid, fields in tactical_overrides.get("units", {}).items():
            unit_overrides[uid] = dict(fields)
            
        # Merge strategic attack/defense overrides from assignments
        for a in assignments:
            if a.attack_override is not None or a.defense_override is not None:
                if a.unit_id not in unit_overrides:
                    unit_overrides[a.unit_id] = {}
                # Ensure they are dict overrides
                if isinstance(unit_overrides[a.unit_id], dict):
                    if a.attack_override is not None:
                        unit_overrides[a.unit_id]["attack_override"] = a.attack_override
                    if a.defense_override is not None:
                        unit_overrides[a.unit_id]["defense_override"] = a.defense_override
                        
        if base_units_ndf.exists() and unit_overrides:
            from wif_ag_tool.generator.unit_patcher import patch_unit_stats
            patch_unit_stats(base_units_ndf, unit_overrides)
            
        # Apply ammunition overrides to Ammunition.ndf
        ammo_overrides = tactical_overrides.get("ammo", {})
        if base_ammo_ndf.exists() and ammo_overrides:
            from wif_ag_tool.generator.ammo_patcher import patch_ammo_stats
            patch_ammo_stats(base_ammo_ndf, ammo_overrides)
    except Exception as e:
        return jsonify({"error": f"Failed to write export files: {str(e)}"}), 500

    return jsonify({
        "ok": True,
        "message": f"Successfully exported files directly to {export_path.resolve()}",
        "paths": {k: str(v.resolve()) for k, v in direct_paths.items()}
    })


@api_bp.post("/sessions/<slug>/build")
def sessions_build(slug: str):
    s = session_mod.load_session(slug)
    if s is None:
        return jsonify({"error": "session not found"}), 404

    target_mod_dir = s.get("target_mod_dir", "").strip()
    if not target_mod_dir:
        return jsonify({"error": "No target mod directory configured in settings. Go to settings and configure it."}), 400

    mod_path = Path(target_mod_dir)
    if not mod_path.exists():
        return jsonify({"error": f"Target mod directory does not exist: {target_mod_dir}"}), 400

    gen_bat = mod_path / "GenerateMod.bat"
    if not gen_bat.exists():
        return jsonify({"error": f"GenerateMod.bat not found inside mod directory: {target_mod_dir}"}), 400

    # Pre-build Verification Check
    custom_export_dir = s.get("export_dir", "").strip()
    if custom_export_dir:
        export_path = Path(custom_export_dir)
    else:
        export_path = mod_path / "GameData"

    mod_name = mod_path.name
    required_files = [
        export_path / "Generated" / "Gameplay" / "Decks" / "StrategicPacks.ndf",
        export_path / "Generated" / "Gameplay" / "Decks" / "StrategicCombatGroups.ndf",
        export_path / "Generated" / "Gameplay" / "Decks" / "StrategicDecks.ndf",
        export_path / "Localisation" / mod_name / "PLATOONS.csv"
    ]

    missing_files = [str(f.resolve()) for f in required_files if not f.exists()]
    if missing_files:
        return jsonify({
            "error": "Pre-build check failed: Export files are missing. Click 'Export Mod' first to generate them.",
            "missing_files": missing_files
        }), 400

    import subprocess
    try:
        res = subprocess.run(
            [str(gen_bat)],
            cwd=str(mod_path),
            shell=True,
            capture_output=True,
            text=True,
            input="\n",
            timeout=300,
        )
        return jsonify({
            "ok": res.returncode == 0,
            "returncode": res.returncode,
            "stdout": res.stdout,
            "stderr": res.stderr,
        })
    except subprocess.TimeoutExpired as e:
        return jsonify({
            "error": "Mod compilation timed out after 300 seconds.",
            "stdout": e.stdout or "",
            "stderr": e.stderr or "",
        }), 500
    except Exception as e:
        return jsonify({"error": f"Failed to execute mod builder: {str(e)}"}), 500


@api_bp.get("/sessions/<slug>/decks")
def sessions_decks(slug: str):
    s = session_mod.load_session(slug)
    if s is None:
        return jsonify({"error": "session not found"}), 404
    decks_map: dict[str, DeckState] = _state["decks"]
    nations_str = request.args.get("nations")
    if nations_str is not None:
        nations = [n.strip() for n in nations_str.split(",") if n.strip()]
    else:
        nations = s.get("nation_scope") or []
    scoped = session_mod.scope_decks(nations, decks_map.keys())
    store = replicas_mod.load_replicas()
    def _count_replica_units(entry: dict) -> int:
        """Count total units across all groups/platoons in a hierarchical replica."""
        total = 0
        # Handle hierarchical format
        for g in entry.get("groups", []):
            for p in g.get("platoons", []):
                total += len(p.get("units", []))
        # Fallback: old flat format
        if total == 0:
            total = len(entry.get("units", []))
        return total

    return jsonify([
        {
            "name": name,
            "pack_count": len(decks_map[name].pack_list),
            "next_index": decks_map[name].next_index,
            "has_replica": bool(store.get(name, {}).get("saved")),
            "replica_unit_count": _count_replica_units(store.get(name, {})),
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

        resolved_sgs = []
        for sg in cg.smart_groups:
            resolved_sgs.append({
                "name": sg.name,
                "is_hq": sg.is_hq,
                "packs": [
                    {**resolve(idx), "count": count}
                    for (idx, count) in sg.pack_indices
                ],
            })

        role_counters: dict[str, int] = {}
        for sg_res in resolved_sgs:
            sg_name = sg_res["name"]
            csv_dn = _state.get("platoons_csv", {}).get(sg_name)

            # If csv_dn is not empty and is not the raw token name, use it!
            # Raw tokens are exactly 10 uppercase characters.
            is_raw_token = sg_name and len(sg_name) == 10 and sg_name.isupper() and sg_name.isalpha()
            if csv_dn and csv_dn != sg_name and not is_raw_token:
                sg_res["display_name"] = csv_dn
                continue

            # Otherwise, use the heuristic!
            if sg_res["is_hq"]:
                sg_res["display_name"] = _get_localized_fallback_name(
                    primary="",
                    is_hq=True,
                    count=1,
                    cg_name=cg.name,
                    deck_name=deck_name,
                )
            else:
                roles = []
                for p in sg_res["packs"]:
                    unit_short = p.get("unit")
                    if unit_short:
                        unit_obj = _lookup_unit(unit_short)
                        if unit_obj:
                            r = normalize_role(unit_obj.role)
                            roles.append(r)
                            if r == "unknown":
                                u_lower = unit_short.lower()
                                if "mortar" in u_lower or "supply" in u_lower or "fob" in u_lower or "hemtt" in u_lower or "ural" in u_lower or "man" in u_lower:
                                    roles.append("supply")

                # Determine primary role
                if "recon" in roles:
                    primary = "RECON"
                elif "armor" in roles or any("abrams" in p.get("unit", "").lower() or "t80" in p.get("unit", "").lower() or "leopard" in p.get("unit", "").lower() for p in sg_res["packs"] if p.get("unit")):
                    primary = "TANK"
                elif "engineer" in roles or any("engineer" in p.get("unit", "").lower() or "pionier" in p.get("unit", "").lower() or "sapper" in p.get("unit", "").lower() for p in sg_res["packs"] if p.get("unit")):
                    primary = "ENGINEER"
                elif "aa" in roles or any("stinger" in p.get("unit", "").lower() or "shorad" in p.get("unit", "").lower() or "flak" in p.get("unit", "").lower() for p in sg_res["packs"] if p.get("unit")):
                    primary = "AA"
                elif "supply" in roles or any("supply" in p.get("unit", "").lower() or "fob" in p.get("unit", "").lower() or "hemtt" in p.get("unit", "").lower() or "lmtv" in p.get("unit", "").lower() for p in sg_res["packs"] if p.get("unit")):
                    primary = "LOGISTICS"
                elif "artillery" in roles or "support" in roles or any("mortar" in p.get("unit", "").lower() or "ural" in p.get("unit", "").lower() or "man" in p.get("unit", "").lower() for p in sg_res["packs"] if p.get("unit")):
                    primary = "SUPPORT"
                elif "infantry" in roles or any("inf" in p.get("unit", "").lower() or "rifle" in p.get("unit", "").lower() or "chasseur" in p.get("unit", "").lower() or "dismount" in p.get("unit", "").lower() or "airborne" in p.get("unit", "").lower() for p in sg_res["packs"] if p.get("unit")):
                    primary = "RIFLE"
                elif "helicopter" in roles or "heli" in roles:
                    primary = "HELI"
                else:
                    primary = "PLATOON"

                role_counters[primary] = role_counters.get(primary, 0) + 1
                count = role_counters[primary]

                sg_res["display_name"] = _get_localized_fallback_name(
                    primary=primary,
                    is_hq=False,
                    count=count,
                    cg_name=cg.name,
                    deck_name=deck_name,
                )

        cg_tree.append({
            "name": cg.name,
            "token": cg.token,
            "smart_groups": resolved_sgs,
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
    raw_groups = body.get("groups")
    raw_units = body.get("units")

    if not raw_groups and not raw_units:
        return jsonify({"error": "payload must contain non-empty groups or units list"}), 400

    # Gather flat units for validation
    units_to_validate = []
    if raw_groups:
        for g in raw_groups:
            for p in g.get("platoons", []):
                for u in p.get("units", []):
                    units_to_validate.append(u)
    else:
        units_to_validate = raw_units

    # unit_id may reference either a WIF or a vanilla unit — accept either.
    units = _state["units"]
    vanilla_units = _state["vanilla_units"]
    for row in units_to_validate:
        try:
            validate_unit_exists(row.get("unit_id", ""), units, vanilla_units)
        except UnitNotFoundError as e:
            return jsonify({"error": str(e)}), 400
        tid = row.get("transport_id")
        if tid:
            if tid not in _state["units"] and tid not in _state["vanilla_units"]:
                return jsonify({"error": f"Transport unit not found: {tid}"}), 400

    try:
        if raw_groups:
            entry = replicas_mod.save_replica(deck_name, raw_groups)
        else:
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
    if nation == "RDA":
        nation = "DDR"
    role = request.args.get("role")
    q = (request.args.get("q") or "").lower()
    units: dict[str, WifUnit] = _state["units"]
    out = []
    for u in units.values():
        if nation and u.nation != nation:
            continue
        if role and role != "all" and not bucket_matches(u.role, role):
            continue
        if q and q not in u.name.lower() and q not in (u.display_name or "").lower():
            continue
        out.append(_serialize_unit(u, source="wif"))
    return jsonify(out)


@api_bp.get("/vanilla_units")
def vanilla_units():
    """Mirror of /wif_units for vanilla. The SPA loads this once for tooltip lookups
    and for the cross-source picker in the Add Unit modal."""
    nation = request.args.get("nation")
    if nation == "RDA":
        nation = "DDR"
    role = request.args.get("role")
    q = (request.args.get("q") or "").lower()
    units: dict[str, WifUnit] = _state["vanilla_units"]
    out = []
    for u in units.values():
        if nation and u.nation != nation:
            continue
        if role and role != "all" and not bucket_matches(u.role, role):
            continue
        if q and q not in u.name.lower() and q not in (u.display_name or "").lower():
            continue
        out.append(_serialize_unit(u, source="vanilla"))
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


def load_tactical_overrides() -> dict:
    if config.STATS_OVERRIDES_FILE.exists():
        try:
            return json.loads(config.STATS_OVERRIDES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"units": {}, "ammo": {}}


def save_tactical_overrides(overrides: dict) -> None:
    config.STATS_OVERRIDES_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.STATS_OVERRIDES_FILE.write_text(json.dumps(overrides, indent=2), encoding="utf-8")


@api_bp.get("/units/<unit_id>/tactical_stats")
def get_unit_tactical_stats(unit_id: str):
    unit = _lookup_unit(unit_id)
    if not unit:
        abort(404)

    overrides = load_tactical_overrides()
    unit_overrides = overrides.get("units", {}).get(unit_id, {})
    
    response = {
        "unit_id": unit_id,
        "display_name": unit.display_name or unit.name.removeprefix("WF_").replace("_", " "),
        "health": {
            "base": unit.health,
            "override": unit_overrides.get("health")
        },
        "max_suppression": {
            "base": unit.max_suppression,
            "override": unit_overrides.get("max_suppression")
        },
        "supply_capacity": {
            "base": unit.supply_capacity,
            "override": unit_overrides.get("supply_capacity")
        },
        "weapons": []
    }

    weapon_key = unit.weapon_descriptor_ref
    if weapon_key and not weapon_key.startswith("WeaponDescriptor_"):
        weapon_key = f"WeaponDescriptor_{weapon_key}"

    # Search in WIF weapons then vanilla weapons
    ammo_refs = _state["wif_weapons"].get(weapon_key) or _state["vanilla_weapons"].get(weapon_key) or []
    
    for ammo_ref in ammo_refs:
        ammo_base = _state["wif_ammo"].get(ammo_ref) or _state["vanilla_ammo"].get(ammo_ref)
        if ammo_base:
            ammo_override = overrides.get("ammo", {}).get(ammo_ref, {})
            response["weapons"].append({
                "ammo_id": ammo_ref,
                "damage_family": {
                    "base": ammo_base.get("damage_family"),
                    "override": ammo_override.get("damage_family")
                },
                "damage_index": {
                    "base": ammo_base.get("damage_index"),
                    "override": ammo_override.get("damage_index")
                },
                "max_range": {
                    "base": ammo_base.get("max_range"),
                    "override": ammo_override.get("max_range")
                },
                "min_range": {
                    "base": ammo_base.get("min_range"),
                    "override": ammo_override.get("min_range")
                },
                "time_between_shots": {
                    "base": ammo_base.get("time_between_shots"),
                    "override": ammo_override.get("time_between_shots")
                },
                "time_between_salvos": {
                    "base": ammo_base.get("time_between_salvos"),
                    "override": ammo_override.get("time_between_salvos")
                },
                "shots_per_salvo": {
                    "base": ammo_base.get("shots_per_salvo"),
                    "override": ammo_override.get("shots_per_salvo")
                },
                "physical_damages": {
                    "base": ammo_base.get("physical_damages"),
                    "override": ammo_override.get("physical_damages")
                },
                "suppress_damages": {
                    "base": ammo_base.get("suppress_damages"),
                    "override": ammo_override.get("suppress_damages")
                },
                "supply_cost": {
                    "base": ammo_base.get("supply_cost"),
                    "override": ammo_override.get("supply_cost")
                }
            })
            
    return jsonify(response)


@api_bp.put("/units/<unit_id>/tactical_stats")
def put_unit_tactical_stats(unit_id: str):
    unit = _lookup_unit(unit_id)
    if not unit:
        abort(404)

    body = request.get_json(force=True) or {}
    overrides = load_tactical_overrides()

    # 1. Update unit stats
    unit_overrides = {}
    
    health = body.get("health")
    if health is not None:
        try:
            unit_overrides["health"] = int(health)
        except (ValueError, TypeError):
            pass
            
    max_supp = body.get("max_suppression")
    if max_supp is not None:
        try:
            unit_overrides["max_suppression"] = int(max_supp)
        except (ValueError, TypeError):
            pass
            
    supply = body.get("supply_capacity")
    if supply is not None:
        try:
            unit_overrides["supply_capacity"] = int(supply)
        except (ValueError, TypeError):
            pass

    # Clean up empty or null values
    unit_overrides = {k: v for k, v in unit_overrides.items() if v is not None}
    
    if "units" not in overrides:
        overrides["units"] = {}
        
    if unit_overrides:
        overrides["units"][unit_id] = unit_overrides
    elif unit_id in overrides["units"]:
        del overrides["units"][unit_id]

    # 2. Update ammo overrides
    ammo_updates = body.get("ammo") or {}
    if "ammo" not in overrides:
        overrides["ammo"] = {}
        
    for ammo_id, fields in ammo_updates.items():
        if not fields:
            if ammo_id in overrides["ammo"]:
                del overrides["ammo"][ammo_id]
            continue
            
        ammo_ov = {}
        
        # Cast fields properly
        if "damage_family" in fields and fields["damage_family"] is not None:
            ammo_ov["damage_family"] = str(fields["damage_family"])
            
        for float_field in ("time_between_shots", "time_between_salvos", "supply_cost", "physical_damages", "suppress_damages"):
            if float_field in fields and fields[float_field] is not None:
                try:
                    ammo_ov[float_field] = float(fields[float_field])
                except (ValueError, TypeError):
                    pass
                    
        for int_field in ("damage_index", "max_range", "min_range", "shots_per_salvo"):
            if int_field in fields and fields[int_field] is not None:
                try:
                    ammo_ov[int_field] = int(fields[int_field])
                except (ValueError, TypeError):
                    pass

        # Clean null values
        ammo_ov = {k: v for k, v in ammo_ov.items() if v is not None}
        
        if ammo_ov:
            overrides["ammo"][ammo_id] = ammo_ov
        elif ammo_id in overrides["ammo"]:
            del overrides["ammo"][ammo_id]

    save_tactical_overrides(overrides)
    return jsonify({"ok": True})


@api_bp.get("/tactical_stats/summary")
def get_tactical_stats_summary():
    overrides = load_tactical_overrides()
    return jsonify({
        "unit_overrides_count": len(overrides.get("units", {})),
        "ammo_overrides_count": len(overrides.get("ammo", {})),
    })


# ── docs ─────────────────────────────────────────────────────────────────────

@api_bp.get("/howto")
def howto():
    """Serve HOWTO.md as raw markdown.

    The same file is rendered on GitHub at https://github.com/lynhan4530/wif-ag-tool/blob/main/HOWTO.md
    so there is one source of truth and the in-app guide cannot drift from the repo doc.
    """
    path = config.TOOL_ROOT / "HOWTO.md"
    if not path.exists():
        return jsonify({"error": "HOWTO.md missing — please pull latest from main"}), 404
    return path.read_text(encoding="utf-8"), 200, {"Content-Type": "text/markdown; charset=utf-8"}


@api_bp.get("/status")
def status():
    """Return status of system dependencies/reference files (e.g. offline status)."""
    return jsonify({
        "raw_files_available": config.VANILLA_STRATEGIC_DECKS.exists()
    })


# ── refresh ──────────────────────────────────────────────────────────────────

@api_bp.post("/refresh")
def refresh():
    if not config.VANILLA_STRATEGIC_DECKS.exists():
        return jsonify({
            "error": (
                f"Missing vanilla reference file: {config.VANILLA_STRATEGIC_DECKS}\n\n"
                "IMPORTANT: You do not need to refresh the deck cache since the pre-parsed campaign decks "
                "are already committed and loaded from the Git repository. "
                "Refreshing is only necessary after a major WARNO game update, which requires "
                "extracting the game's base files and configuring the Vanilla Reference path."
            )
        }), 500
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


def _get_localized_fallback_name(primary: str, is_hq: bool, count: int, cg_name: str, deck_name: str) -> str:
    """Generate localized platoon names when translation is missing from PLATOONS.csv."""
    deck_lower = deck_name.lower()
    cg_lower = cg_name.lower()

    is_german = any(x in deck_lower for x in ["_rfa_", "_rda_", "_ddr_", "_ger_"])
    is_french = "_fr_" in deck_lower
    is_russian = any(x in deck_lower for x in ["_sov_", "_rus_"])

    is_artillery = any(x in cg_lower for x in ["art", "artillerie", "bty", "bataillon_artillerie"])

    if is_german:
        if is_hq:
            return "STAB"
        else:
            if is_artillery:
                return f"{count}. BATTERIE"
            elif primary == "RECON":
                return f"{count}. AUFKLÄRUNGSZUG"
            elif primary == "TANK":
                return f"{count}. PANZERZUG"
            elif primary == "ENGINEER":
                return f"{count}. PIONIERZUG"
            elif primary == "AA":
                return f"{count}. FLUGABWEHRZUG"
            elif primary == "LOGISTICS":
                return "NACHSCHUBGRUPPE" if count == 1 else f"NACHSCHUBGRUPPE {count}"
            elif primary == "RIFLE":
                return f"{count}. INFANTERIEZUG"
            elif primary == "SUPPORT":
                return "UNTERSTÜTZUNGSGRUPPE" if count == 1 else f"UNTERSTÜTZUNGSGRUPPE {count}"
            elif primary == "HELI":
                return f"{count}. HUBSCHRAUBERZUG"
            else:
                return f"{count}. ZUG"

    elif is_french:
        def _fr_ord(n: int) -> str:
            return "1ère" if n == 1 else f"{n}e"

        if is_hq:
            return "PELOTON DE COMMANDEMENT" if is_artillery else "QG"
        else:
            if is_artillery:
                return f"{_fr_ord(count)} BATTERIE"
            elif primary == "RECON":
                return f"{_fr_ord(count)} PELOTON RECON"
            elif primary == "TANK":
                return f"{_fr_ord(count)} PELOTON DE CHARS"
            elif primary == "ENGINEER":
                return f"{_fr_ord(count)} SECTION DU GENIE"
            elif primary == "AA":
                return f"{_fr_ord(count)} SECTION SOL-AIR"
            elif primary == "LOGISTICS":
                return "GROUPE LOGISTIQUE" if count == 1 else f"GROUPE LOGISTIQUE {count}"
            elif primary == "RIFLE":
                return f"{_fr_ord(count)} SECTION D'INFANTERIE"
            elif primary == "SUPPORT":
                return "GROUPE D'APPUI" if count == 1 else f"GROUPE D'APPUI {count}"
            elif primary == "HELI":
                return f"{_fr_ord(count)} ESCADRILLE D'HELICOPTERES"
            else:
                return f"{_fr_ord(count)} SECTION"

    elif is_russian:
        if is_hq:
            return "SHTAB"
        else:
            if is_artillery:
                return f"{count}-YA BATAREYA"
            elif primary == "RECON":
                return f"{count}-Y VZVOD RAZVEDKI"
            elif primary == "TANK":
                return f"{count}-Y TANKOVYY VZVOD"
            elif primary == "ENGINEER":
                return f"{count}-Y SAPERNYY VZVOD"
            elif primary == "AA":
                return f"{count}-Y ZENITNYY VZVOD"
            elif primary == "LOGISTICS":
                return "VZVOD OBESPECHENIYA" if count == 1 else f"VZVOD OBESPECHENIYA {count}"
            elif primary == "RIFLE":
                return f"{count}-Y MOTOSTRELKOVYY VZVOD"
            elif primary == "SUPPORT":
                return "GRUPPA PODDERZHKI" if count == 1 else f"GRUPPA PODDERZHKI {count}"
            elif primary == "HELI":
                return f"{count}-Y VZVOD VERTOLETOV"
            else:
                return f"{count}-Y VZVOD"

    else:
        # Default English
        def _ordinal(n: int) -> str:
            if 11 <= (n % 100) <= 13:
                return f"{n}TH"
            return f"{n}" + {1: 'ST', 2: 'ND', 3: 'RD'}.get(n % 10, 'TH')

        is_cavalry = any(x in cg_lower or x in deck_lower for x in ["acr", "cav", "cavalry"])

        if is_hq:
            if is_cavalry:
                return "TROOP HQ"
            elif is_artillery:
                return "BATTERY HQ"
            else:
                return "COMPANY HQ"
        else:
            if is_cavalry:
                if primary == "ENGINEER":
                    return f"{count}/58ENG"
                elif primary == "AA":
                    return "AIR DEFENSE PLATO"
                elif primary == "LOGISTICS":
                    return "LOGISTICS GROUP" if count == 1 else f"LOGISTICS GROUP {count}"
                elif primary == "RECON":
                    return "RECON GROUP" if count == 1 else f"RECON GROUP {count}"
                elif primary == "SUPPORT":
                    return "SUPPORT GROUP" if count == 1 else f"SUPPORT GROUP {count}"
                elif primary == "TANK":
                    return f"{_ordinal(count)} TANK PLATOON"
                elif primary == "RIFLE":
                    return f"{_ordinal(count)} RIFLE PLATOON"
                elif primary == "HELI":
                    return f"{_ordinal(count)} HELI PLATOON"
                else:
                    return f"{_ordinal(count)} PLATOON"
            else:
                if primary == "RECON":
                    return f"{_ordinal(count)} RECON PLATOON"
                elif primary == "TANK":
                    return f"{_ordinal(count)} TANK PLATOON"
                elif primary == "ENGINEER":
                    return f"{_ordinal(count)} ENGINEER PLATOON"
                elif primary == "AA":
                    return f"{_ordinal(count)} AIR DEFENSE PLATOON"
                elif primary == "LOGISTICS":
                    return f"{_ordinal(count)} SUPPLY PLATOON"
                elif primary == "RIFLE":
                    return f"{_ordinal(count)} RIFLE PLATOON"
                elif primary == "SUPPORT":
                    return "SUPPORT GROUP" if count == 1 else f"SUPPORT GROUP {count}"
                elif primary == "HELI":
                    return f"{_ordinal(count)} HELI PLATOON"
                else:
                    return f"{_ordinal(count)} PLATOON"


# Legacy /api/assign, /api/decks, /api/deck/<name> endpoints are gone.
# Old UI clients will see 404 from Flask, which is the intended cue to refresh.
