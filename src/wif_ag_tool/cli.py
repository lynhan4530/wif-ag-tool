"""CLI entry: refresh | export | serve."""
from __future__ import annotations
import sys
from pathlib import Path

from wif_ag_tool import config
from wif_ag_tool.parser.deck_parser import list_decks
from wif_ag_tool.parser.unit_parser import parse_wif_units
from wif_ag_tool.pipeline import (
    refresh_deck_cache,
    load_deck_cache,
    export_from_replicas,
    migrate_legacy_assignments,
)
from wif_ag_tool import replicas as replicas_mod

USAGE = """\
usage: py -m wif_ag_tool <command>

commands:
    refresh   re-parse vanilla StrategicDecks.ndf → .deck_cache.json
    export    read assignments.json → write NDF patch files to ./output/
    serve     start Flask dev server on localhost:5000
"""


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print(USAGE, file=sys.stderr)
        return 1
    cmd = argv[0]
    if cmd == "refresh":
        return cmd_refresh()
    if cmd == "export":
        return cmd_export()
    if cmd == "serve":
        return cmd_serve()
    print(f"unknown command: {cmd}\n", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 1


def cmd_refresh() -> int:
    decks = list_decks(config.VANILLA_STRATEGIC_DECKS)
    state = refresh_deck_cache(config.VANILLA_STRATEGIC_DECKS, decks, config.CACHE_FILE)
    print(f"refreshed {len(state)} decks -> {config.CACHE_FILE}")
    return 0


def cmd_export() -> int:
    migrate_legacy_assignments()
    store = replicas_mod.load_replicas()
    if not any(e.get("saved") for e in store.values()):
        print("no saved replicas to export")
        return 0
    decks = load_deck_cache(config.CACHE_FILE)
    if not decks:
        print("no deck cache — run `refresh` first", file=sys.stderr)
        return 2
    units = parse_wif_units(config.WIF_UNITE_DESCRIPTOR)
    output_dir = config.TOOL_ROOT / "output"
    paths = export_from_replicas(decks, units, output_dir, replicas=store)
    for label, path in paths.items():
        print(f"wrote {label:8s} -> {path}")
    return 0


def cmd_serve() -> int:
    from wif_ag_tool.web.app import create_app
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
