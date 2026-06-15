"""Patch unit stats in UniteDescriptor.ndf."""
from __future__ import annotations
import re
from pathlib import Path
from typing import Any

from wif_ag_tool.parser.block_utils import find_block_span, find_matching_bracket

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
    span = find_block_span(block, module_header)
    if not span:
        return block
    start, end = span
    module_block = block[start:end]

    for field_name, value in fields.items():
        if value is not None:
            module_block = _set_field_in_module(module_block, field_name, value)

    return block[:start] + module_block + block[end:]

def _patch_cost_in_block(block: str, cost: int) -> str:
    span = find_block_span(block, "TProductionModuleDescriptor")
    if not span:
        return block
    start, end = span
    prod_block = block[start:end]
    
    cost_pattern = r'(\(\s*\$/GFX/Resources/Resource_CommandPoints\s*,\s*)\d+(\s*\))'
    if re.search(cost_pattern, prod_block):
        prod_block = re.sub(cost_pattern, rf'\g<1>{cost}\g<2>', prod_block)
        return block[:start] + prod_block + block[end:]
    return block

def _patch_armor_in_block(block: str, armor_fields: dict[str, int]) -> str:
    span = find_block_span(block, "TDamageModuleDescriptor")
    if not span:
        return block
    start, end = span
    dmg_block = block[start:end]
    
    bp_span = find_block_span(dmg_block, "BlindageProperties = TBlindageProperties")
    if bp_span:
        bp_start, bp_end = bp_span
        bp_block = dmg_block[bp_start:bp_end]
        
        if "armor_front" in armor_fields:
            pat = r'(ResistanceFront\s*=\s*TResistanceTypeRTTI\s*\(\s*Family\s*=\s*[\w_]+\s+Index\s*=\s*)\d+(\s*\))'
            if re.search(pat, bp_block):
                bp_block = re.sub(pat, rf'\g<1>{armor_fields["armor_front"]}\g<2>', bp_block)
        if "armor_sides" in armor_fields:
            pat = r'(ResistanceSides\s*=\s*TResistanceTypeRTTI\s*\(\s*Family\s*=\s*[\w_]+\s+Index\s*=\s*)\d+(\s*\))'
            if re.search(pat, bp_block):
                bp_block = re.sub(pat, rf'\g<1>{armor_fields["armor_sides"]}\g<2>', bp_block)
        if "armor_rear" in armor_fields:
            pat = r'(ResistanceRear\s*=\s*TResistanceTypeRTTI\s*\(\s*Family\s*=\s*[\w_]+\s+Index\s*=\s*)\d+(\s*\))'
            if re.search(pat, bp_block):
                bp_block = re.sub(pat, rf'\g<1>{armor_fields["armor_rear"]}\g<2>', bp_block)
        if "armor_top" in armor_fields:
            pat = r'(ResistanceTop\s*=\s*TResistanceTypeRTTI\s*\(\s*Family\s*=\s*[\w_]+\s+Index\s*=\s*)\d+(\s*\))'
            if re.search(pat, bp_block):
                bp_block = re.sub(pat, rf'\g<1>{armor_fields["armor_top"]}\g<2>', bp_block)
                
        dmg_block = dmg_block[:bp_start] + bp_block + dmg_block[bp_end:]
        return block[:start] + dmg_block + block[end:]
    return block

def _patch_optics_in_block(block: str, optics_val: float) -> str:
    span = find_block_span(block, "TScannerConfigurationDescriptor")
    if not span:
        return block
    start, end = span
    scanner_block = block[start:end]
    
    optics_pattern = r'(\(\s*EOpticalStrength/Standard\s*,\s*)[-\d\.]+(\s*\))'
    if re.search(optics_pattern, scanner_block):
        scanner_block = re.sub(optics_pattern, rf'\g<1>{optics_val}\g<2>', scanner_block)
        return block[:start] + scanner_block + block[end:]
    return block

def _patch_fwd_deploy_in_block(block: str, fwd_val: float) -> str:
    if "TDeploymentShiftModuleDescriptor" in block:
        if fwd_val <= 0:
            return _patch_module_in_block(block, "TDeploymentShiftModuleDescriptor", {"DeploymentShiftGRU": 0.0})
        else:
            return _patch_module_in_block(block, "TDeploymentShiftModuleDescriptor", {"DeploymentShiftGRU": fwd_val})
    else:
        if fwd_val > 0:
            insert_idx = block.find("ModulesDescriptors = [")
            if insert_idx >= 0:
                bracket_idx = block.find("[", insert_idx)
                if bracket_idx >= 0:
                    new_module = f"\n        TDeploymentShiftModuleDescriptor\n        (\n            DeploymentShiftGRU = {fwd_val}\n        ),"
                    return block[:bracket_idx + 1] + new_module + block[bracket_idx + 1:]
        return block

def _patch_amphibious_in_block(block: str, amphibious: bool) -> str:
    # 1. Update PathfindType in TGenericMovementModuleDescriptor
    mov_span = find_block_span(block, "TGenericMovementModuleDescriptor")
    if mov_span:
        mov_start, mov_end = mov_span
        mov_block = block[mov_start:mov_end]
        pat = r'(PathfindType\s*=\s*\$/Pathfind/PathfindTypes/)(\w+)'
        match = re.search(pat, mov_block)
        if match:
            orig_type = match.group(2)
            if amphibious:
                if orig_type == "Vehicle":
                    new_type = "AmphibiousVehicle"
                    mov_block = re.sub(pat, rf'\g<1>{new_type}', mov_block)
            else:
                if orig_type == "AmphibiousVehicle":
                    new_type = "Vehicle"
                    mov_block = re.sub(pat, rf'\g<1>{new_type}', mov_block)
            block = block[:mov_start] + mov_block + block[mov_end:]

    # 2. Update UnitMovingType in TLandMovementModuleDescriptor
    land_span = find_block_span(block, "TLandMovementModuleDescriptor")
    if land_span:
        land_start, land_end = land_span
        land_block = block[land_start:land_end]
        pat = r'(UnitMovingType\s*=\s*EUnitMovingType/)(\w+)'
        match = re.search(pat, land_block)
        if match:
            orig_moving = match.group(2)
            if amphibious:
                if orig_moving == "Track":
                    new_moving = "TrackAmphibious"
                    land_block = re.sub(pat, rf'\g<1>{new_moving}', land_block)
                elif orig_moving == "Wheel":
                    new_moving = "WheelAmphibious"
                    land_block = re.sub(pat, rf'\g<1>{new_moving}', land_block)
            else:
                if orig_moving == "TrackAmphibious":
                    new_moving = "Track"
                    land_block = re.sub(pat, rf'\g<1>{new_moving}', land_block)
                elif orig_moving == "WheelAmphibious":
                    new_moving = "Wheel"
                    land_block = re.sub(pat, rf'\g<1>{new_moving}', land_block)
            block = block[:land_start] + land_block + block[land_end:]
    return block

def _patch_specialties_in_block(block: str, specialties_list: list[str]) -> str:
    span = find_block_span(block, "TUnitUIModuleDescriptor")
    if not span:
        return block
    start, end = span
    ui_block = block[start:end]
    
    formatted_list = "[\n" + ",\n".join(f"                '{spec}'" for spec in specialties_list) + "\n            ]" if specialties_list else "[]"
    
    list_pattern = r'SpecialtiesList\s*=\s*\[[^\]]*\]'
    if re.search(list_pattern, ui_block):
        ui_block = re.sub(list_pattern, f"SpecialtiesList = {formatted_list}", ui_block)
    else:
        last_paren = ui_block.rfind(")")
        if last_paren >= 0:
            ui_block = ui_block[:last_paren].rstrip() + f"\n            SpecialtiesList = {formatted_list}\n        " + ui_block[last_paren:]
            
    return block[:start] + ui_block + block[end:]

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
        span = find_block_span(text, header)
        if not span:
            continue
        start, block_end = span
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

        # 4. Patch cost in TProductionModuleDescriptor
        if "cost" in overrides_dict:
            block = _patch_cost_in_block(block, overrides_dict["cost"])

        # 5. Patch armor in TDamageModuleDescriptor
        armor_fields = {}
        for k in ("armor_front", "armor_sides", "armor_rear", "armor_top"):
            if k in overrides_dict:
                armor_fields[k] = overrides_dict[k]
        if armor_fields:
            block = _patch_armor_in_block(block, armor_fields)

        # 6. Patch speed in TGenericMovementModuleDescriptor
        if "speed" in overrides_dict:
            block = _patch_module_in_block(block, "TGenericMovementModuleDescriptor", {"MaxSpeedInKmph": overrides_dict["speed"]})

        # 7. Patch road speed in TUnitUIModuleDescriptor
        if "road_speed" in overrides_dict:
            block = _patch_module_in_block(block, "TUnitUIModuleDescriptor", {"DisplayRoadSpeedInKmph": overrides_dict["road_speed"]})

        # 8. Patch fuel configuration in TFuelModuleDescriptor
        fuel_fields = {}
        if "fuel_capacity" in overrides_dict:
            fuel_fields["FuelCapacity"] = overrides_dict["fuel_capacity"]
        if "fuel_move_duration" in overrides_dict:
            fuel_fields["FuelMoveDuration"] = f"{float(overrides_dict['fuel_move_duration'])}"
        if fuel_fields:
            block = _patch_module_in_block(block, "TFuelModuleDescriptor", fuel_fields)

        # 9. Patch optics under TScannerConfigurationDescriptor
        if "optics" in overrides_dict:
            block = _patch_optics_in_block(block, float(overrides_dict["optics"]))

        # 10. Patch stealth (concealment bonus) under TVisibilityModuleDescriptor
        if "stealth" in overrides_dict:
            block = _patch_module_in_block(block, "TVisibilityModuleDescriptor", {"UnitConcealmentBonus": float(overrides_dict["stealth"])})

        # 11. Patch fwd_deploy under TDeploymentShiftModuleDescriptor
        if "fwd_deploy" in overrides_dict:
            block = _patch_fwd_deploy_in_block(block, float(overrides_dict["fwd_deploy"]))

        # 12. Patch amphibious under TGenericMovementModuleDescriptor & TLandMovementModuleDescriptor
        if "amphibious" in overrides_dict:
            block = _patch_amphibious_in_block(block, bool(overrides_dict["amphibious"]))

        # 13. Patch SpecialtiesList under TUnitUIModuleDescriptor
        if "specialties" in overrides_dict:
            block = _patch_specialties_in_block(block, list(overrides_dict["specialties"]))

        # Replace block in text
        text = text[:start] + block + text[block_end:]

    unite_descriptor_path.write_text(text, encoding="utf-8")
