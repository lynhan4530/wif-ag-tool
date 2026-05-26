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
    group_name = assignment.combat_group_name()
    group_token = make_unique_token(
        group_token_key(assignment.unit_id, assignment.seq),
        assignment.deck_name,
        existing_tokens,
    )
    existing_tokens.add(group_token)

    base_index = deck_state.next_index
    lines = [
        f"{group_name} is TDeckCombatGroupDescriptor",
        "(",
        f'    Name = "{group_token}"',
        "    SmartGroupList =",
        "    [",
    ]
    for offset, xp in enumerate(assignment.xp_levels):
        smart_token = make_unique_token(
            smart_token_key(assignment.unit_id, xp, assignment.seq),
            assignment.deck_name,
            existing_tokens,
        )
        existing_tokens.add(smart_token)
        index = base_index + offset
        lines.extend([
            "        TDeckSmartGroupDescriptor",
            "        (",
            f'            Name = "{smart_token}"',
            "            PackIndexUnitNumberList =",
            "            [",
            f"                ({index},{assignment.count}),",
            "            ]",
            "        ),",
        ])
    lines.extend(["    ]", ")"])
    return "\n".join(lines)
