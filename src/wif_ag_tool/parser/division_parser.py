"""Parse Divisions.ndf → CfgName / DivisionName token / tags per division.

Used to resolve a deck's DeckDivision reference to a friendly division label.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Division:
    cfg_name: str                                  # e.g. "RDA_10MSD_solo"
    division_name_token: str = ""                  # 10-char LOC token, e.g. "DTNMQBUQTC"
    description_token: str = ""                    # optional hint title token
    coalition: str = ""                            # "NATO" / "PACT"
    tags: list[str] = field(default_factory=list)
    emblem_texture: str = ""
    display_name: str = ""
 
 
_RE_BLOCK_HEAD = re.compile(
    r"^export\s+Descriptor_Deck_Division_(\S+)\s+is\s+TDeckDivisionDescriptor",
    re.MULTILINE,
)
_RE_CFG_NAME   = re.compile(r"CfgName\s*=\s*'([^']+)'")
_RE_DIV_NAME   = re.compile(r"DivisionName\s*=\s*'([^']+)'")
_RE_DESC_TOKEN = re.compile(r"DescriptionHintTitleToken\s*=\s*'([^']+)'")
_RE_COALITION  = re.compile(r"DivisionCoalition\s*=\s*ECoalition/(\w+)")
_RE_TAGS       = re.compile(r"DivisionTags\s*=\s*\[([^\]]*)\]", re.DOTALL)
_RE_TAG_ITEM   = re.compile(r"'([^']+)'")
_RE_EMBLEM     = re.compile(r'EmblemTexture\s*=\s*"([^"]+)"')
 
 
def parse_divisions(path: Path, units_csv: dict[str, str] | None = None) -> dict[str, Division]:
    """Return ``{CfgName: Division}`` for every block in the file."""
    csv_map = units_csv or {}
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    starts = [m.start() for m in _RE_BLOCK_HEAD.finditer(text)]
    suffixes = [m.group(1) for m in _RE_BLOCK_HEAD.finditer(text)]
    starts.append(len(text))
 
    out: dict[str, Division] = {}
    for i, suffix in enumerate(suffixes):
        block = text[starts[i]:starts[i + 1]]
        div = _parse_block(suffix, block)
        if div.division_name_token:
            div.display_name = csv_map.get(div.division_name_token, "")
        out[div.cfg_name] = div
    return out


def _parse_block(suffix: str, block: str) -> Division:
    cfg_m   = _RE_CFG_NAME.search(block)
    name_m  = _RE_DIV_NAME.search(block)
    desc_m  = _RE_DESC_TOKEN.search(block)
    coal_m  = _RE_COALITION.search(block)
    tags_m  = _RE_TAGS.search(block)
    emb_m   = _RE_EMBLEM.search(block)
    tags = _RE_TAG_ITEM.findall(tags_m.group(1)) if tags_m else []
    return Division(
        cfg_name=cfg_m.group(1) if cfg_m else suffix,
        division_name_token=name_m.group(1) if name_m else "",
        description_token=desc_m.group(1) if desc_m else "",
        coalition=coal_m.group(1) if coal_m else "",
        tags=tags,
        emblem_texture=emb_m.group(1) if emb_m else "",
    )


def load_vanilla_divisions(units_csv: dict[str, str] | None = None) -> dict[str, Division]:
    """Load vanilla divisions from Divisions.ndf or JSON cache."""
    from wif_ag_tool import config
    import json
    from dataclasses import asdict

    divisions = {}
    divisions_ndf = config.VANILLA_DIVISIONS_NDF
    wif_divisions_ndf = config.WIF_ROOT / "Generated" / "Gameplay" / "Decks" / "Divisions.ndf"

    target_path = None
    if divisions_ndf.exists():
        target_path = divisions_ndf
    elif wif_divisions_ndf.exists():
        target_path = wif_divisions_ndf

    if target_path:
        divisions = parse_divisions(target_path, units_csv=units_csv)
        try:
            config.VANILLA_DIVISIONS_CACHE.parent.mkdir(parents=True, exist_ok=True)
            cache_data = {name: asdict(d) for name, d in divisions.items()}
            config.VANILLA_DIVISIONS_CACHE.write_text(json.dumps(cache_data, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"warn: failed to cache vanilla divisions: {e}")
    elif config.VANILLA_DIVISIONS_CACHE.exists():
        try:
            cache_data = json.loads(config.VANILLA_DIVISIONS_CACHE.read_text(encoding="utf-8"))
            divisions = {name: Division(**d) for name, d in cache_data.items()}
        except Exception as e:
            print(f"warn: failed to load vanilla divisions cache: {e}")
    return divisions



__all__ = ["Division", "parse_divisions", "load_vanilla_divisions"]
