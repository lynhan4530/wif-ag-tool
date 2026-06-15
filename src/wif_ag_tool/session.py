"""Session module: per-campaign workspace state.

A session owns campaign metadata + the user's curated nation scope. It does NOT own
unit data — that lives in `replicas.py` (global per-deck WIF replicas).

On-disk layout: one JSON file per campaign at ``SESSIONS_DIR/<slug>.json``.
"""
from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from wif_ag_tool import config


# ── slug ─────────────────────────────────────────────────────────────────────

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """Lower-kebab-case ASCII slug. Empty input → "session"."""
    s = _SLUG_STRIP.sub("-", name.lower()).strip("-")
    return s or "session"


# ── compound faction tokens ──────────────────────────────────────────────────

# Save filenames use abbreviations that don't always match vanilla deck-name prefixes.
# Aliases translate save-side codes to the deck-side prefix used in StrategicDecks.ndf.
NATION_ALIASES: dict[str, str] = {
    "DDR": "RDA",   # East Germany: filename uses German abbr, NDF uses French abbr
}


def normalize_nation(code: str) -> str:
    """Translate a save-filename faction code to its vanilla deck-prefix code."""
    return NATION_ALIASES.get(code.upper(), code.upper())


def split_factions(tokens: Iterable[str]) -> list[str]:
    """Split compound faction codes like ``UK_RFA`` → ``["UK","RFA"]``.

    Order is preserved; duplicates removed. Empty strings dropped. Codes are
    normalized via :data:`NATION_ALIASES` so DDR → RDA, etc.
    """
    out: list[str] = []
    seen: set[str] = set()
    for tok in tokens:
        for part in (p.strip() for p in tok.split("_") if p.strip()):
            n = normalize_nation(part)
            if n not in seen:
                seen.add(n)
                out.append(n)
    return out


# ── IO ───────────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path_for(slug: str, sessions_dir: Path | None = None) -> Path:
    return (sessions_dir or config.SESSIONS_DIR) / f"{slug}.json"


def list_sessions(sessions_dir: Path | None = None) -> list[dict]:
    """Return all sessions sorted by updated_at desc (newest first)."""
    d = sessions_dir or config.SESSIONS_DIR
    if not d.exists():
        return []
    out: list[dict] = []
    for p in d.glob("*.json"):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    out.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
    return out


def load_session(slug: str, sessions_dir: Path | None = None) -> dict | None:
    p = _path_for(slug, sessions_dir)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def save_session(session: dict, sessions_dir: Path | None = None) -> dict:
    """Persist *session* atomically; bumps updated_at; returns the saved payload."""
    d = sessions_dir or config.SESSIONS_DIR
    d.mkdir(parents=True, exist_ok=True)
    session = {**session, "updated_at": _now()}
    p = _path_for(session["slug"], d)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(session, indent=2), encoding="utf-8")
    tmp.replace(p)
    return session


def delete_session(slug: str, sessions_dir: Path | None = None) -> bool:
    p = _path_for(slug, sessions_dir)
    if p.exists():
        p.unlink()
        return True
    return False


def create_session(
    campaign: str,
    factions: Iterable[str] = (),
    missions: Iterable[str] = (),
    sessions_dir: Path | None = None,
    slug: str | None = None,
) -> dict:
    """Initialise a new session. Seeds nation_scope from split factions."""
    chosen_slug = slug or slugify(campaign)
    if load_session(chosen_slug, sessions_dir) is not None:
        # Disambiguate
        n = 2
        while load_session(f"{chosen_slug}-{n}", sessions_dir) is not None:
            n += 1
        chosen_slug = f"{chosen_slug}-{n}"

    factions_seed = list(factions)
    nation_scope = split_factions(factions_seed)

    payload = {
        "slug": chosen_slug,
        "campaign": campaign,
        "factions_from_save": factions_seed,
        "missions_seen": list(missions),
        "nation_scope": nation_scope,
        "target_mod_dir": "",
        "game_dir": "",
        "export_dir": "",
        "source_mod_dir": "",
        "mod_unit_prefix": "WF_",
        "mod_tag": "WIF",
        "mod_loc_folder": "A World in Flames",
        "created_at": _now(),
        "updated_at": _now(),
    }
    return save_session(payload, sessions_dir)


# ── scope resolution ─────────────────────────────────────────────────────────

def scope_decks(nation_scope: Iterable[str], all_deck_names: Iterable[str]) -> list[str]:
    """Return the deck names whose ``pion_<NATION>_`` prefix is in *nation_scope*.

    Deck name convention from NDF: ``Descriptor_Deck_pion_<NATION>_<rest>``.
    """
    scope = {n.upper() for n in nation_scope}
    out: list[str] = []
    for name in all_deck_names:
        parts = name.split("_")
        # Descriptor / Deck / pion / NATION / ...
        if len(parts) < 4:
            continue
        if parts[3].upper() in scope:
            out.append(name)
    return out


__all__ = [
    "slugify",
    "split_factions",
    "list_sessions",
    "load_session",
    "save_session",
    "delete_session",
    "create_session",
    "scope_decks",
]
