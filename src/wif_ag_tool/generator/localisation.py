"""Emit PLATOONS.csv rows for combat-group and smart-group tokens.

Full-replacement model: every combat group / smart group in a replica'd deck is a
WIF-generated group, so all tokens here are WIF tokens. (No vanilla token reuse — the
old merge path was removed.)
"""
from __future__ import annotations

from wif_ag_tool.models import Assignment, WifUnit
from wif_ag_tool.generator.token_gen import make_unique_token
from wif_ag_tool.generator.group_generator import (
    sorted_smart_group_items,
    order_smart_groups,
)


def generate_platoons_rows(
    assignments: list[Assignment],
    units: dict[str, WifUnit],
    decks: dict | None = None,
    combat_groups: dict | None = None,
) -> str:
    """Return PLATOONS.csv content: semicolon-separated, double-quoted, no BOM.

    One row per SmartGroup Name, plus one per CombatGroup Name *only when the group does
    not reuse a vanilla combat group* (vanilla combat-group tokens already have loc rows in
    the mod's PLATOONS.csv, so re-emitting them would duplicate/clobber the vanilla name).
    Token generation mirrors ``build_export_blocks``/``group_generator`` so the same
    Assignment produces the same tokens.
    """
    by_deck: dict[str, list[Assignment]] = {}
    for a in assignments:
        by_deck.setdefault(a.deck_name, []).append(a)
    for lst in by_deck.values():
        lst.sort(key=lambda a: (a.order, a.seq))

    existing: set[str] = set()
    written_tokens: set[str] = set()
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

            # Mirror build_export_blocks: reuse the vanilla combat-group token when the
            # group maps to one. Add it to `existing` either way so the smart-group token
            # sequence stays identical to the generated combat-group blocks.
            vanilla_token = None
            if decks is not None and combat_groups and deck_name in decks:
                from wif_ag_tool.generator.group_generator import resolve_cg_name
                cg_name = resolve_cg_name(deck_name, gname, decks[deck_name].combat_group_list)
                v = combat_groups.get(cg_name)
                vanilla_token = v.token if v else None

            group_token = vanilla_token or make_unique_token(f"cg_WIF_{gname}", deck_name, existing)
            existing.add(group_token)
            # Only emit a row for WIF-named groups; vanilla combat-group tokens keep their
            # existing loc row in the mod's PLATOONS.csv.
            if vanilla_token is None and group_token not in written_tokens:
                written_tokens.add(group_token)
                rows.append(f'"{group_token}";"WIF {gname}"')

            smart_group_items = sorted_smart_group_items(group_assignments)
            aligned_groups = order_smart_groups(smart_group_items, deck_name, gname, existing)

            for smart_token, sg_is_hq, sg_assignments in aligned_groups:
                if not sg_assignments:
                    continue

                sg_name = sg_assignments[0].sub_group

                if sg_name:
                    if sg_name == "HQ":
                        display_name = f"WIF — {gname} HQ"
                    elif sg_name == "SPT":
                        display_name = f"WIF — {gname} SUPPORT"
                    elif sg_name.isdigit():
                        display_name = f"WIF — {gname} PLATOON {sg_name}"
                    else:
                        # Custom platoon name
                        display_name = sg_name
                else:
                    a = sg_assignments[0]
                    unit = units.get(a.unit_id)
                    display_base = _display_name(unit, a.unit_id)
                    seq_label = f" ({a.seq + 1})" if a.seq else ""
                    xp = a.xp_levels[0] if a.xp_levels else 1
                    display_name = f"WIF {display_base}{seq_label} XP{xp}"

                if smart_token not in written_tokens:
                    written_tokens.add(smart_token)
                    rows.append(f'"{smart_token}";"{display_name}"')

    return "\n".join(rows) + "\n"


def _display_name(unit: WifUnit | None, unit_id: str) -> str:
    """Cleanest readable name we have for a unit."""
    return unit_id.removeprefix("WF_").replace("_", " ")
