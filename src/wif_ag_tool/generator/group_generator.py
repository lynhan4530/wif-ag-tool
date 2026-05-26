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

    Each smart group references the next pack index.
    Tokens are added to *existing_tokens* in-place.
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

    current_index = deck_state.next_index
    for a in assignments:
        for offset, xp in enumerate(a.xp_levels):
            smart_token = make_unique_token(
                smart_token_key(a.unit_id, xp, a.seq),
                a.deck_name,
                existing_tokens,
            )
            existing_tokens.add(smart_token)
            lines.extend([
                "        TDeckSmartGroupDescriptor",
                "        (",
                f'            Name = "{smart_token}"',
                "            PackIndexUnitNumberList =",
                "            [",
                f"                ({current_index},{a.count}),",
                "            ]",
                "        ),",
            ])
            current_index += 1

    lines.extend(["    ]", ")"])
    return "\n".join(lines)
