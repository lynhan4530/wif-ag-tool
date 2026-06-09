"""Parse Ammunition.ndf."""
from __future__ import annotations
import re
import json
from pathlib import Path

_RE_EXPORT = re.compile(r'^\s*(\w+)\s+is\s+TAmmunitionDescriptor')
_RE_GUID   = re.compile(r'DescriptorId\s*=\s*GUID:\{([^}]+)\}')
_RE_ARME   = re.compile(r'Arme\s*=\s*TDamageTypeRTTI\s*\(\s*Family\s*=\s*(\w+)\s*Index\s*=\s*(\d+)\s*\)')
_RE_MAX_RANGE = re.compile(r'MaximumRangeGRU\s*=\s*(\d+)')
_RE_MIN_RANGE = re.compile(r'MinimumRangeGRU\s*=\s*(\d+)')
_RE_TIME_SHOTS = re.compile(r'TimeBetweenTwoShots\s*=\s*(\d+(?:\.\d+)?)')
_RE_TIME_SALVOS = re.compile(r'TimeBetweenTwoSalvos\s*=\s*([-\d\.]+)')
_RE_SHOTS_SALVO = re.compile(r'ShotsCountPerSalvo\s*=\s*(\d+)')
_RE_PHYS_DAMAGE = re.compile(r'PhysicalDamages\s*=\s*(\d+(?:\.\d+)?)')
_RE_SUPP_DAMAGE = re.compile(r'SuppressDamages\s*=\s*(\d+(?:\.\d+)?)')
_RE_SUPPLY_COST = re.compile(r'SupplyCost\s*=\s*(\d+(?:\.\d+)?)')

def parse_ammo(path: Path) -> dict[str, dict]:
    """Parse ammunition descriptors from path."""
    if not path.exists():
        return {}
        
    text = path.read_text(encoding="utf-8", errors="replace")
    results: dict[str, dict] = {}
    
    # Split by blocks. In Ammunition.ndf, blocks do not always have export prefix.
    # We scan line by line to find blocks.
    lines = text.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        m = _RE_EXPORT.match(lines[i])
        if m:
            full_name = m.group(1)
            start = i
            i += 1
            # Find the end of this block by paren balancing or next block
            open_paren = -1
            for idx in range(start, min(start + 5, n)):
                if '(' in lines[idx]:
                    open_paren = idx
                    break
            if open_paren == -1:
                continue
                
            depth = 0
            block_end = None
            for idx in range(open_paren, n):
                # Check if next block starts to prevent runaway parsing if paren matching fails
                if idx > open_paren and _RE_EXPORT.match(lines[idx]):
                    block_end = idx
                    i = idx
                    break
                for ch in lines[idx]:
                    if ch == '(':
                        depth += 1
                    elif ch == ')':
                        depth -= 1
                        if depth == 0:
                            block_end = idx + 1
                            i = idx + 1
                            break
                if block_end is not None:
                    break
            if block_end is None:
                break
                
            block = "\n".join(lines[start:block_end])
            
            guid_m = _RE_GUID.search(block)
            if not guid_m:
                continue
                
            arme_m = _RE_ARME.search(block)
            max_range_m = _RE_MAX_RANGE.search(block)
            min_range_m = _RE_MIN_RANGE.search(block)
            time_shots_m = _RE_TIME_SHOTS.search(block)
            time_salvos_m = _RE_TIME_SALVOS.search(block)
            shots_salvo_m = _RE_SHOTS_SALVO.search(block)
            phys_damage_m = _RE_PHYS_DAMAGE.search(block)
            supp_damage_m = _RE_SUPP_DAMAGE.search(block)
            supply_cost_m = _RE_SUPPLY_COST.search(block)
            
            results[full_name] = {
                "name": full_name,
                "guid": guid_m.group(1),
                "damage_family": arme_m.group(1) if arme_m else "DamageFamily_he",
                "damage_index": int(arme_m.group(2)) if arme_m else 0,
                "max_range": int(max_range_m.group(1)) if max_range_m else 0,
                "min_range": int(min_range_m.group(1)) if min_range_m else 0,
                "time_between_shots": float(time_shots_m.group(1)) if time_shots_m else 0.0,
                "time_between_salvos": float(time_salvos_m.group(1)) if time_salvos_m else 0.0,
                "shots_per_salvo": int(shots_salvo_m.group(1)) if shots_salvo_m else 1,
                "physical_damages": float(phys_damage_m.group(1)) if phys_damage_m else 1.0,
                "suppress_damages": float(supp_damage_m.group(1)) if supp_damage_m else 0.0,
                "supply_cost": float(supply_cost_m.group(1)) if supply_cost_m else 0.0,
            }
        else:
            i += 1
            
    return results

def load_wif_ammo() -> dict[str, dict]:
    from wif_ag_tool import config
    
    if config.WIF_AMMO.exists():
        ammo = parse_ammo(config.WIF_AMMO)
        try:
            config.WIF_AMMO_CACHE.parent.mkdir(parents=True, exist_ok=True)
            config.WIF_AMMO_CACHE.write_text(json.dumps(ammo, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"warn: failed to cache WIF ammo: {e}")
        return ammo
    elif config.WIF_AMMO_CACHE.exists():
        try:
            return json.loads(config.WIF_AMMO_CACHE.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"warn: failed to load WIF ammo cache: {e}")
    return {}

def load_vanilla_ammo() -> dict[str, dict]:
    from wif_ag_tool import config
    
    if config.VANILLA_AMMO.exists():
        ammo = parse_ammo(config.VANILLA_AMMO)
        try:
            config.VANILLA_AMMO_CACHE.parent.mkdir(parents=True, exist_ok=True)
            config.VANILLA_AMMO_CACHE.write_text(json.dumps(ammo, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"warn: failed to cache vanilla ammo: {e}")
        return ammo
    elif config.VANILLA_AMMO_CACHE.exists():
        try:
            return json.loads(config.VANILLA_AMMO_CACHE.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"warn: failed to load vanilla ammo cache: {e}")
    return {}
