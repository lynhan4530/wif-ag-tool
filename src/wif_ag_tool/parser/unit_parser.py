"""Parse WF_ unit descriptors from UniteDescriptor.ndf.

Uses line-by-line scanning rather than a full NDF AST — the file is 33 MB
and we only need a handful of fields from each WF_ block.
"""

from __future__ import annotations
import re
from pathlib import Path

from wif_ag_tool.models import WifUnit

# ── compiled regexes ──────────────────────────────────────────────────────────
_RE_EXPORT    = re.compile(r'^(?:\s*|\s*\)\s*)export (Descriptor_Unit_\S+) is TEntityDescriptor')
_RE_GUID      = re.compile(r'DescriptorId\s*=\s*GUID:\{([^}]+)\}')
_RE_COUNTRY   = re.compile(r"MotherCountry\s*=\s*'(\w+)'")
_RE_ATTACK    = re.compile(r'UnitAttackValue\s*=\s*(\d+)')
_RE_DEFENSE   = re.compile(r'UnitDefenseValue\s*=\s*(\d+)')
_RE_XP_BONUS  = re.compile(r'UnitBonusXpPerLevelValue\s*=\s*(\d+)')
_RE_ROLE      = re.compile(r"UnitRole\s*=\s*'(\w+)'")
_RE_TOKEN     = re.compile(r"NameToken\s*=\s*'(\w+)'")
_RE_BUTTON    = re.compile(r"ButtonTexture\s*=\s*'(Texture_Button_Unit_\w+)'")
_RE_SPECIALTY = re.compile(r"'([^']+)'")   # used inside SpecialtiesList block
_RE_HEALTH    = re.compile(r'MaxPhysicalDamages\s*=\s*(\d+)')
_RE_SUPPRESS  = re.compile(r'MaxSuppressionDamages\s*=\s*(\S+)')
_RE_SUPPLY    = re.compile(r'SupplyCapacity\s*=\s*(\d+(?:\.\d+)?)')
_RE_WEAPON    = re.compile(r'\$/GFX/Weapon/WeaponDescriptor_([\w_]+)')
_RE_COST      = re.compile(r'\(\s*\$/GFX/Resources/Resource_CommandPoints\s*,\s*(\d+)\s*\)')
_RE_ARMOR_FRONT = re.compile(r'ResistanceFront\s*=\s*TResistanceTypeRTTI\s*\(\s*Family\s*=\s*[\w_]+\s+Index\s*=\s*(\d+)\s*\)')
_RE_ARMOR_SIDES = re.compile(r'ResistanceSides\s*=\s*TResistanceTypeRTTI\s*\(\s*Family\s*=\s*[\w_]+\s+Index\s*=\s*(\d+)\s*\)')
_RE_ARMOR_REAR  = re.compile(r'ResistanceRear\s*=\s*TResistanceTypeRTTI\s*\(\s*Family\s*=\s*[\w_]+\s+Index\s*=\s*(\d+)\s*\)')
_RE_ARMOR_TOP   = re.compile(r'ResistanceTop\s*=\s*TResistanceTypeRTTI\s*\(\s*Family\s*=\s*[\w_]+\s+Index\s*=\s*(\d+)\s*\)')
_RE_SPEED       = re.compile(r'MaxSpeedInKmph\s*=\s*(\d+)')
_RE_ROAD_SPEED  = re.compile(r'DisplayRoadSpeedInKmph\s*=\s*(\d+)')
_RE_FUEL_CAP    = re.compile(r'FuelCapacity\s*=\s*(\d+)')
_RE_FUEL_MOVE   = re.compile(r'FuelMoveDuration\s*=\s*([-\d\.]+)')
_RE_OPTICS      = re.compile(r'\(\s*EOpticalStrength/Standard\s*,\s*([-\d\.]+)\s*\)')
_RE_STEALTH     = re.compile(r'UnitConcealmentBonus\s*=\s*([-\d\.]+)')
_RE_FWD_DEPLOY  = re.compile(r'DeploymentShiftGRU\s*=\s*([-\d\.]+)')


def _resolve_suppression(val_str: str) -> int:
    if 'Infanterie' in val_str:
        return 600
    if 'Helico' in val_str:
        return 800
    if 'Airplane' in val_str:
        return 1000
    if 'GroundUnit' in val_str:
        return 800
    try:
        clean = val_str.replace('~/', '').strip()
        return int(clean)
    except ValueError:
        return 800



def parse_wif_units(
    path: Path,
    nation_filter: str | None = None,
    units_csv: dict[str, str] | None = None,
    prefix: str | None = "WF_",
) -> dict[str, WifUnit]:
    """Return units from *path*, keyed by unit name (no Descriptor_Unit_ prefix).

    Args:
        path: Path to UniteDescriptor.ndf (WIF or vanilla).
        nation_filter: If set (e.g. "US"), only return units whose MotherCountry matches.
        units_csv: Optional ``{NameToken: REFTEXT}`` mapping; when provided, populates
            ``WifUnit.display_name`` for matching tokens. Defaults to ``{}``.
        prefix: Restrict to units whose name begins with this string (default ``"WF_"``).
            Pass ``None`` to include every unit in the file (vanilla mode).
    """
    csv_map = units_csv or {}
    units: dict[str, WifUnit] = {}
    text = path.read_text(encoding="utf-8", errors="replace")
    blocks = _split_into_unit_blocks(text)
    for raw_name, block in blocks:
        unit = _parse_block(raw_name, block)
        if unit is None:
            continue
        if prefix and not unit.name.startswith(prefix):
            continue
        if nation_filter and unit.nation != nation_filter:
            continue
        if unit.name_token:
            unit.display_name = csv_map.get(unit.name_token, "")
        units[unit.name] = unit
    return units


def _split_into_unit_blocks(text: str) -> list[tuple[str, str]]:
    """Split the full NDF text into (descriptor_name, block_text) pairs for WF_ units only."""
    results: list[tuple[str, str]] = []
    lines = text.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        m = _RE_EXPORT.match(lines[i])
        if m:
            full_name = m.group(1)  # Descriptor_Unit_WF_...
            # Collect lines until next top-level export or end-of-file
            start = i
            i += 1
            while i < n and not _RE_EXPORT.match(lines[i]):
                i += 1
            block = "\n".join(lines[start:i])
            results.append((full_name, block))
        else:
            i += 1
    return results


def _parse_block(full_name: str, block: str) -> WifUnit | None:
    """Extract a WifUnit from a single descriptor block. Returns None on parse failure."""
    # Strip "Descriptor_Unit_" prefix to get the plain name
    name = full_name.removeprefix("Descriptor_Unit_")

    guid_m    = _RE_GUID.search(block)
    country_m = _RE_COUNTRY.search(block)
    attack_m  = _RE_ATTACK.search(block)
    defense_m = _RE_DEFENSE.search(block)
    xp_m      = _RE_XP_BONUS.search(block)
    role_m    = _RE_ROLE.search(block)
    token_m   = _RE_TOKEN.search(block)
    button_m  = _RE_BUTTON.search(block)

    health_m   = _RE_HEALTH.search(block)
    suppress_m = _RE_SUPPRESS.search(block)
    supply_m   = _RE_SUPPLY.search(block)
    weapon_m   = _RE_WEAPON.search(block)
    cost_m = _RE_COST.search(block)
    armor_front_m = _RE_ARMOR_FRONT.search(block)
    armor_sides_m = _RE_ARMOR_SIDES.search(block)
    armor_rear_m = _RE_ARMOR_REAR.search(block)
    armor_top_m = _RE_ARMOR_TOP.search(block)
    speed_m = _RE_SPEED.search(block)
    road_speed_m = _RE_ROAD_SPEED.search(block)
    fuel_cap_m = _RE_FUEL_CAP.search(block)
    fuel_move_m = _RE_FUEL_MOVE.search(block)
    optics_m = _RE_OPTICS.search(block)
    stealth_m = _RE_STEALTH.search(block)
    fwd_m = _RE_FWD_DEPLOY.search(block)

    # GUID is required; everything else gets a sensible default
    if not guid_m:
        return None

    specialties = _parse_specialties(block)
    tag_match = re.search(r'TagSet\s*=\s*\[([^\]]*)\]', block, re.DOTALL)
    if tag_match and 'Unite_transportable' in tag_match.group(1):
        if 'transportable' not in specialties:
            specialties.append('transportable')
    nation = country_m.group(1) if country_m else _infer_nation(name)
    is_transport = 'TTransporterModuleDescriptor' in block
    is_transportable = 'TTransportableModuleDescriptor' in block

    health = int(health_m.group(1)) if health_m else 10
    max_supp = _resolve_suppression(suppress_m.group(1)) if suppress_m else 0
    supply = int(float(supply_m.group(1))) if supply_m else 0
    weapon_ref = weapon_m.group(1) if weapon_m else ""
    cost = int(cost_m.group(1)) if cost_m else 0
    armor_front = int(armor_front_m.group(1)) if armor_front_m else 0
    armor_sides = int(armor_sides_m.group(1)) if armor_sides_m else 0
    armor_rear = int(armor_rear_m.group(1)) if armor_rear_m else 0
    armor_top = int(armor_top_m.group(1)) if armor_top_m else 0
    speed = int(speed_m.group(1)) if speed_m else 0
    road_speed = int(road_speed_m.group(1)) if road_speed_m else 0
    fuel_cap = int(fuel_cap_m.group(1)) if fuel_cap_m else 0
    fuel_move = float(fuel_move_m.group(1)) if fuel_move_m else 0.0
    optics = float(optics_m.group(1)) if optics_m else 2473.0
    stealth = float(stealth_m.group(1)) if stealth_m else 1.0
    fwd_deploy = float(fwd_m.group(1)) if fwd_m else 0.0
    amphibious = ("AmphibiousVehicle" in block or
                  "TrackAmphibious" in block or
                  "WheelAmphibious" in block or
                  "'_amphibie'" in block)
    is_plane = ('TAirplane' in block or 'AirplanePosition' in block or 'AirplaneFlags' in block or 'AirplaneModule' in block)
    is_helo = ('THelicopter' in block or 'HelicopterPosition' in block or 'HeliApparence' in block or 'HelicopterMovement' in block)

    return WifUnit(
        name=name,
        guid=guid_m.group(1),
        nation=nation,
        attack=int(attack_m.group(1)) if attack_m else 0,
        defense=int(defense_m.group(1)) if defense_m else 0,
        xp_bonus=int(xp_m.group(1)) if xp_m else 1,
        role=role_m.group(1) if role_m else "unknown",
        name_token=token_m.group(1) if token_m else "",
        specialties=specialties,
        button_texture=button_m.group(1) if button_m else "",
        is_transport=is_transport,
        is_transportable=is_transportable,
        health=health,
        max_suppression=max_supp,
        supply_capacity=supply,
        weapon_descriptor_ref=weapon_ref,
        cost=cost,
        armor_front=armor_front,
        armor_sides=armor_sides,
        armor_rear=armor_rear,
        armor_top=armor_top,
        speed=speed,
        road_speed=road_speed,
        fuel_capacity=fuel_cap,
        fuel_move_duration=fuel_move,
        optics=optics,
        stealth=stealth,
        fwd_deploy=fwd_deploy,
        amphibious=amphibious,
        is_plane=is_plane,
        is_helo=is_helo,
    )


def _parse_specialties(block: str) -> list[str]:
    """Extract the SpecialtiesList entries from a block."""
    m = re.search(r'SpecialtiesList\s*=\s*\[([^\]]*)\]', block, re.DOTALL)
    if not m:
        return []
    return _RE_SPECIALTY.findall(m.group(1))


def _infer_nation(name: str) -> str:
    """Fallback: infer nation from the unit name suffix (e.g. _US, _RUS, _FR)."""
    for suffix in ("_RUS", "_US", "_FR", "_GER", "_BEL", "_NL", "_UK", "_DNR", "_SOV"):
        if name.endswith(suffix):
            return suffix.lstrip("_")
    return "UNKNOWN"


def load_wif_units(units_csv: dict[str, str] | None = None) -> dict[str, WifUnit]:
    """Load WIF units from the UniteDescriptor.ndf and BuildingDescriptors.ndf files, or fallback to the json cache."""
    from wif_ag_tool import config
    import json
    from dataclasses import asdict

    ndf_path = config.WIF_UNITE_DESCRIPTOR
    cache_path = config.UNITS_CACHE_FILE
    use_cache = cache_path.exists() and (not ndf_path.exists() or cache_path.stat().st_mtime >= ndf_path.stat().st_mtime)

    if use_cache:
        try:
            cache_data = json.loads(cache_path.read_text(encoding="utf-8"))
            if cache_data and not any("is_plane" in d for d in cache_data.values()):
                raise ValueError("Cache needs rebuild for new is_plane/is_helo fields")
            units = {name: WifUnit(**data) for name, data in cache_data.items()}
            if units_csv:
                for unit in units.values():
                    if unit.name_token:
                        unit.display_name = units_csv.get(unit.name_token, unit.display_name or "")
            return units
        except Exception as e:
            print(f"warn: failed to load WIF units cache: {e}")

    units = {}
    if ndf_path.exists():
        units = parse_wif_units(ndf_path, units_csv=units_csv, prefix=config.MOD_UNIT_PREFIX)
        building_ndf = config.WIF_ROOT / "Generated" / "Gameplay" / "Gfx" / "BuildingDescriptors.ndf"
        if building_ndf.exists():
            try:
                units.update(parse_wif_units(building_ndf, units_csv=units_csv, prefix=None))
            except Exception as e:
                print(f"warn: failed to parse WIF BuildingDescriptors.ndf: {e}")
        try:
            config.UNITS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            cache_data = {name: asdict(unit) for name, unit in units.items()}
            config.UNITS_CACHE_FILE.write_text(json.dumps(cache_data, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"warn: failed to cache WIF units: {e}")
    elif cache_path.exists():
        try:
            cache_data = json.loads(cache_path.read_text(encoding="utf-8"))
            units = {name: WifUnit(**data) for name, data in cache_data.items()}
            if units_csv:
                for unit in units.values():
                    if unit.name_token:
                        unit.display_name = units_csv.get(unit.name_token, unit.display_name or "")
        except Exception as e:
            print(f"warn: failed to load WIF units cache: {e}")
    return units


def load_vanilla_units(units_csv: dict[str, str] | None = None) -> dict[str, WifUnit]:
    """Load vanilla units from the UniteDescriptor.ndf and BuildingDescriptors.ndf files, or fallback to the json cache."""
    from wif_ag_tool import config
    import json
    from dataclasses import asdict

    ndf_path = config.VANILLA_UNITE_DESCRIPTOR
    cache_path = config.VANILLA_UNITS_CACHE
    use_cache = cache_path.exists() and (not ndf_path.exists() or cache_path.stat().st_mtime >= ndf_path.stat().st_mtime)

    if use_cache:
        try:
            cache_data = json.loads(cache_path.read_text(encoding="utf-8"))
            if cache_data and not any("is_plane" in d for d in cache_data.values()):
                raise ValueError("Cache needs rebuild for new is_plane/is_helo fields")
            units = {name: WifUnit(**data) for name, data in cache_data.items()}
            if units_csv:
                for unit in units.values():
                    if unit.name_token:
                        unit.display_name = units_csv.get(unit.name_token, unit.display_name or "")
            return units
        except Exception as e:
            print(f"warn: failed to load vanilla units cache: {e}")

    units = {}
    if ndf_path.exists():
        units = parse_wif_units(ndf_path, units_csv=units_csv, prefix=None)
        building_ndf = config.VANILLA_ROOT / "Generated" / "Gameplay" / "Gfx" / "BuildingDescriptors.ndf"
        if building_ndf.exists():
            try:
                units.update(parse_wif_units(building_ndf, units_csv=units_csv, prefix=None))
            except Exception as e:
                print(f"warn: failed to parse Vanilla BuildingDescriptors.ndf: {e}")
        try:
            config.VANILLA_UNITS_CACHE.parent.mkdir(parents=True, exist_ok=True)
            cache_data = {name: asdict(unit) for name, unit in units.items()}
            config.VANILLA_UNITS_CACHE.write_text(json.dumps(cache_data, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"warn: failed to cache vanilla units: {e}")
    elif cache_path.exists():
        try:
            cache_data = json.loads(cache_path.read_text(encoding="utf-8"))
            units = {name: WifUnit(**data) for name, data in cache_data.items()}
            if units_csv:
                for unit in units.values():
                    if unit.name_token:
                        unit.display_name = units_csv.get(unit.name_token, unit.display_name or "")
        except Exception as e:
            print(f"warn: failed to load vanilla units cache: {e}")
    return units
