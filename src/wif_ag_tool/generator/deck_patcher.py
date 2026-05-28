"""Emit deck patch text and optionally apply it to StrategicDecks.ndf in place."""
from __future__ import annotations
from pathlib import Path


def generate_deck_patch(
    deck_name: str,
    new_pack_refs: list[str],
    new_group_refs: list[str],
) -> str:
    """Return a human-readable patch describing what to append to the deck's two lists.

    *new_pack_refs* and *new_group_refs* are bare descriptor names (no ~/ prefix, no comma).
    """
    out: list[str] = []
    out.append(f"// === WIF AG PATCH for {deck_name} ===")
    out.append("// Append these lines to DeckPackList (before the closing ]):")
    out.append("")
    for ref in new_pack_refs:
        out.append(f"        ~/{ref},")
    out.append("")
    out.append("// Append these lines to DeckCombatGroupList (before the closing ]):")
    out.append("")
    for ref in new_group_refs:
        out.append(f"        ~/{ref},")
    out.append("")
    return "\n".join(out)


def apply_deck_patch(
    strategic_decks_path: Path,
    deck_name: str,
    new_pack_refs: list[str],
    new_group_refs: list[str],
) -> None:
    """Insert ~/refs before the closing ] of each list of *deck_name* in StrategicDecks.ndf."""
    text = strategic_decks_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=False)

    start = _find_deck_start(lines, deck_name)
    if start is None:
        raise KeyError(f"deck not found: {deck_name}")

    block_end = _find_block_end(lines, start)
    lines = _insert_into_list(lines, start, block_end, "DeckPackList", new_pack_refs)
    # block_end may have shifted
    block_end = _find_block_end(lines, start)
    lines = _insert_into_list(lines, start, block_end, "DeckCombatGroupList", new_group_refs)

    strategic_decks_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _find_deck_start(lines: list[str], deck_name: str) -> int | None:
    header = f"export {deck_name} is TDeckDescriptor"
    for i, line in enumerate(lines):
        if line.startswith(header):
            return i
    return None


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


def _insert_into_list(
    lines: list[str], start: int, end: int, list_name: str, refs: list[str]
) -> list[str]:
    """Find the closing `]` of *list_name* between [start, end) and insert refs above it."""
    if not refs:
        return lines

    header_idx = None
    for i in range(start, end):
        stripped = lines[i].strip()
        if stripped.startswith(list_name) and "=" in stripped:
            header_idx = i
            break
    if header_idx is None:
        raise KeyError(f"list {list_name} not found in deck block")

    # Walk from header_idx, track brackets, find matching closing ]
    depth = 0
    saw_open = False
    close_idx = None
    for i in range(header_idx, end):
        for ch in lines[i]:
            if ch == "[":
                depth += 1
                saw_open = True
            elif ch == "]":
                depth -= 1
                if saw_open and depth == 0:
                    close_idx = i
                    break
        if close_idx is not None:
            break
    if close_idx is None:
        raise ValueError(f"unterminated list {list_name}")

    insertion = [f"        ~/{ref}," for ref in refs]
    return lines[:close_idx] + insertion + lines[close_idx:]


def apply_combat_group_patches(
    strategic_groups_path: Path,
    group_blocks: list[str],
) -> None:
    """Find and replace existing combat group blocks in StrategicCombatGroups.ndf, or append them."""
    if not group_blocks:
        return

    import re
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
