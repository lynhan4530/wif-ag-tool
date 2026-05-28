"""Emit TDeckCombatGroupDescriptor NDF blocks."""
from __future__ import annotations
from typing import Any

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
    vanilla_token: str | None = None,
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
        vanilla_token=vanilla_token,
    )


def resolve_cg_name(deck_name: str, gname: str, vanilla_cg_list: list[str]) -> str:
    """Find a matching combat group in the deck's vanilla combat group list, or fall back to WIF name."""
    target = f"_{gname}_"
    for cg in vanilla_cg_list:
        if target in cg:
            return cg
    target_suffix = f"_{gname}"
    for cg in vanilla_cg_list:
        if cg.endswith(target_suffix):
            return cg
    deck_short = deck_name.replace("Descriptor_Deck_pion_", "")
    return f"Descriptor_CombatGroup_{deck_short}_WIF_{gname}"


def align_and_order_smart_groups(
    smart_group_items: list[tuple[str | None, list[Assignment]]],
    vanilla_smart_groups: list[Any] | None,
    deck_name: str,
    gname: str,
    existing_tokens: set[str],
) -> list[tuple[str, bool, list[Assignment]]]:
    """Align generated smart groups to vanilla smart groups, maintaining vanilla order and tokens."""
    if not vanilla_smart_groups:
        # No vanilla reference: just output generated smart groups in their sorted order
        out = []
        for sg_name, sg_assignments in smart_group_items:
            is_sg_hq = bool(sg_name and "HQ" in sg_name.upper())
            if sg_name:
                token_key = f"sg_WIF_{gname}_{sg_name}"
            else:
                a = sg_assignments[0]
                xp = a.xp_levels[0] if a.xp_levels else 1
                token_key = smart_token_key(a.unit_id, xp, a.seq)
            smart_token = make_unique_token(token_key, deck_name, existing_tokens)
            existing_tokens.add(smart_token)
            out.append((smart_token, is_sg_hq, sg_assignments))
        return out

    # We have vanilla smart groups: align by role and index
    vanilla_hq = [sg for sg in vanilla_smart_groups if sg.is_hq]
    vanilla_non_hq = [sg for sg in vanilla_smart_groups if not sg.is_hq]

    # Separate generated smart groups
    gen_hq = []
    gen_non_hq = []
    for sg_name, sg_assignments in smart_group_items:
        is_sg_hq = bool(sg_name and "HQ" in sg_name.upper())
        if is_sg_hq:
            gen_hq.append(sg_assignments)
        else:
            gen_non_hq.append(sg_assignments)

    # Build bidirectional mapping between vanilla SmartGroup and generated assignments
    vanilla_to_gen = {}
    gen_matched = set()

    # Map HQ
    for idx, g_asn in enumerate(gen_hq):
        if idx < len(vanilla_hq):
            v_sg = vanilla_hq[idx]
            vanilla_to_gen[id(v_sg)] = g_asn
            gen_matched.add(id(g_asn))

    # Map non-HQ
    for idx, g_asn in enumerate(gen_non_hq):
        if idx < len(vanilla_non_hq):
            v_sg = vanilla_non_hq[idx]
            vanilla_to_gen[id(v_sg)] = g_asn
            gen_matched.add(id(g_asn))

    # Construct the ordered output list matching vanilla order
    ordered_out = []
    for v_sg in vanilla_smart_groups:
        g_asn = vanilla_to_gen.get(id(v_sg))
        if g_asn is not None:
            # Reusing vanilla token
            existing_tokens.add(v_sg.name)
            ordered_out.append((v_sg.name, v_sg.is_hq, g_asn))
        else:
            # Unmatched vanilla slot: output an empty placeholder to preserve index
            existing_tokens.add(v_sg.name)
            ordered_out.append((v_sg.name, v_sg.is_hq, []))

    # Append any extra generated HQ groups that didn't fit
    for idx, g_asn in enumerate(gen_hq):
        if id(g_asn) not in gen_matched:
            # Generate a new unique token
            token_key = f"sg_WIF_{gname}_HQ_extra_{idx}"
            smart_token = make_unique_token(token_key, deck_name, existing_tokens)
            existing_tokens.add(smart_token)
            ordered_out.append((smart_token, True, g_asn))

    # Append any extra generated non-HQ groups that didn't fit
    for idx, g_asn in enumerate(gen_non_hq):
        if id(g_asn) not in gen_matched:
            token_key = f"sg_WIF_{gname}_extra_{idx}"
            smart_token = make_unique_token(token_key, deck_name, existing_tokens)
            existing_tokens.add(smart_token)
            ordered_out.append((smart_token, False, g_asn))

    return ordered_out


def generate_grouped_combat_group(
    gname: str,
    deck_name: str,
    assignments: list[Assignment],
    deck_state: DeckState,
    existing_tokens: set[str],
    vanilla_token: str | None = None,
    is_hq: bool = False,
    vanilla_smart_groups: list[Any] | None = None,
) -> str:
    """Emit one TDeckCombatGroupDescriptor containing smart groups for *assignments*.

    Smart groups are grouped by their sub_group property and sorted tactically.
    Pack indices are correctly mapped from linear deck additions.
    """
    deck_short = deck_name.replace("Descriptor_Deck_pion_", "")
    group_name = resolve_cg_name(deck_name, gname, deck_state.combat_group_list)

    if vanilla_token:
        group_token = vanilla_token
    else:
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
    ]
    if is_hq:
        lines.append("    IsHQ = True")
    lines.extend([
        "    SmartGroupList =",
        "    [",
    ])

    # Map each assignment's id to its starting pack index as linear deck additions.
    # Each (xp_level, count) consumes `count` consecutive DeckPackList slots, so the
    # next assignment starts at curr + len(xp_levels) * count.
    assignment_indices = {}
    curr = deck_state.next_index
    for a in assignments:
        assignment_indices[id(a)] = curr
        curr += len(a.xp_levels) * a.count

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

    # Align and order generated smart groups to vanilla smart groups if available
    aligned_groups = align_and_order_smart_groups(
        smart_group_items=smart_group_items,
        vanilla_smart_groups=vanilla_smart_groups,
        deck_name=deck_name,
        gname=gname,
        existing_tokens=existing_tokens,
    )

    for smart_token, sg_is_hq, sg_assignments in aligned_groups:
        # Smart group descriptor block
        lines.extend([
            "        TDeckSmartGroupDescriptor",
            "        (",
            f'            Name = "{smart_token}"',
        ])
        if sg_is_hq:
            lines.append("            IsHQ = True")
        lines.extend([
            "            PackIndexUnitNumberList =",
            "            [",
        ])
        for a in sg_assignments:
            start_idx = assignment_indices[id(a)]
            for offset, xp in enumerate(a.xp_levels):
                lines.append(f"                ({start_idx + offset * a.count},{a.count}),")
        lines.extend([
            "            ]",
            "        ),",
        ])

    lines.extend(["    ]", ")"])
    return "\n".join(lines)
