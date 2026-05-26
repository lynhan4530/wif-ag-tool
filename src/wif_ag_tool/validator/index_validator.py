"""Validate that a pack index is within bounds for a DeckState."""
from __future__ import annotations

from wif_ag_tool.models import DeckState


class IndexOutOfBoundsError(Exception):
    pass


def validate_pack_index(index: int, deck_state: DeckState) -> None:
    """Valid range: 0 .. next_index (inclusive). next_index itself is valid for appends."""
    if index < 0 or index > deck_state.next_index:
        raise IndexOutOfBoundsError(
            f"index {index} out of bounds for deck {deck_state.name} (next_index={deck_state.next_index})"
        )
