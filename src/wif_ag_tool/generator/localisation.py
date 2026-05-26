"""Emit PLATOONS.csv rows for combat-group and smart-group tokens."""
from __future__ import annotations

from wif_ag_tool.models import Assignment, WifUnit
from wif_ag_tool.generator.token_gen import (
    make_unique_token,
    group_token_key,
    smart_token_key,
)


def generate_platoons_rows(
    assignments: list[Assignment],
    units: dict[str, WifUnit],
) -> str:
    """Return PLATOONS.csv content: semicolon-separated, double-quoted, no BOM.

    One row per CombatGroup Name plus one per SmartGroup Name. Token generation
    mirrors group_generator so the same Assignment produces the same tokens.
    """
    existing: set[str] = set()
    rows: list[str] = ['"TOKEN";"REFTEXT"']
    for a in assignments:
        unit = units.get(a.unit_id)
        display_base = _display_name(unit, a.unit_id)
        seq_label = f" ({a.seq + 1})" if a.seq else ""

        group_token = make_unique_token(
            group_token_key(a.unit_id, a.seq),
            a.deck_name,
            existing,
        )
        existing.add(group_token)
        rows.append(f'"{group_token}";"WIF {display_base}{seq_label}"')

        for xp in a.xp_levels:
            smart_token = make_unique_token(
                smart_token_key(a.unit_id, xp, a.seq),
                a.deck_name,
                existing,
            )
            existing.add(smart_token)
            rows.append(f'"{smart_token}";"WIF {display_base}{seq_label} XP{xp}"')

    return "\n".join(rows) + "\n"


def _display_name(unit: WifUnit | None, unit_id: str) -> str:
    """Cleanest readable name we have for a unit."""
    if unit and unit.name_token:
        # name_token is a UNITS.csv key, not human-readable on its own — fall back to id
        return unit_id.removeprefix("WF_").replace("_", " ")
    return unit_id.removeprefix("WF_").replace("_", " ")
