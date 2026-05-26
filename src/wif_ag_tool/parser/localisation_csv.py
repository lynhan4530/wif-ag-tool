"""Load WARNO-style localisation CSVs: ``"TOKEN";"REFTEXT"`` semicolon-quoted pairs.

WIF + vanilla ship UNITS.csv / DIVISIONS.csv in this format. We use the result to
resolve ``NameToken`` (e.g. ``"WFM1ASV2"``) → human-readable display strings.
"""
from __future__ import annotations
import csv
from pathlib import Path


def load_units_csv(path: Path) -> dict[str, str]:
    """Return ``{TOKEN: REFTEXT}`` for the CSV at *path*. Empty dict if file missing."""
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    reader = csv.reader(text.splitlines(), delimiter=";", quotechar='"')
    for row in reader:
        if len(row) < 2:
            continue
        token = row[0].strip()
        if not token or token.upper() == "TOKEN":
            continue
        out[token] = row[1].strip()
    return out


__all__ = ["load_units_csv"]
