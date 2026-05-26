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
    by_deck: dict[str, list[Assignment]] = {}
    for a in assignments:
        by_deck.setdefault(a.deck_name, []).append(a)
    for lst in by_deck.values():
        lst.sort(key=lambda a: (a.order, a.seq))

    existing: set[str] = set()
    rows: list[str] = ['"TOKEN";"REFTEXT"']

    for deck_name, deck_assignments in by_deck.items():
        groups_map: dict[str, list[Assignment]] = {}
        group_order: list[str] = []
        for a in deck_assignments:
            gname = a.group_name or "A"
            if gname not in groups_map:
                groups_map[gname] = []
                group_order.append(gname)
            groups_map[gname].append(a)

        for gname in group_order:
            group_assignments = groups_map[gname]

            group_token = make_unique_token(
                f"cg_WIF_{gname}",
                deck_name,
                existing,
            )
            existing.add(group_token)
            rows.append(f'"{group_token}";"WIF {gname}"')

            # Group assignments by sub_group
            grouped: dict[str, list[Assignment]] = {}
            ungrouped: list[Assignment] = []
            for a in group_assignments:
                if a.sub_group:
                    grouped.setdefault(a.sub_group, []).append(a)
                else:
                    ungrouped.append(a)

            # Build smart group items for sorting
            smart_group_items = []
            for sg_name, sg_assignments in grouped.items():
                smart_group_items.append((sg_name, sg_assignments))
            for a in ungrouped:
                smart_group_items.append((None, [a]))

            # Tactical sort: HQ first, then numeric, then SPT, then ungrouped
            def smart_group_sort_key(item):
                sg_name, sg_assignments = item
                if sg_name is None:
                    return (4, sg_assignments[0].order)
                if sg_name == "HQ":
                    return (0, "")
                elif sg_name.isdigit():
                    return (1, int(sg_name))
                elif sg_name == "SPT" or sg_name == "SUPPORT":
                    return (3, "")
                else:
                    return (2, sg_name)

            smart_group_items.sort(key=smart_group_sort_key)

            for sg_name, sg_assignments in smart_group_items:
                if sg_name:
                    token_key = f"sg_WIF_{gname}_{sg_name}"
                else:
                    a = sg_assignments[0]
                    xp = a.xp_levels[0] if a.xp_levels else 1
                    token_key = smart_token_key(a.unit_id, xp, a.seq)

                smart_token = make_unique_token(token_key, deck_name, existing)
                existing.add(smart_token)

                # Determine display name
                if sg_name:
                    if sg_name == "HQ":
                        display_name = f"WIF — {gname} HQ"
                    elif sg_name == "SPT":
                        display_name = f"WIF — {gname} SUPPORT"
                    elif sg_name.isdigit():
                        display_name = f"WIF — {gname} PLATOON {sg_name}"
                    else:
                        # Custom or vanilla platoon name
                        display_name = sg_name
                else:
                    a = sg_assignments[0]
                    unit = units.get(a.unit_id)
                    display_base = _display_name(unit, a.unit_id)
                    seq_label = f" ({a.seq + 1})" if a.seq else ""
                    xp = a.xp_levels[0] if a.xp_levels else 1
                    display_name = f"WIF {display_base}{seq_label} XP{xp}"

                rows.append(f'"{smart_token}";"{display_name}"')

    return "\n".join(rows) + "\n"


def _display_name(unit: WifUnit | None, unit_id: str) -> str:
    """Cleanest readable name we have for a unit."""
    if unit and unit.name_token:
        # name_token is a UNITS.csv key, not human-readable on its own — fall back to id
        return unit_id.removeprefix("WF_").replace("_", " ")
    return unit_id.removeprefix("WF_").replace("_", " ")
