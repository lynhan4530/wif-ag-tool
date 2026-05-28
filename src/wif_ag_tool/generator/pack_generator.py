"""Emit DeckPackDescriptor NDF blocks."""
from __future__ import annotations

from wif_ag_tool.models import Assignment, make_pack_descriptor_name


def generate_pack(
    unit_id: str,
    xp: int,
    transport_id: str | None = None,
    seq: int = 0,
) -> str:
    """Emit a single DeckPackDescriptor block as a string.

    seq>0 inserts a sequence suffix between unit_id and xp so duplicate unit rows
    in the same deck get distinct pack descriptor names. Vanilla units (no WF_
    prefix) get a ``_v`` marker to avoid colliding with the packs already in
    vanilla StrategicPacks.ndf.
    """
    pack_name = make_pack_descriptor_name(unit_id, xp, seq)
    unit_ref = f"$/GFX/Unit/Descriptor_Unit_{unit_id}"
    lines = [f"{pack_name} is DeckPackDescriptor", "("]
    if transport_id:
        transport_ref = f"$/GFX/Unit/Descriptor_Unit_{transport_id}"
        lines.append(f"    Xp        = {xp}")
        lines.append(f"    Transport = {transport_ref}")
        lines.append(f"    Unit      = {unit_ref}")
    else:
        lines.append(f"    Xp   = {xp}")
        lines.append(f"    Unit = {unit_ref}")
    lines.append(")")
    return "\n".join(lines)


def generate_packs_for_assignment(assignment: Assignment, transport_id: str | None = None) -> str:
    """Emit all packs for all XP levels in an assignment. Newline-separated."""
    blocks = [
        generate_pack(assignment.unit_id, xp, transport_id=transport_id, seq=assignment.seq)
        for xp in assignment.xp_levels
    ]
    return "\n\n".join(blocks)
