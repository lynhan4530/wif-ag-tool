"""Parse TDeckDescriptor blocks from StrategicDecks.ndf."""
from __future__ import annotations
import re
from pathlib import Path

from wif_ag_tool.models import DeckState

_RE_DECK_EXPORT = re.compile(r'^export (Descriptor_Deck_\S+) is TDeckDescriptor')
_RE_DECK_PION = re.compile(r'^export (Descriptor_Deck_pion_\S+) is TDeckDescriptor')
_RE_LIST_ITEM = re.compile(r'~/(Descriptor_\S+?),?\s*$')


def parse_deck(path: Path, deck_name: str) -> DeckState:
    """Return the DeckState for *deck_name* found in StrategicDecks.ndf at *path*.

    Raises KeyError if the deck is not found.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    header = f"export {deck_name} is TDeckDescriptor"

    start = _find_header(lines, header)
    if start is None:
        raise KeyError(f"deck not found: {deck_name}")

    end = _find_block_end(lines, start)
    block = lines[start:end]

    pack_list = _extract_list_items(block, "DeckPackList")
    combat_group_list = _extract_list_items(block, "DeckCombatGroupList")

    return DeckState(name=deck_name, pack_list=pack_list, combat_group_list=combat_group_list)


def list_decks(path: Path, nation_prefix: str | None = None) -> list[str]:
    """Return all Descriptor_Deck_pion_* names. Filter by e.g. 'US', 'SOV', 'FR'."""
    text = path.read_text(encoding="utf-8", errors="replace")
    names: list[str] = []
    for line in text.splitlines():
        m = _RE_DECK_PION.match(line)
        if not m:
            continue
        name = m.group(1)
        if nation_prefix:
            # Descriptor_Deck_pion_<NATION>_...
            parts = name.split("_")
            if len(parts) < 4 or parts[3] != nation_prefix:
                continue
        names.append(name)
    return names


# ── internals ─────────────────────────────────────────────────────────────────

def _find_header(lines: list[str], header: str) -> int | None:
    for i, line in enumerate(lines):
        if line.startswith(header):
            return i
    return None


def _find_block_end(lines: list[str], start: int) -> int:
    """Find the end of the descriptor block starting at *start* by tracking paren depth."""
    depth = 0
    seen_open = False
    for i in range(start, len(lines)):
        for ch in lines[i]:
            if ch == "(":
                depth += 1
                seen_open = True
            elif ch == ")":
                depth -= 1
                if seen_open and depth == 0:
                    return i + 1
    return len(lines)


def _extract_list_items(block: list[str], list_name: str) -> list[str]:
    """Collect ~/Descriptor_* refs inside the named list of *block*."""
    items: list[str] = []
    in_list = False
    depth = 0
    header_re = re.compile(rf'^\s*{re.escape(list_name)}\s*=')
    for line in block:
        if not in_list:
            if header_re.match(line):
                in_list = True
                # consume any opening bracket on this line
                depth += line.count("[") - line.count("]")
                if "[" in line and depth == 0:
                    # single-line empty list
                    in_list = False
            continue
        depth += line.count("[") - line.count("]")
        m = _RE_LIST_ITEM.search(line.strip())
        if m:
            items.append(m.group(1))
        if depth <= 0:
            break
    return items
