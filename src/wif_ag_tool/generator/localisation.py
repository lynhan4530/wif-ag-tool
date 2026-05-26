"""Emit PLATOONS.csv rows for combat-group and smart-group tokens."""
from __future__ import annotations

from wif_ag_tool.models import Assignment, WifUnit
from wif_ag_tool.generator.token_gen import make_unique_token


def generate_platoons_rows(
    assignments: list[Assignment],
    units: dict[str, WifUnit],
) -> str:
    """Return PLATOONS.csv content: semicolon-separated, double-quoted, no BOM.

    One row per CombatGroup Name plus one per SmartGroup Name.
    """
    existing: set[str] = set()
    rows: list[str] = ['"TOKEN";"REFTEXT"']
    for a in assignments:
        unit = units.get(a.unit_id)
        display_base = _display_name(unit, a.unit_id)

        group_token = make_unique_token(a.unit_id, a.deck_name, existing)
        existing.add(group_token)
        rows.append(f'"{group_token}";"WIF {display_base}"')

        for xp in a.xp_levels:
            smart_token = make_unique_token(f"{a.unit_id}_xp{xp}", a.deck_name, existing)
            existing.add(smart_token)
            rows.append(f'"{smart_token}";"WIF {display_base} XP{xp}"')

    return "\n".join(rows) + "\n"


def _display_name(unit: WifUnit | None, unit_id: str) -> str:
    """Cleanest readable name we have for a unit."""
    if unit and unit.name_token:
        # name_token is a UNITS.csv key, not human-readable on its own — fall back to id
        return unit_id.removeprefix("WF_").replace("_", " ")
    return unit_id.removeprefix("WF_").replace("_", " ")
