"""Patch unit stats in UniteDescriptor.ndf."""
from __future__ import annotations
import re
from pathlib import Path

def _set_field_in_module(block: str, field_name: str, value: int) -> str:
    """Set field_name to value inside the module block, preserving spacing/indentation if found."""
    # Match the field name, its spacing, the equals, spacing, and the digits
    pattern = rf'(\b{field_name})(\s*)=(\s*)\d+'
    
    def repl(match):
        return f"{match.group(1)}{match.group(2)}={match.group(3)}{value}"
        
    if re.search(pattern, block):
        return re.sub(pattern, repl, block)
    else:
        # If field is not found in the block, insert it before the closing parenthesis
        last_paren = block.rfind(")")
        if last_paren >= 0:
            return block[:last_paren].rstrip() + f"\n            {field_name} = {value}\n        " + block[last_paren:]
        return block

def patch_unit_stats(
    unite_descriptor_path: Path,
    overrides: dict[str, tuple[int | None, int | None]]
) -> None:
    """Read UniteDescriptor.ndf, locate each unit block, and override its stats."""
    if not unite_descriptor_path.exists():
        return

    text = unite_descriptor_path.read_text(encoding="utf-8")
    
    # We iterate over overrides to perform replacements block by block
    for unit_id, (atk, dfn) in overrides.items():
        if atk is None and dfn is None:
            continue

        header = f"export Descriptor_Unit_{unit_id} is TEntityDescriptor"
        start = text.find(header)
        if start < 0:
            continue

        # Find the end of the descriptor block
        open_paren = text.find("(", start)
        if open_paren < 0:
            continue

        depth = 0
        block_end = None
        for i in range(open_paren, len(text)):
            ch = text[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    block_end = i + 1
                    break
        if block_end is None:
            continue

        block = text[start:block_end]

        module_header = "TStrategicDataModuleDescriptor"
        module_start = block.find(module_header)
        if module_start < 0:
            continue

        m_open_paren = block.find("(", module_start)
        if m_open_paren < 0:
            continue

        m_depth = 0
        module_end = None
        for i in range(m_open_paren, len(block)):
            ch = block[i]
            if ch == "(":
                m_depth += 1
            elif ch == ")":
                m_depth -= 1
                if m_depth == 0:
                    module_end = i + 1
                    break
        if module_end is None:
            continue

        module_block = block[module_start:module_end]

        if atk is not None:
            module_block = _set_field_in_module(module_block, "UnitAttackValue", atk)
        if dfn is not None:
            module_block = _set_field_in_module(module_block, "UnitDefenseValue", dfn)

        # Replace module block in block, then block in text
        modified_block = block[:module_start] + module_block + block[module_end:]
        text = text[:start] + modified_block + text[block_end:]

    unite_descriptor_path.write_text(text, encoding="utf-8")
