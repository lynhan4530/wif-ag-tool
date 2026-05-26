"""Parse Texture_Button_Unit_* → on-disk PNG path from ButtonTexturesUnites.ndf."""
from __future__ import annotations
import re
from pathlib import Path

_RE_ENTRY = re.compile(
    r'\("(Texture_Button_Unit_\w+)"[^)]*?FileName\s*=\s*"GameData:/([^"]+)"'
)


def parse_button_textures(path: Path, wif_root: Path) -> dict[str, Path]:
    """Return {button_key: absolute Path to .png}. Missing files are still mapped (caller checks exists())."""
    text = path.read_text(encoding="utf-8", errors="replace")
    out: dict[str, Path] = {}
    for m in _RE_ENTRY.finditer(text):
        key, rel = m.group(1), m.group(2)
        out[key] = wif_root / rel.replace("/", "\\")
    return out
