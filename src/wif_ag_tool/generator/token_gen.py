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
