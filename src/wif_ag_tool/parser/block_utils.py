"""NDF parsing block utilities for finding matching parentheses, brackets, and block spans."""
from __future__ import annotations


def find_matching_bracket(
    text: str,
    start_index: int,
    open_char: str = "(",
    close_char: str = ")",
) -> int | None:
    """Find the index of the matching closing bracket/paren/brace in text.

    Returns the 0-indexed char offset of the closing character, or None if not found.
    """
    depth = 0
    for idx in range(start_index, len(text)):
        ch = text[idx]
        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                return idx
    return None


def find_block_span(
    text: str,
    header: str,
    open_char: str = "(",
    close_char: str = ")",
) -> tuple[int, int] | None:
    """Locate header, find the first occurrence of open_char, and return the span (start, end)
    of the outer parenthesized/bracketed block.

    Returns (start_idx, end_idx) where start_idx is the index of header and end_idx is the character
    index immediately after the matching close_char. Returns None if not found.
    """
    start = text.find(header)
    if start < 0:
        return None
    open_idx = text.find(open_char, start)
    if open_idx < 0:
        return None
    close_idx = find_matching_bracket(text, open_idx, open_char, close_char)
    if close_idx is None:
        return None
    return start, close_idx + 1
