"""Parse WeaponDescriptor.ndf."""
from __future__ import annotations
import re
from pathlib import Path

_RE_EXPORT = re.compile(r'^export (WeaponDescriptor_\S+) is TWeaponManagerModuleDescriptor')
_RE_AMMO   = re.compile(r'Ammunition\s*=\s*\$/GFX/Weapon/(\S+)')

def parse_weapons(path: Path) -> dict[str, list[str]]:
    """Parse weapon descriptors from path, return mapping of weapon_name -> list of ammo_names."""
    if not path.exists():
        return {}
        
    text = path.read_text(encoding="utf-8", errors="replace")
    results: dict[str, list[str]] = {}
    
    # Split by export lines
    lines = text.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        m = _RE_EXPORT.match(lines[i])
        if m:
            full_name = m.group(1)
            start = i
            i += 1
            while i < n and not _RE_EXPORT.match(lines[i]):
                i += 1
            block = "\n".join(lines[start:i])
            
            # Find all ammunition refs in this block
            ammo_refs = _RE_AMMO.findall(block)
            # Dedup while preserving order
            seen = set()
            deduped = []
            for ref in ammo_refs:
                if ref not in seen:
                    seen.add(ref)
                    deduped.append(ref)
                    
            results[full_name] = deduped
        else:
            i += 1
            
    return results

def load_wif_weapons() -> dict[str, list[str]]:
    from wif_ag_tool import config
    import json
    
    if config.WIF_WEAPON_DESCRIPTOR.exists():
        weapons = parse_weapons(config.WIF_WEAPON_DESCRIPTOR)
        try:
            config.WIF_WEAPONS_CACHE.parent.mkdir(parents=True, exist_ok=True)
            config.WIF_WEAPONS_CACHE.write_text(json.dumps(weapons, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"warn: failed to cache WIF weapons: {e}")
        return weapons
    elif config.WIF_WEAPONS_CACHE.exists():
        try:
            return json.loads(config.WIF_WEAPONS_CACHE.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"warn: failed to load WIF weapons cache: {e}")
    return {}

def load_vanilla_weapons() -> dict[str, list[str]]:
    from wif_ag_tool import config
    import json
    
    if config.VANILLA_WEAPON_DESCRIPTOR.exists():
        weapons = parse_weapons(config.VANILLA_WEAPON_DESCRIPTOR)
        try:
            config.VANILLA_WEAPONS_CACHE.parent.mkdir(parents=True, exist_ok=True)
            config.VANILLA_WEAPONS_CACHE.write_text(json.dumps(weapons, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"warn: failed to cache vanilla weapons: {e}")
        return weapons
    elif config.VANILLA_WEAPONS_CACHE.exists():
        try:
            return json.loads(config.VANILLA_WEAPONS_CACHE.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"warn: failed to load vanilla weapons cache: {e}")
    return {}
