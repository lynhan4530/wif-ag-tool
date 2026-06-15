"""Patch ammunition stats in Ammunition.ndf."""
from __future__ import annotations
import re
from pathlib import Path
from typing import Any

from wif_ag_tool.generator.unit_patcher import _set_field_in_module
from wif_ag_tool.parser.block_utils import find_matching_bracket


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

        close_paren = find_matching_bracket(text, open_paren, "(", ")")
        if close_paren is None:
            continue
            
        block_end = close_paren + 1
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

        if "max_range_heli" in val and val["max_range_heli"] is not None:
            block = _set_field_in_module(block, "MaximumRangeHelicopterGRU", val["max_range_heli"])

        if "min_range_heli" in val and val["min_range_heli"] is not None:
            block = _set_field_in_module(block, "MinimumRangeHelicopterGRU", val["min_range_heli"])

        if "max_range_plane" in val and val["max_range_plane"] is not None:
            block = _set_field_in_module(block, "MaximumRangeAirplaneGRU", val["max_range_plane"])

        if "min_range_plane" in val and val["min_range_plane"] is not None:
            block = _set_field_in_module(block, "MinimumRangeAirplaneGRU", val["min_range_plane"])

        if "aiming_time" in val and val["aiming_time"] is not None:
            block = _set_field_in_module(block, "AimingTime", f"{float(val['aiming_time'])}")

        if "accuracy_static" in val and val["accuracy_static"] is not None:
            idling_pattern = r'(\(EBaseHitValueModifier/Idling\s*,\s*)[-\d\.]+(\))'
            if re.search(idling_pattern, block):
                block = re.sub(idling_pattern, rf'\g<1>{val["accuracy_static"]}\g<2>', block)

        if "accuracy_motion" in val and val["accuracy_motion"] is not None:
            moving_pattern = r'(\(EBaseHitValueModifier/Moving\s*,\s*)[-\d\.]+(\))'
            if re.search(moving_pattern, block):
                block = re.sub(moving_pattern, rf'\g<1>{val["accuracy_motion"]}\g<2>', block)
            
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

        if "traits" in val and val["traits"] is not None:
            formatted_list = "[ " + ", ".join(f"'{t}'" for t in val["traits"]) + ", ]" if val["traits"] else "[]"
            traits_pattern = r'TraitsToken\s*=\s*\[[^\]]*\]'
            if re.search(traits_pattern, block):
                block = re.sub(traits_pattern, f"TraitsToken = {formatted_list}", block)
            else:
                last_paren = block.rfind(")")
                if last_paren >= 0:
                    block = block[:last_paren].rstrip() + f"\n    TraitsToken = {formatted_list}\n" + block[last_paren:]

        # Replace block in text
        text = text[:start] + block + text[block_end:]

    ammo_path.write_text(text, encoding="utf-8")
