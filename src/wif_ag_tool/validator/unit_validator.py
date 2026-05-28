"""Validate that a unit_id exists in one of the parsed unit catalogues."""
from __future__ import annotations

from wif_ag_tool.models import WifUnit


class UnitNotFoundError(Exception):
    pass


def validate_unit_exists(unit_id: str, *catalogues: dict[str, WifUnit]) -> None:
    """Raise if `unit_id` is missing from every catalogue passed in.

    Pass the WIF catalogue alone to keep the historical behavior, or pass both
    WIF + vanilla to accept either source.
    """
    if not catalogues:
        raise UnitNotFoundError(f"no catalogue provided to validate against: {unit_id}")
    for cat in catalogues:
        if unit_id in cat:
            return
    raise UnitNotFoundError(f"unit not found in any catalogue: {unit_id}")
