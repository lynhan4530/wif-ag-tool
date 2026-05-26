"""Deterministic 10-char uppercase tokens for NDF Name fields."""
from __future__ import annotations
import hashlib


def make_token(unit_id: str, deck_name: str, suffix: str = "") -> str:
    """Return MD5 prefix of f'{unit_id}:{deck_name}{suffix}' — 10 hex chars, uppercase."""
    key = f"{unit_id}:{deck_name}{suffix}"
    return hashlib.md5(key.encode()).hexdigest()[:10].upper()


def make_unique_token(unit_id: str, deck_name: str, existing: set[str]) -> str:
    """Like make_token but guaranteed unique against *existing*. Mutates nothing."""
    suffix = ""
    counter = 0
    while True:
        token = make_token(unit_id, deck_name, suffix)
        if token not in existing:
            return token
        counter += 1
        suffix = str(counter)


# ── assignment-aware key helpers ─────────────────────────────────────────────
# Used by group_generator and localisation so they produce identical tokens for
# the same Assignment row (since both iterate assignments in the same order and
# feed the same string key into make_unique_token).

def group_token_key(unit_id: str, seq: int = 0) -> str:
    """Key for the combat-group Name token. seq>0 disambiguates duplicate units."""
    return f"{unit_id}#{seq}" if seq else unit_id


def smart_token_key(unit_id: str, xp: int, seq: int = 0) -> str:
    """Key for a smart-group Name token under a given combat group + XP."""
    base = group_token_key(unit_id, seq)
    return f"{base}_xp{xp}"
