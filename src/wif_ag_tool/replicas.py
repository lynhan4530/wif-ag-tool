"""Global per-deck WIF replicas — the source of truth for export.

A replica = the WIF unit list a user has committed to a specific vanilla deck.
Replicas are shared across sessions (a deck has at most one replica).

On-disk layout: a single JSON at ``config.REPLICAS_FILE`` keyed by deck descriptor name.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from wif_ag_tool import config
from wif_ag_tool.models import Assignment


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_replicas(path: Path | None = None) -> dict[str, dict]:
    p = path or config.REPLICAS_FILE
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _write(payload: dict, path: Path | None = None) -> None:
    p = path or config.REPLICAS_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(p)


def save_replica(
    deck_name: str,
    payload: list[dict],
    path: Path | None = None,
) -> dict:
    """Replace the replica for *deck_name* with hierarchical groups.

    Supports both new hierarchical payloads (groups containing platoons containing units)
    and old flat payloads (list of unit rows), automatically converting the latter.
    Raises ValueError when payload is empty.
    """
    if not payload:
        raise ValueError("cannot save replica with empty units list — use delete_replica")

    # Detect if flat units payload or hierarchical groups payload
    is_hierarchical = any("platoons" in item for item in payload)

    if is_hierarchical:
        groups = [_normalize_group(g) for g in payload]
    else:
        # Convert flat list to hierarchical groups
        flat_units = [_normalize_row(u) for u in payload]
        groups_dict: dict[str, dict[str, list[dict]]] = {}
        for row in flat_units:
            gname = row.get("group_name", "A")
            pl_name = row.get("sub_group") or "none"
            groups_dict.setdefault(gname, {}).setdefault(pl_name, []).append({
                "unit_id": row["unit_id"],
                "xp": row["xp"],
                "count": row["count"],
                "attack_override": row.get("attack_override"),
                "defense_override": row.get("defense_override"),
                "transport_id": row.get("transport_id"),
            })
        groups = []
        for gname in sorted(groups_dict.keys()):
            platoons = []
            for pl_name in sorted(groups_dict[gname].keys()):
                platoons.append({
                    "name": pl_name,
                    "units": groups_dict[gname][pl_name]
                })
            groups.append({
                "name": gname,
                "platoons": platoons
            })

    store = load_replicas(path)
    store[deck_name] = {
        "saved": True,
        "updated_at": _now(),
        "groups": groups,
    }
    _write(store, path)
    return store[deck_name]


def delete_replica(deck_name: str, path: Path | None = None) -> bool:
    store = load_replicas(path)
    if deck_name not in store:
        return False
    del store[deck_name]
    _write(store, path)
    return True


def _normalize_group(group: dict) -> dict:
    return {
        "name": str(group["name"]),
        "platoons": [_normalize_platoon(p) for p in group.get("platoons", [])],
    }


def _normalize_platoon(platoon: dict) -> dict:
    return {
        "name": str(platoon["name"]),
        "units": [_normalize_unit(u) for u in platoon.get("units", [])],
    }


def _normalize_unit(unit: dict) -> dict:
    xp = int(unit.get("xp", 1))
    if xp not in (0, 1, 2, 3):
        raise ValueError(f"xp must be in 0/1/2/3, got {xp}")
    return {
        "unit_id": str(unit["unit_id"]),
        "xp": xp,
        "count": int(unit.get("count", 1)),
        "attack_override": unit.get("attack_override"),
        "defense_override": unit.get("defense_override"),
        "transport_id": unit.get("transport_id"),
    }


def _normalize_row(row: dict) -> dict:
    """Coerce a flat row dict into canonical shape (for backward compatibility)."""
    xp = int(row.get("xp", 1))
    if xp not in (0, 1, 2, 3):
        raise ValueError(f"xp must be in 0/1/2/3, got {xp}")
    return {
        "unit_id": str(row["unit_id"]),
        "xp": xp,
        "count": int(row.get("count", 1)),
        "attack_override": row.get("attack_override"),
        "defense_override": row.get("defense_override"),
        "group_name": str(row.get("group_name", "A")),
        "transport_id": row.get("transport_id"),
        "sub_group": row.get("sub_group"),
    }


def migrate_flat_to_hierarchical(entry: dict) -> dict:
    """If the deck entry has legacy flat 'units', convert it on-the-fly to nested 'groups'."""
    if "units" in entry and "groups" not in entry:
        groups_dict: dict[str, dict[str, list[dict]]] = {}
        for row in entry["units"]:
            gname = row.get("group_name", "A")
            pl_name = row.get("sub_group") or "none"
            groups_dict.setdefault(gname, {}).setdefault(pl_name, []).append({
                "unit_id": row["unit_id"],
                "xp": row.get("xp", 1),
                "count": row.get("count", 1),
                "attack_override": row.get("attack_override"),
                "defense_override": row.get("defense_override"),
                "transport_id": row.get("transport_id"),
            })
        groups = []
        for gname in sorted(groups_dict.keys()):
            platoons = []
            for pl_name in sorted(groups_dict[gname].keys()):
                platoons.append({
                    "name": pl_name,
                    "units": groups_dict[gname][pl_name]
                })
            groups.append({
                "name": gname,
                "platoons": platoons
            })
        entry["groups"] = groups
        del entry["units"]
    return entry


def replicas_to_assignments(
    replicas: dict[str, dict] | None = None,
    scope_decks: Iterable[str] | None = None,
) -> list[Assignment]:
    """Flatten replicas into Assignment list for the export pipeline.

    *scope_decks* — if provided, only replicas for these decks are included.
    """
    src = load_replicas() if replicas is None else replicas
    scope = set(scope_decks) if scope_decks is not None else None

    out: list[Assignment] = []
    for deck_name, entry in src.items():
        if not entry.get("saved"):
            continue
        if scope is not None and deck_name not in scope:
            continue

        # Ensure migrated to hierarchical
        entry = migrate_flat_to_hierarchical(entry)

        idx = 0
        seen: dict[str, int] = {}
        for g_data in entry.get("groups", []):
            gname = g_data["name"]
            for pl_data in g_data.get("platoons", []):
                pl_name = pl_data["name"]
                for u_data in pl_data.get("units", []):
                    unit_id = u_data["unit_id"]
                    xp = int(u_data.get("xp", 1))
                    seq = seen.get(unit_id, 0)
                    seen[unit_id] = seq + 1
                    out.append(Assignment(
                        deck_name=deck_name,
                        unit_id=unit_id,
                        xp_levels=[xp],
                        count=int(u_data.get("count", 1)),
                        attack_override=u_data.get("attack_override"),
                        defense_override=u_data.get("defense_override"),
                        order=idx,
                        seq=seq,
                        group_name=gname,
                        transport_id=u_data.get("transport_id"),
                        sub_group=None if pl_name == "none" else pl_name,
                    ))
                    idx += 1
    return out


__all__ = [
    "load_replicas",
    "save_replica",
    "delete_replica",
    "replicas_to_assignments",
]
