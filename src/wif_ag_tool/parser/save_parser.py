"""Parse campaign info from .sav3 filenames. The save body is binary; we read only the name."""
from __future__ import annotations
import re
from pathlib import Path

_RE_FACTION = re.compile(r'#(\w+)')
_RE_CAMPAIGN = re.compile(r'\{([^}]+)\}')


def list_campaigns(saves_dir: Path) -> list[dict]:
    """Return [{factions, campaign, mission, path}] for every .sav3 with a campaign tag.

    Saves without a ``{Campaign}`` brace (quicksaves, etc.) are skipped.
    """
    if not saves_dir.exists():
        return []
    out: list[dict] = []
    for sav in sorted(saves_dir.glob("*.sav3")):
        info = _parse_filename(sav.stem)
        if not info["campaign"]:
            continue
        info["path"] = sav
        out.append(info)
    return out


def _parse_filename(stem: str) -> dict:
    """E.g. 'Autosave - #US #SOV #medium{CENTAG - DAY 7} Highway 66' →
    {factions:['US','SOV'], campaign:'CENTAG - DAY 7', mission:'Highway 66'}."""
    factions = _RE_FACTION.findall(stem)
    # Drop difficulty tokens (medium / hard / easy etc.) — heuristic: factions are uppercase short codes
    factions = [f for f in factions if f.isupper() and len(f) <= 5]

    campaign = ""
    mission = ""
    cm = _RE_CAMPAIGN.search(stem)
    if cm:
        campaign = cm.group(1).strip()
        after = stem[cm.end():].strip()
        mission = after

    return {"factions": factions, "campaign": campaign, "mission": mission}
