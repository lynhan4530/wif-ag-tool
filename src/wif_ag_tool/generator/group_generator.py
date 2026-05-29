"""Emit TDeckCombatGroupDescriptor NDF blocks.

Full-replacement model: a deck's replica defines the deck outright, so combat groups
are generated purely from the replica's groups/platoons/units. There is no merging with
vanilla combat groups — the export rewrites the deck's lists wholesale, and decks without
a replica are left untouched. (The old vanilla-alignment/merge path was removed once we
verified in-game that AG accepts a fully-replaced deck.)
"""
from __future__ import annotations

from wif_ag_tool.models import Assignment, DeckState
from wif_ag_tool.generator.token_gen import make_unique_token, smart_token_key


def wif_cg_name(deck_name: str, gname: str) -> str:
    """Descriptor name for a WIF combat group: ``Descriptor_CombatGroup_<deck>_WIF_<gname>``."""
    deck_short = deck_name.replace("Descriptor_Deck_pion_", "")
    return f"Descriptor_CombatGroup_{deck_short}_WIF_{gname}"


def resolve_all_cg_names(deck_name: str, group_order: list[str], vanilla_cg_list: list[str]) -> dict[str, str]:
    """Map a deck's replica groups to its vanilla combat-group descriptor names.

    Tries to:
    1. Match HQ group to vanilla HQ group.
    2. Match non-HQ groups by letter match (e.g. A matches _A_ or _A).
    3. Match any remaining unmatched replica groups to unmatched vanilla groups by index order.
    4. Fall back to a WIF-prefixed name if no vanilla groups remain.

    REQUIRED for the campaign to load: the AG campaign binds pre-placed pawns/battalions to
    vanilla combat-group *names*. Renaming a kept group (e.g. to ``_WIF_A``) hangs the
    campaign loader.
    """
    mapping: dict[str, str] = {}

    hq_replicas = [g for g in group_order if g == "HQ"]
    non_hq_replicas = [g for g in group_order if g != "HQ"]

    hq_vanillas = []
    non_hq_vanillas = []
    for cg in vanilla_cg_list:
        cg_lower = cg.lower()
        if "_hq_" in cg_lower or cg_lower.endswith("_hq") or "_hq" in cg_lower:
            hq_vanillas.append(cg)
        else:
            non_hq_vanillas.append(cg)

    if hq_replicas and hq_vanillas:
        mapping[hq_replicas[0]] = hq_vanillas[0]

    unmatched_replicas = []
    matched_vanillas = set()

    for gname in non_hq_replicas:
        target_in = f"_{gname}_"
        target_end = f"_{gname}"
        matched = False
        for cg in non_hq_vanillas:
            if cg in matched_vanillas:
                continue
            cg_lower = cg.lower()
            if target_in.lower() in cg_lower or cg_lower.endswith(target_end.lower()):
                mapping[gname] = cg
                matched_vanillas.add(cg)
                matched = True
                break
        if not matched:
            unmatched_replicas.append(gname)

    unmatched_vanillas = [cg for cg in non_hq_vanillas if cg not in matched_vanillas and cg.startswith("Descriptor_CombatGroup_")]
    for r_gname, v_cg in zip(unmatched_replicas, unmatched_vanillas):
        mapping[r_gname] = v_cg

    # Fallback for any replica groups that didn't get mapped
    for gname in group_order:
        if gname not in mapping:
            mapping[gname] = wif_cg_name(deck_name, gname)

    return mapping


def resolve_cg_name(deck_name: str, gname: str, vanilla_cg_list: list[str]) -> str:
    """Map a single replica group name to the deck's matching vanilla combat-group descriptor name.

    Delegates to ``resolve_all_cg_names`` to keep behavior consistent.
    """
    mapping = resolve_all_cg_names(deck_name, [gname], vanilla_cg_list)
    return mapping.get(gname, wif_cg_name(deck_name, gname))


def generate_combat_group(
    assignment: Assignment,
    deck_state: DeckState,
    existing_tokens: set[str],
) -> str:
    """Emit one TDeckCombatGroupDescriptor for a single *assignment*.

    Tokens are added to *existing_tokens* in-place so callers can keep accumulating.
    """
    return generate_grouped_combat_group(
        gname=assignment.group_name,
        deck_name=assignment.deck_name,
        assignments=[assignment],
        deck_state=deck_state,
        existing_tokens=existing_tokens,
        is_hq=(assignment.group_name == "HQ"),
    )


def order_smart_groups(
    smart_group_items: list[tuple[str | None, list[Assignment]]],
    deck_name: str,
    gname: str,
    existing_tokens: set[str],
) -> list[tuple[str, bool, list[Assignment]]]:
    """Assign a token to each smart group and return ``(token, is_hq, assignments)`` items.

    *smart_group_items* must already be in the desired emission order.
    """
    out: list[tuple[str, bool, list[Assignment]]] = []
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


def sorted_smart_group_items(
    assignments: list[Assignment],
) -> list[tuple[str | None, list[Assignment]]]:
    """Group *assignments* by sub_group and sort tactically (HQ → numbered → named → SPT → ungrouped)."""
    grouped: dict[str, list[Assignment]] = {}
    ungrouped: list[Assignment] = []
    for a in assignments:
        if a.sub_group:
            grouped.setdefault(a.sub_group, []).append(a)
        else:
            ungrouped.append(a)

    items: list[tuple[str | None, list[Assignment]]] = []
    for sg_name, sg_assignments in grouped.items():
        items.append((sg_name, sg_assignments))
    for a in ungrouped:
        items.append((None, [a]))

    def sort_key(item):
        sg_name, sg_assignments = item
        if sg_name is None:
            return (4, "", sg_assignments[0].order)
        if sg_name == "HQ":
            return (0, "", 0)
        elif sg_name.isdigit():
            return (1, "", int(sg_name))
        elif sg_name == "SPT" or sg_name == "SUPPORT":
            return (3, "", 0)
        else:
            return (2, sg_name, 0)

    items.sort(key=sort_key)
    return items


def emission_ordered_assignments(assignments: list[Assignment]) -> list[Assignment]:
    """Flatten *assignments* in pack-emission order — grouped by sub_group with smart
    groups in tactical order, matching how ``generate_grouped_combat_group`` assigns pack
    indices. The export appends DeckPackList refs in this order so refs line up with the
    SmartGroup ``(start,count)`` tuples slot-for-slot.
    """
    ordered: list[Assignment] = []
    for _sg_name, sg_assignments in sorted_smart_group_items(assignments):
        ordered.extend(sg_assignments)
    return ordered


def generate_grouped_combat_group(
    gname: str,
    deck_name: str,
    assignments: list[Assignment],
    deck_state: DeckState,
    existing_tokens: set[str],
    is_hq: bool = False,
    cg_name: str | None = None,
    cg_token: str | None = None,
) -> str:
    """Emit one TDeckCombatGroupDescriptor containing smart groups for *assignments*.

    Smart groups are grouped by sub_group and sorted tactically. Pack indices count
    forward from ``deck_state.next_index`` (the export seeds an empty DeckState per deck
    so a replaced deck's indices start at 0).

    *cg_name* / *cg_token* — when the group maps to a vanilla combat group, the caller
    passes the vanilla descriptor name and token so the campaign keeps binding to it (see
    ``resolve_cg_name``). Otherwise a WIF name/token is generated.
    """
    group_name = cg_name or wif_cg_name(deck_name, gname)
    group_token = cg_token or make_unique_token(f"cg_WIF_{gname}", deck_name, existing_tokens)
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

    smart_group_items = sorted_smart_group_items(assignments)
    aligned_groups = order_smart_groups(smart_group_items, deck_name, gname, existing_tokens)

    # Assign pack indices in the SAME order the smart groups are emitted, so each combat
    # group's (start,count) tuples form an ascending, contiguous run — exactly how vanilla
    # lays out a combat group. A non-monotonic layout (indices assigned in replica order
    # but smart groups emitted in tactical/alphabetical order) compiles and resolves fine
    # but HANGS the Army General campaign loader. Each (xp_level, count) consumes `count`
    # consecutive DeckPackList slots, so the next assignment starts at curr + xp*count.
    # `build_export_blocks` appends the DeckPackList refs in this same order (via
    # emission_ordered_assignments) so refs and indices stay in lockstep.
    assignment_indices = {}
    curr = deck_state.next_index
    for _sg_name, sg_assignments in smart_group_items:
        for a in sg_assignments:
            assignment_indices[id(a)] = curr
            curr += len(a.xp_levels) * a.count

    for smart_token, sg_is_hq, sg_assignments in aligned_groups:
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
