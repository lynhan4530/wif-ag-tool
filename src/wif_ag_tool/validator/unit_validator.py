"""Validate that a unit_id exists in the parsed WIF unit catalogue."""
from __future__ import annotations

from wif_ag_tool.models import WifUnit


class UnitNotFoundError(Exception):
    pass


def validate_unit_exists(unit_id: str, units: dict[str, WifUnit]) -> None:
    if unit_id not in units:
        raise UnitNotFoundError(f"unit not found in WIF catalogue: {unit_id}")
