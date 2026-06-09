"""Patch ammunition stats in Ammunition.ndf."""
from __future__ import annotations
import re
from pathlib import Path
from typing import Any

from wif_ag_tool.generator.unit_patcher import _set_field_in_module

def patch_ammo_stats(
    ammo_path: Path,
    overrides: dict[str, dict[str, Any]]
) -> None:
    """Read Ammunition.ndf, locate each ammo block, and override its stats."""
    if not ammo_path.exists():
        return

    text = ammo_path.read_text(encoding="utf-8")
    
    for ammo_id, val in overrides.items():
        if not val:
            continue

        header_pattern = rf'^\s*({re.escape(ammo_id)})\s+is\s+TAmmunitionDescriptor'
        m = re.search(header_pattern, text, re.MULTILINE)
        if not m:
            continue
            
        start = m.start()

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

        # Apply field replacements inside this block
        if "max_range" in val and val["max_range"] is not None:
            block = _set_field_in_module(block, "MaximumRangeGRU", val["max_range"])
            
        if "min_range" in val and val["min_range"] is not None:
            block = _set_field_in_module(block, "MinimumRangeGRU", val["min_range"])
            
        if "time_between_shots" in val and val["time_between_shots"] is not None:
            block = _set_field_in_module(block, "TimeBetweenTwoShots", f"{float(val['time_between_shots'])}")
            
        if "time_between_salvos" in val and val["time_between_salvos"] is not None:
            block = _set_field_in_module(block, "TimeBetweenTwoSalvos", f"{float(val['time_between_salvos'])}")
            
        if "shots_per_salvo" in val and val["shots_per_salvo"] is not None:
            block = _set_field_in_module(block, "ShotsCountPerSalvo", val["shots_per_salvo"])
            block = _set_field_in_module(block, "AffichageMunitionParSalve", val["shots_per_salvo"])
            
        if "supply_cost" in val and val["supply_cost"] is not None:
            block = _set_field_in_module(block, "SupplyCost", f"{float(val['supply_cost'])}")
            
        if "physical_damages" in val and val["physical_damages"] is not None:
            block = _set_field_in_module(block, "PhysicalDamages", f"{float(val['physical_damages'])}")

        if "suppress_damages" in val and val["suppress_damages"] is not None:
            block = _set_field_in_module(block, "SuppressDamages", f"{float(val['suppress_damages'])}")
            
        # Patch Arme Family and Index
        if ("damage_family" in val and val["damage_family"] is not None) or ("damage_index" in val and val["damage_index"] is not None):
            arme_pattern = r'(Arme\s*=\s*TDamageTypeRTTI\s*\(\s*Family\s*=\s*)(\w+)(\s*Index\s*=\s*)(\d+)(\s*\))'
            arme_match = re.search(arme_pattern, block)
            if arme_match:
                orig_family = arme_match.group(2)
                orig_index = arme_match.group(4)
                
                new_family = val.get("damage_family") or orig_family
                new_index = val.get("damage_index") if val.get("damage_index") is not None else orig_index
                
                replacement = f"{arme_match.group(1)}{new_family}{arme_match.group(3)}{new_index}{arme_match.group(5)}"
                block = re.sub(arme_pattern, replacement, block)

        # Replace block in text
        text = text[:start] + block + text[block_end:]

    ammo_path.write_text(text, encoding="utf-8")
