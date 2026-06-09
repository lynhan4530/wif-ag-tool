"""Patch unit stats in UniteDescriptor.ndf."""
from __future__ import annotations
import re
from pathlib import Path
from typing import Any

def _set_field_in_module(block: str, field_name: str, value: Any) -> str:
    """Set field_name to value inside the module block, preserving spacing/indentation if found."""
    # Match the field name, its spacing, the equals, spacing, and the value (word/reference/number)
    pattern = rf'(\b{field_name})(\s*)=(\s*)(\S+)'
    
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

def _patch_module_in_block(block: str, module_header: str, fields: dict[str, Any]) -> str:
    """Locate module_header inside the block and apply field replacements. Returns modified block."""
    module_start = block.find(module_header)
    if module_start < 0:
        return block

    m_open_paren = block.find("(", module_start)
    if m_open_paren < 0:
        return block

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
        return block

    module_block = block[module_start:module_end]

    for field_name, value in fields.items():
        if value is not None:
            module_block = _set_field_in_module(module_block, field_name, value)

    return block[:module_start] + module_block + block[module_end:]

def patch_unit_stats(
    unite_descriptor_path: Path,
    overrides: dict[str, tuple[int | None, int | None] | dict[str, Any]]
) -> None:
    """Read UniteDescriptor.ndf, locate each unit block, and override its stats."""
    if not unite_descriptor_path.exists():
        return

    text = unite_descriptor_path.read_text(encoding="utf-8")
    
    for unit_id, val in overrides.items():
        if isinstance(val, tuple):
            atk, dfn = val
            overrides_dict = {}
            if atk is not None: overrides_dict["attack_override"] = atk
            if dfn is not None: overrides_dict["defense_override"] = dfn
        else:
            overrides_dict = val

        if not overrides_dict:
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

        # 1. Patch TStrategicDataModuleDescriptor
        strat_fields = {}
        if "attack_override" in overrides_dict:
            strat_fields["UnitAttackValue"] = overrides_dict["attack_override"]
        if "defense_override" in overrides_dict:
            strat_fields["UnitDefenseValue"] = overrides_dict["defense_override"]
        if strat_fields:
            block = _patch_module_in_block(block, "TStrategicDataModuleDescriptor", strat_fields)

        # 2. Patch TBaseDamageModuleDescriptor or TDamageModuleDescriptor
        damage_fields = {}
        if "health" in overrides_dict:
            damage_fields["MaxPhysicalDamages"] = overrides_dict["health"]
        if "max_suppression" in overrides_dict:
            damage_fields["MaxSuppressionDamages"] = overrides_dict["max_suppression"]
        if damage_fields:
            if block.find("TBaseDamageModuleDescriptor") >= 0:
                block = _patch_module_in_block(block, "TBaseDamageModuleDescriptor", damage_fields)
            elif block.find("TDamageModuleDescriptor") >= 0:
                block = _patch_module_in_block(block, "TDamageModuleDescriptor", damage_fields)

        # 3. Patch TSupplyModuleDescriptor
        supply_fields = {}
        if "supply_capacity" in overrides_dict:
            supply_fields["SupplyCapacity"] = f"{float(overrides_dict['supply_capacity'])}"
        if supply_fields:
            block = _patch_module_in_block(block, "TSupplyModuleDescriptor", supply_fields)

        # Replace block in text
        text = text[:start] + block + text[block_end:]

    unite_descriptor_path.write_text(text, encoding="utf-8")
