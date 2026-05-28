"""Parse StrategicCombatGroups.ndf → CombatGroup → SmartGroup → (pack_index, count).

Used by the session-view center pane to render a vanilla deck's structure.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SmartGroup:
    name: str                              # 10-char token
    is_hq: bool = False
    pack_indices: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class CombatGroup:
    name: str                              # full descriptor name
    token: str = ""                        # 10-char Name field
    smart_groups: list[SmartGroup] = field(default_factory=list)
    is_hq: bool = False


# Each block starts with: ``<DescriptorName> is TDeckCombatGroupDescriptor``
_RE_BLOCK_HEAD = re.compile(
    r"^(Descriptor_CombatGroup_\S+)\s+is\s+TDeckCombatGroupDescriptor",
    re.MULTILINE,
)
_RE_TOP_NAME = re.compile(r"Name\s*=\s*\"([A-Z0-9]+)\"")
_RE_SMART_NAME = re.compile(r"Name\s*=\s*\"([A-Z0-9]+)\"")
_RE_IS_HQ = re.compile(r"IsHQ\s*=\s*True", re.IGNORECASE)
_RE_PACK_TUPLE = re.compile(r"\(\s*(\d+)\s*,\s*(\d+)\s*\)")


def _slice_smart_groups(block: str) -> list[str]:
    """Return the bodies of each TDeckSmartGroupDescriptor(...) found in *block*.

    Uses paren-depth walking so nested ``(idx,count)`` tuples don't trip up extraction.
    """
    bodies: list[str] = []
    marker = "TDeckSmartGroupDescriptor"
    i = 0
    while True:
        j = block.find(marker, i)
        if j < 0:
            break
        # Find the opening '(' for this descriptor (skipping whitespace).
        k = block.find("(", j + len(marker))
        if k < 0:
            break
        depth = 1
        end = k + 1
        while end < len(block) and depth > 0:
            ch = block[end]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break
            end += 1
        bodies.append(block[k + 1:end])
        i = end + 1
    return bodies


def parse_combat_groups(path: Path) -> dict[str, CombatGroup]:
    """Parse the file at *path* into a name → CombatGroup map."""
    text = Path(path).read_text(encoding="utf-8")

    # Find all top-level block headers; carve text into per-block segments.
    starts = [m.start() for m in _RE_BLOCK_HEAD.finditer(text)]
    names = [m.group(1) for m in _RE_BLOCK_HEAD.finditer(text)]
    # Append EOF sentinel to slice the last block
    starts.append(len(text))

    out: dict[str, CombatGroup] = {}
    for i, name in enumerate(names):
        block = text[starts[i]:starts[i + 1]]
        out[name] = _parse_block(name, block)
    return out


def _parse_block(name: str, block: str) -> CombatGroup:
    # The top-level Name token sits on a line BEFORE the first SmartGroupList entry.
    # Find the first Name match that occurs before the first TDeckSmartGroupDescriptor.
    smart_pos = block.find("TDeckSmartGroupDescriptor")
    head_region = block if smart_pos < 0 else block[:smart_pos]
    head_match = _RE_TOP_NAME.search(head_region)
    token = head_match.group(1) if head_match else ""
    is_hq = bool(_RE_IS_HQ.search(head_region))

    cg = CombatGroup(name=name, token=token, is_hq=is_hq)
    for smart in _slice_smart_groups(block):
        sg_name = _RE_SMART_NAME.search(smart)
        sg_is_hq = bool(_RE_IS_HQ.search(smart))
        tuples = [(int(a), int(b)) for a, b in _RE_PACK_TUPLE.findall(smart)]
        cg.smart_groups.append(SmartGroup(
            name=sg_name.group(1) if sg_name else "",
            is_hq=sg_is_hq,
            pack_indices=tuples,
        ))
    return cg


__all__ = ["CombatGroup", "SmartGroup", "parse_combat_groups"]
