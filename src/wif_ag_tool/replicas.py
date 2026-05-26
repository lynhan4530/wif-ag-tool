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
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(p)


def save_replica(
    deck_name: str,
    units: list[dict],
    path: Path | None = None,
) -> dict:
    """Replace the replica for *deck_name* with *units* (ordered list).

    Raises ValueError when *units* is empty — empty saves are blocked by design;
    use ``delete_replica`` to clear instead.
    """
    if not units:
        raise ValueError("cannot save replica with empty units list — use delete_replica")
    store = load_replicas(path)
    store[deck_name] = {
        "saved": True,
        "updated_at": _now(),
        "units": [_normalize_row(u) for u in units],
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


def _normalize_row(row: dict) -> dict:
    """Coerce a row dict into canonical shape (defensive against API input)."""
    xp = int(row.get("xp", 1))
    if xp not in (0, 1, 2, 3):
        raise ValueError(f"xp must be in 0/1/2/3, got {xp}")
    return {
        "unit_id": str(row["unit_id"]),
        "xp": xp,
        "count": int(row.get("count", 1)),
        "attack_override": row.get("attack_override"),
        "defense_override": row.get("defense_override"),
    }


def replicas_to_assignments(
    replicas: dict[str, dict] | None = None,
    scope_decks: Iterable[str] | None = None,
) -> list[Assignment]:
    """Flatten replicas into Assignment list for the export pipeline.

    Each row → one Assignment with ``xp_levels=[xp]``. Duplicate (unit_id, xp) pairs
    in the same deck get an incrementing ``seq`` so their descriptor names disambiguate
    via the ``_1``/``_2`` suffix on combat-group + pack names.

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
        # seq counts occurrences of *unit_id* within this deck so combat-group names
        # disambiguate when the same unit appears more than once (regardless of XP).
        seen: dict[str, int] = {}
        for idx, row in enumerate(entry.get("units", [])):
            unit_id = row["unit_id"]
            xp = int(row["xp"])
            seq = seen.get(unit_id, 0)
            seen[unit_id] = seq + 1
            out.append(Assignment(
                deck_name=deck_name,
                unit_id=unit_id,
                xp_levels=[xp],
                count=int(row.get("count", 1)),
                attack_override=row.get("attack_override"),
                defense_override=row.get("defense_override"),
                order=idx,
                seq=seq,
            ))
    return out


__all__ = [
    "load_replicas",
    "save_replica",
    "delete_replica",
    "replicas_to_assignments",
]
