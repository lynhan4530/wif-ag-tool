"""Parse DeckPackDescriptor entries from StrategicPacks.ndf."""
from __future__ import annotations
import re
from pathlib import Path

from wif_ag_tool.models import StrategicPack

_RE_PACK_HEADER = re.compile(r'^(Descriptor_StrategicPack_\S+) is DeckPackDescriptor')
_RE_XP = re.compile(r'^\s*Xp\s*=\s*(\d+)')
_RE_UNIT = re.compile(r'^\s*Unit\s*=\s*(\$/\S+)')
_RE_TRANSPORT = re.compile(r'^\s*Transport\s*=\s*(\$/\S+)')


def parse_strategic_packs(path: Path) -> dict[str, StrategicPack]:
    """Return all DeckPackDescriptor entries keyed by descriptor name."""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    packs: dict[str, StrategicPack] = {}

    i, n = 0, len(lines)
    while i < n:
        m = _RE_PACK_HEADER.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1)
        start = i
        i += 1
        while i < n and not _RE_PACK_HEADER.match(lines[i]):
            i += 1
        pack = _parse_block(name, lines[start:i])
        if pack:
            packs[name] = pack
    return packs


def _parse_block(name: str, block_lines: list[str]) -> StrategicPack | None:
    xp: int | None = None
    unit: str | None = None
    transport: str | None = None
    for line in block_lines:
        if (m := _RE_XP.match(line)):
            xp = int(m.group(1))
        elif (m := _RE_UNIT.match(line)):
            unit = m.group(1).rstrip(",")
        elif (m := _RE_TRANSPORT.match(line)):
            transport = m.group(1).rstrip(",")
    if unit is None:
        return None
    return StrategicPack(name=name, unit=unit, xp=xp, transport=transport)


def load_vanilla_packs() -> dict[str, StrategicPack]:
    """Load vanilla strategic packs from StrategicPacks.ndf or JSON cache."""
    from wif_ag_tool import config
    import json
    from dataclasses import asdict

    packs = {}
    if config.VANILLA_STRATEGIC_PACKS.exists():
        packs = parse_strategic_packs(config.VANILLA_STRATEGIC_PACKS)
        try:
            config.VANILLA_PACKS_CACHE.parent.mkdir(parents=True, exist_ok=True)
            cache_data = {name: asdict(p) for name, p in packs.items()}
            config.VANILLA_PACKS_CACHE.write_text(json.dumps(cache_data, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"warn: failed to cache vanilla packs: {e}")
    elif config.VANILLA_PACKS_CACHE.exists():
        try:
            cache_data = json.loads(config.VANILLA_PACKS_CACHE.read_text(encoding="utf-8"))
            packs = {name: StrategicPack(**p) for name, p in cache_data.items()}
        except Exception as e:
            print(f"warn: failed to load vanilla packs cache: {e}")
    return packs
