"""Validate 10-char uppercase tokens and uniqueness."""
from __future__ import annotations


class TokenLengthError(Exception):
    pass


class TokenCollisionError(Exception):
    pass


def validate_token(token: str) -> None:
    if len(token) != 10:
        raise TokenLengthError(f"token must be exactly 10 chars, got {len(token)}: {token!r}")


def validate_token_unique(token: str, existing: set[str]) -> None:
    if token in existing:
        raise TokenCollisionError(f"token already used: {token}")
