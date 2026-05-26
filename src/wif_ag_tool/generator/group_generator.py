"""Emit TDeckCombatGroupDescriptor NDF blocks."""
from __future__ import annotations

from wif_ag_tool.models import Assignment, DeckState
from wif_ag_tool.generator.token_gen import (
    make_unique_token,
    group_token_key,
    smart_token_key,
)


def generate_combat_group(
    assignment: Assignment,
    deck_state: DeckState,
    existing_tokens: set[str],
) -> str:
    """Emit one TDeckCombatGroupDescriptor for *assignment*.

    The SmartGroup at position i references pack index (deck.next_index + i).
    Tokens are added to *existing_tokens* in-place so callers can keep accumulating.
    """
    return generate_grouped_combat_group(
        gname=assignment.group_name,
        deck_name=assignment.deck_name,
        assignments=[assignment],
        deck_state=deck_state,
        existing_tokens=existing_tokens,
    )


def generate_grouped_combat_group(
    gname: str,
    deck_name: str,
    assignments: list[Assignment],
    deck_state: DeckState,
    existing_tokens: set[str],
) -> str:
    """Emit one TDeckCombatGroupDescriptor containing smart groups for *assignments*.

    Smart groups are grouped by their sub_group property and sorted tactically.
    Pack indices are correctly mapped from linear deck additions.
    """
    deck_short = deck_name.replace("Descriptor_Deck_pion_", "")
    group_name = f"Descriptor_CombatGroup_{deck_short}_WIF_{gname}"

    group_token = make_unique_token(
        f"cg_WIF_{gname}",
        deck_name,
        existing_tokens,
    )
    existing_tokens.add(group_token)

    lines = [
        f"{group_name} is TDeckCombatGroupDescriptor",
        "(",
        f'    Name = "{group_token}"',
        "    SmartGroupList =",
        "    [",
    ]

    # Map each assignment's id to its starting pack index as linear deck additions
    assignment_indices = {}
    curr = deck_state.next_index
    for a in assignments:
        assignment_indices[id(a)] = curr
        curr += len(a.xp_levels)

    # Group assignments by sub_group
    grouped: dict[str, list[Assignment]] = {}
    ungrouped: list[Assignment] = []
    for a in assignments:
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
        # Determine token key
        if sg_name:
            token_key = f"sg_WIF_{gname}_{sg_name}"
        else:
            a = sg_assignments[0]
            xp = a.xp_levels[0] if a.xp_levels else 1
            token_key = smart_token_key(a.unit_id, xp, a.seq)

        smart_token = make_unique_token(token_key, deck_name, existing_tokens)
        existing_tokens.add(smart_token)

        # Smart group descriptor block
        lines.extend([
            "        TDeckSmartGroupDescriptor",
            "        (",
            f'            Name = "{smart_token}"',
        ])
        if sg_name == "HQ":
            lines.append("            IsHQ = True")
        lines.extend([
            "            PackIndexUnitNumberList =",
            "            [",
        ])
        for a in sg_assignments:
            start_idx = assignment_indices[id(a)]
            for offset, xp in enumerate(a.xp_levels):
                lines.append(f"                ({start_idx + offset},{a.count}),")
        lines.extend([
            "            ]",
            "        ),",
        ])

    lines.extend(["    ]", ")"])
    return "\n".join(lines)
