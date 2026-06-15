"""Parse Ammunition.ndf."""
from __future__ import annotations
import re
import json
from pathlib import Path

_RE_EXPORT = re.compile(r'^\s*(\w+)\s+is\s+TAmmunitionDescriptor')
_RE_GUID   = re.compile(r'DescriptorId\s*=\s*GUID:\{([^}]+)\}')
_RE_NAME   = re.compile(r"Name\s*=\s*'(\w+)'")
_RE_ARME   = re.compile(r'Arme\s*=\s*TDamageTypeRTTI\s*\(\s*Family\s*=\s*(\w+)\s*Index\s*=\s*(\d+)\s*\)')
_RE_MAX_RANGE = re.compile(r'MaximumRangeGRU\s*=\s*(\d+)')
_RE_MIN_RANGE = re.compile(r'MinimumRangeGRU\s*=\s*(\d+)')
_RE_MAX_RANGE_HELI = re.compile(r'MaximumRangeHelicopterGRU\s*=\s*(\d+)')
_RE_MIN_RANGE_HELI = re.compile(r'MinimumRangeHelicopterGRU\s*=\s*(\d+)')
_RE_MAX_RANGE_PLANE = re.compile(r'MaximumRangeAirplaneGRU\s*=\s*(\d+)')
_RE_MIN_RANGE_PLANE = re.compile(r'MinimumRangeAirplaneGRU\s*=\s*(\d+)')
_RE_TIME_SHOTS = re.compile(r'TimeBetweenTwoShots\s*=\s*(\d+(?:\.\d+)?)')
_RE_TIME_SALVOS = re.compile(r'TimeBetweenTwoSalvos\s*=\s*([-\d\.]+)')
_RE_SHOTS_SALVO = re.compile(r'ShotsCountPerSalvo\s*=\s*(\d+)')
_RE_PHYS_DAMAGE = re.compile(r'PhysicalDamages\s*=\s*(\d+(?:\.\d+)?)')
_RE_SUPP_DAMAGE = re.compile(r'SuppressDamages\s*=\s*(\d+(?:\.\d+)?)')
_RE_SUPPLY_COST = re.compile(r'SupplyCost\s*=\s*(\d+(?:\.\d+)?)')
_RE_AIMING_TIME = re.compile(r'AimingTime\s*=\s*(\d+(?:\.\d+)?)')
_RE_ACC_STATIC = re.compile(r'\(EBaseHitValueModifier/Idling\s*,\s*([-\d\.]+)\)')
_RE_ACC_MOTION = re.compile(r'\(EBaseHitValueModifier/Moving\s*,\s*([-\d\.]+)\)')
_RE_TRAITS     = re.compile(r'TraitsToken\s*=\s*\[([^\]]*)\]', re.DOTALL)

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
                
            name_token_m = _RE_NAME.search(block)
            arme_m = _RE_ARME.search(block)
            max_range_m = _RE_MAX_RANGE.search(block)
            min_range_m = _RE_MIN_RANGE.search(block)
            max_range_heli_m = _RE_MAX_RANGE_HELI.search(block)
            min_range_heli_m = _RE_MIN_RANGE_HELI.search(block)
            max_range_plane_m = _RE_MAX_RANGE_PLANE.search(block)
            min_range_plane_m = _RE_MIN_RANGE_PLANE.search(block)
            time_shots_m = _RE_TIME_SHOTS.search(block)
            time_salvos_m = _RE_TIME_SALVOS.search(block)
            shots_salvo_m = _RE_SHOTS_SALVO.search(block)
            phys_damage_m = _RE_PHYS_DAMAGE.search(block)
            supp_damage_m = _RE_SUPP_DAMAGE.search(block)
            supply_cost_m = _RE_SUPPLY_COST.search(block)
            aiming_time_m = _RE_AIMING_TIME.search(block)
            acc_static_m = _RE_ACC_STATIC.search(block)
            acc_motion_m = _RE_ACC_MOTION.search(block)
            traits_m = _RE_TRAITS.search(block)
            traits = []
            if traits_m:
                traits = re.findall(r"'([^']+)'", traits_m.group(1))
            
            results[full_name] = {
                "name": full_name,
                "guid": guid_m.group(1),
                "name_token": name_token_m.group(1) if name_token_m else "",
                "damage_family": arme_m.group(1) if arme_m else "DamageFamily_he",
                "damage_index": int(arme_m.group(2)) if arme_m else 0,
                "max_range": int(max_range_m.group(1)) if max_range_m else 0,
                "min_range": int(min_range_m.group(1)) if min_range_m else 0,
                "max_range_heli": int(max_range_heli_m.group(1)) if max_range_heli_m else 0,
                "min_range_heli": int(min_range_heli_m.group(1)) if min_range_heli_m else 0,
                "max_range_plane": int(max_range_plane_m.group(1)) if max_range_plane_m else 0,
                "min_range_plane": int(min_range_plane_m.group(1)) if min_range_plane_m else 0,
                "time_between_shots": float(time_shots_m.group(1)) if time_shots_m else 0.0,
                "time_between_salvos": float(time_salvos_m.group(1)) if time_salvos_m else 0.0,
                "shots_per_salvo": int(shots_salvo_m.group(1)) if shots_salvo_m else 1,
                "physical_damages": float(phys_damage_m.group(1)) if phys_damage_m else 1.0,
                "suppress_damages": float(supp_damage_m.group(1)) if supp_damage_m else 0.0,
                "supply_cost": float(supply_cost_m.group(1)) if supply_cost_m else 0.0,
                "aiming_time": float(aiming_time_m.group(1)) if aiming_time_m else 0.0,
                "accuracy_static": float(acc_static_m.group(1)) if acc_static_m else 0.0,
                "accuracy_motion": float(acc_motion_m.group(1)) if acc_motion_m else 0.0,
                "traits": traits,
            }
        else:
            i += 1
            
    return results

def load_wif_ammo() -> dict[str, dict]:
    from wif_ag_tool import config
    
    cache_path = config.WIF_AMMO_CACHE
    ndf_ammo = config.WIF_AMMO
    ndf_missiles = config.WIF_AMMO_MISSILES
    
    use_cache = cache_path.exists()
    if use_cache:
        # Check against st_mtime of whichever source file exists
        if ndf_ammo.exists() and cache_path.stat().st_mtime < ndf_ammo.stat().st_mtime:
            use_cache = False
        if ndf_missiles.exists() and cache_path.stat().st_mtime < ndf_missiles.stat().st_mtime:
            use_cache = False

    if use_cache:
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"warn: failed to load WIF ammo cache: {e}")

    has_source = False
    ammo = {}
    if ndf_ammo.exists():
        ammo.update(parse_ammo(ndf_ammo))
        has_source = True
    if ndf_missiles.exists():
        ammo.update(parse_ammo(ndf_missiles))
        has_source = True
        
    if has_source:
        try:
            config.WIF_AMMO_CACHE.parent.mkdir(parents=True, exist_ok=True)
            config.WIF_AMMO_CACHE.write_text(json.dumps(ammo, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"warn: failed to cache WIF ammo: {e}")
        return ammo
    elif cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"warn: failed to load WIF ammo cache: {e}")
    return {}

def load_vanilla_ammo() -> dict[str, dict]:
    from wif_ag_tool import config
    
    cache_path = config.VANILLA_AMMO_CACHE
    ndf_ammo = config.VANILLA_AMMO
    ndf_missiles = config.VANILLA_AMMO_MISSILES
    
    use_cache = cache_path.exists()
    if use_cache:
        if ndf_ammo.exists() and cache_path.stat().st_mtime < ndf_ammo.stat().st_mtime:
            use_cache = False
        if ndf_missiles.exists() and cache_path.stat().st_mtime < ndf_missiles.stat().st_mtime:
            use_cache = False

    if use_cache:
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"warn: failed to load vanilla ammo cache: {e}")

    has_source = False
    ammo = {}
    if ndf_ammo.exists():
        ammo.update(parse_ammo(ndf_ammo))
        has_source = True
    if ndf_missiles.exists():
        ammo.update(parse_ammo(ndf_missiles))
        has_source = True
        
    if has_source:
        try:
            config.VANILLA_AMMO_CACHE.parent.mkdir(parents=True, exist_ok=True)
            config.VANILLA_AMMO_CACHE.write_text(json.dumps(ammo, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"warn: failed to cache vanilla ammo: {e}")
        return ammo
    elif cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"warn: failed to load vanilla ammo cache: {e}")
    return {}
