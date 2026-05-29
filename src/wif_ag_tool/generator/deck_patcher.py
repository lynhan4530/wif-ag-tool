"""Emit deck patch text and apply it to StrategicDecks.ndf in place.

Full-replacement model: ``replace_deck_lists`` overwrites a deck's DeckPackList and
DeckCombatGroupList with exactly the replica-derived refs. ``generate_deck_patch``
produces a human-readable summary of those new lists for the zip-export / diff path.
"""
from __future__ import annotations
import re
from pathlib import Path


def generate_deck_patch(
    deck_name: str,
    new_pack_refs: list[str],
    new_group_refs: list[str],
) -> str:
    """Return a human-readable summary of the deck's new (fully-replaced) lists.

    *new_pack_refs* and *new_group_refs* are bare descriptor names (no ~/ prefix, no comma).
    """
    out: list[str] = []
    out.append(f"// === WIF AG full-replacement for {deck_name} ===")
    out.append("// DeckPackList is replaced with exactly these refs:")
    out.append("")
    for ref in new_pack_refs:
        out.append(f"        ~/{ref},")
    out.append("")
    out.append("// DeckCombatGroupList is replaced with exactly these refs:")
    out.append("")
    for ref in new_group_refs:
        out.append(f"        ~/{ref},")
    out.append("")
    return "\n".join(out)


def replace_deck_lists(
    strategic_decks_path: Path,
    deck_name: str,
    pack_refs: list[str],
    group_refs: list[str],
) -> None:
    """Overwrite *deck_name*'s DeckPackList and DeckCombatGroupList with exactly these refs.

    This is the full-replacement primitive: whatever the replica defines becomes the
    entire deck. Raises KeyError if the deck is not present in the file.
    """
    text = strategic_decks_path.read_text(encoding="utf-8")
    span = _find_block_span_chars(text, deck_name)
    if span is None:
        raise KeyError(f"deck not found: {deck_name}")
    block_start, block_end = span
    block = text[block_start:block_end]
    block = _replace_list_in_block(block, "DeckPackList", pack_refs)
    block = _replace_list_in_block(block, "DeckCombatGroupList", group_refs)
    text = text[:block_start] + block + text[block_end:]
    strategic_decks_path.write_text(text, encoding="utf-8")


def _find_block_span_chars(text: str, deck_name: str) -> tuple[int, int] | None:
    """Char offsets [start, end) of the ``export <deck_name> is TDeckDescriptor(...)`` block."""
    header = f"export {deck_name} is TDeckDescriptor"
    start = text.find(header)
    if start < 0:
        return None
    # Walk parens from the first '(' after the header to find the block end.
    open_paren = text.find("(", start)
    if open_paren < 0:
        return None
    depth = 0
    i = open_paren
    while i < len(text):
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return start, i + 1
        i += 1
    return start, len(text)


def _replace_list_in_block(block: str, list_name: str, refs: list[str]) -> str:
    """Replace everything between the brackets of *list_name* with *refs* (or empty)."""
    m = re.search(rf"\b{re.escape(list_name)}\s*=", block)
    if m is None:
        raise KeyError(f"list {list_name} not found in deck block")
    open_br = block.find("[", m.end())
    if open_br < 0:
        raise ValueError(f"no opening [ for {list_name}")
    depth = 0
    close_br = None
    for i in range(open_br, len(block)):
        if block[i] == "[":
            depth += 1
        elif block[i] == "]":
            depth -= 1
            if depth == 0:
                close_br = i
                break
    if close_br is None:
        raise ValueError(f"unterminated list {list_name}")

    if refs:
        inner = "\n" + "\n".join(f"        ~/{r}," for r in refs) + "\n    "
    else:
        inner = "\n    "
    return block[: open_br + 1] + inner + block[close_br:]


def _find_block_end(lines: list[str], start: int) -> int:
    """Return the line index just after the closing `)` of the descriptor block."""
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


def apply_combat_group_patches(
    strategic_groups_path: Path,
    group_blocks: list[str],
) -> None:
    """Find and replace existing combat group blocks in StrategicCombatGroups.ndf, or append them."""
    if not group_blocks:
        return

    text = strategic_groups_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=False)

    append_blocks = []

    for block in group_blocks:
        if not block.strip():
            continue
        first_line = block.splitlines()[0]
        # Match e.g. "Descriptor_CombatGroup_pion_US_11ACR_1_A_1_11th_ACR is TDeckCombatGroupDescriptor"
        m = re.match(r'^(\S+)\s+is\s+', first_line)
        if not m:
            append_blocks.append(block)
            continue

        cg_name = m.group(1)
        header = f"{cg_name} is TDeckCombatGroupDescriptor"
        
        start = None
        for i, line in enumerate(lines):
            if line.startswith(header):
                start = i
                break

        if start is not None:
            end = _find_block_end(lines, start)
            lines = lines[:start] + block.splitlines() + lines[end:]
        else:
            append_blocks.append(block)

    new_text = "\n".join(lines) + "\n"
    if append_blocks:
        new_text += "\n\n// === WIF AG additions ===\n\n" + "\n\n".join(append_blocks) + "\n"

    strategic_groups_path.write_text(new_text, encoding="utf-8")
