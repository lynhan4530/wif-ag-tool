#!/usr/bin/env python3
r"""
AG minimal-deck experiment — standalone, reversible. Does NOT touch wif_ag_tool source.

WHY THIS EXISTS
---------------
Before committing to a "full replacement" export rewrite (where a deck's replica
fully defines the deck and you can DELETE combat groups for balance), we need to
know one thing the NDF compiler can't tell us: does WARNO Army General actually
accept a drastically reduced deck at runtime, or does the campaign assume some
minimum structure (an HQ, a minimum pack count, etc.)?

WHAT IT DOES
------------
Minimizes ONE deck by trimming its DeckCombatGroupList down to the first N combat
groups. It LEAVES DeckPackList completely untouched, so every combat group's
(start_index, count) tuple still points at valid slots — no re-indexing, no risk of
the pawn-click out-of-bounds crash. The only thing that changes is how many combat
groups are recruitable in that one deck.

This edits StrategicDecks.ndf inside an ALREADY-BUILT mod's Decks folder, after
backing the file up to <file>.pretest_backup. It does not run any part of the tool's
export pipeline, so it is unaffected by any in-progress code changes.

THE IN-GAME CHECK
-----------------
After --apply:
  1. Run GenerateMod.bat in the mod folder (let it finish; ignore the PAUSE).
  2. Launch the AG campaign, open the trimmed deck.
  3. Click the pawn / open recruitment. Confirm:
       - the deck opens without crashing,
       - you can recruit from the one remaining combat group,
       - you can start and resolve a battle.
If all three hold, deleting combat groups is safe -> full replacement is viable.
If it crashes or the deck is unusable, we learn the real constraint and can guard
for it in the export. Then run --restore to undo.

USAGE (PowerShell)
------------------
  # 1. List decks + how many combat groups / packs each has
  py experiments/ag_minimal_deck_test.py --decks-dir "G:\...\GameData\Generated\Gameplay\Decks" --list

  # 2. Dry-run: show what trimming a deck to 1 combat group would change
  py experiments/ag_minimal_deck_test.py --decks-dir "...\Decks" --deck Descriptor_Deck_pion_US_11ACR_4 --keep 1

  # 3. Apply it (backs up StrategicDecks.ndf first)
  py experiments/ag_minimal_deck_test.py --decks-dir "...\Decks" --deck Descriptor_Deck_pion_US_11ACR_4 --keep 1 --apply

  # 4. Undo
  py experiments/ag_minimal_deck_test.py --decks-dir "...\Decks" --restore
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BACKUP_SUFFIX = ".pretest_backup"

_RE_DECK_HEAD = re.compile(r"^export (Descriptor_Deck_pion_\S+) is TDeckDescriptor")
_RE_CG_REF = re.compile(r"~/(Descriptor_CombatGroup_\S+?),?\s*$")
_RE_PACK_REF = re.compile(r"~/(Descriptor_StrategicPack_\S+?),?\s*$")


# ── block / list location (self-contained; no wif_ag_tool import) ──────────────

def _find_deck_block(lines: list[str], deck_name: str) -> tuple[int, int]:
    header = f"export {deck_name} is TDeckDescriptor"
    start = None
    for i, line in enumerate(lines):
        if line.startswith(header):
            start = i
            break
    if start is None:
        raise KeyError(f"deck not found: {deck_name}")
    return start, _find_block_end(lines, start)


def _find_block_end(lines: list[str], start: int) -> int:
    """Index just past the closing ')' of the descriptor block (paren-depth walk)."""
    depth = 0
    seen_open = False
    for i in range(start, len(lines)):
        for ch in lines[i]:
            if ch == "(":
                depth += 1
                seen_open = True
            elif ch == ")":
                depth -= 1
                if seen_open and depth == 0:
                    return i + 1
    return len(lines)


def _find_list_region(lines: list[str], start: int, end: int, list_name: str) -> tuple[int, int, int]:
    """Return (header_idx, open_bracket_idx, close_bracket_idx) for *list_name*."""
    header_idx = None
    for i in range(start, end):
        s = lines[i].strip()
        if s.startswith(list_name) and "=" in s:
            header_idx = i
            break
    if header_idx is None:
        raise KeyError(f"{list_name} not found in deck block")

    depth = 0
    open_idx = None
    close_idx = None
    for i in range(header_idx, end):
        for ch in lines[i]:
            if ch == "[":
                depth += 1
                if open_idx is None:
                    open_idx = i
            elif ch == "]":
                depth -= 1
                if open_idx is not None and depth == 0:
                    close_idx = i
                    break
        if close_idx is not None:
            break
    if open_idx is None or close_idx is None:
        raise ValueError(f"could not bound {list_name} brackets")
    return header_idx, open_idx, close_idx


def _refs_in_region(lines: list[str], open_idx: int, close_idx: int, pattern: re.Pattern) -> list[tuple[int, str]]:
    """(line_index, descriptor_name) for every ref line strictly inside the brackets."""
    out: list[tuple[int, str]] = []
    for i in range(open_idx + 1, close_idx):
        m = pattern.search(lines[i].strip())
        if m:
            out.append((i, m.group(1)))
    return out


# ── operations ─────────────────────────────────────────────────────────────────

def cmd_list(decks_path: Path, nation: str | None) -> int:
    lines = decks_path.read_text(encoding="utf-8", errors="replace").splitlines()
    deck_starts = [(i, m.group(1)) for i, line in enumerate(lines)
                   if (m := _RE_DECK_HEAD.match(line))]
    if not deck_starts:
        print("No Descriptor_Deck_pion_* decks found in", decks_path)
        return 1

    print(f"{'COMBAT GROUPS':>13}  {'PACKS':>6}  DECK")
    print("-" * 80)
    shown = 0
    for idx, (start, name) in enumerate(deck_starts):
        if nation:
            parts = name.split("_")
            if len(parts) < 4 or parts[3] != nation:
                continue
        end = _find_block_end(lines, start)
        try:
            _, cg_open, cg_close = _find_list_region(lines, start, end, "DeckCombatGroupList")
            cg_count = len(_refs_in_region(lines, cg_open, cg_close, _RE_CG_REF))
        except (KeyError, ValueError):
            cg_count = -1
        try:
            _, pk_open, pk_close = _find_list_region(lines, start, end, "DeckPackList")
            pk_count = len(_refs_in_region(lines, pk_open, pk_close, _RE_PACK_REF))
        except (KeyError, ValueError):
            pk_count = -1
        print(f"{cg_count:>13}  {pk_count:>6}  {name}")
        shown += 1
    print("-" * 80)
    print(f"{shown} deck(s) shown.")
    print("\nPick a deck with several combat groups, then trim it with --deck <NAME> --keep 1.")
    return 0


def cmd_trim(decks_path: Path, deck_name: str, keep: int, apply: bool, force: bool) -> int:
    if keep < 1:
        print("ERROR: --keep must be >= 1 (a deck with zero combat groups is not a useful test).")
        return 2

    backup = decks_path.with_name(decks_path.name + BACKUP_SUFFIX)
    if apply and backup.exists() and not force:
        print(f"ERROR: a backup already exists at:\n  {backup}")
        print("That means StrategicDecks.ndf may already be trimmed. Run --restore first,")
        print("or pass --force to overwrite the backup with the current (possibly trimmed) file.")
        return 2

    lines = decks_path.read_text(encoding="utf-8", errors="replace").splitlines()
    start, end = _find_deck_block(lines, deck_name)
    _, cg_open, cg_close = _find_list_region(lines, start, end, "DeckCombatGroupList")
    cg_refs = _refs_in_region(lines, cg_open, cg_close, _RE_CG_REF)

    if not cg_refs:
        print(f"ERROR: {deck_name} has no combat group refs to trim.")
        return 2
    if keep >= len(cg_refs):
        print(f"Nothing to do: deck has {len(cg_refs)} combat group(s); --keep {keep} keeps them all.")
        return 0

    kept = cg_refs[:keep]
    dropped = cg_refs[keep:]

    print(f"Deck: {deck_name}")
    print(f"Combat groups: {len(cg_refs)} total -> keeping {len(kept)}, dropping {len(dropped)}")
    print("\n  KEEP:")
    for _, name in kept:
        print(f"    + {name}")
    print("\n  DROP:")
    for _, name in dropped:
        print(f"    - {name}")
    print("\nDeckPackList is left untouched, so all (start_index,count) tuples stay valid.")

    if not apply:
        print("\n[dry-run] No files changed. Re-run with --apply to write (and back up first).")
        return 0

    drop_line_idxs = {i for i, _ in dropped}
    new_lines = [ln for i, ln in enumerate(lines) if i not in drop_line_idxs]

    backup.write_text("\n".join(lines) + "\n", encoding="utf-8")
    decks_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"\n[applied] Backed up original to:\n  {backup}")
    print(f"[applied] Wrote trimmed deck to:\n  {decks_path}")
    print("\nNext: run GenerateMod.bat, load the AG campaign, open this deck, recruit, start a battle.")
    print("When done testing, undo with:  --restore")
    return 0


def cmd_restore(decks_path: Path) -> int:
    backup = decks_path.with_name(decks_path.name + BACKUP_SUFFIX)
    if not backup.exists():
        print(f"No backup found at {backup} — nothing to restore.")
        return 1
    decks_path.write_bytes(backup.read_bytes())
    backup.unlink()
    print(f"Restored {decks_path.name} from backup and removed the backup file.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="AG minimal-deck experiment (standalone, reversible).")
    ap.add_argument("--decks-dir", required=True,
                    help=r"Path to ...\GameData\Generated\Gameplay\Decks (must contain StrategicDecks.ndf)")
    ap.add_argument("--list", action="store_true", help="List decks with combat-group / pack counts.")
    ap.add_argument("--nation", default=None, help="Filter --list by nation code (US, SOV, FR, RFA, ...).")
    ap.add_argument("--deck", default=None, help="Deck descriptor name to trim.")
    ap.add_argument("--keep", type=int, default=1, help="How many combat groups to keep (default 1).")
    ap.add_argument("--apply", action="store_true", help="Actually write the change (default is dry-run).")
    ap.add_argument("--force", action="store_true", help="Overwrite an existing backup (use with care).")
    ap.add_argument("--restore", action="store_true", help="Restore StrategicDecks.ndf from backup and exit.")
    args = ap.parse_args(argv)

    decks_dir = Path(args.decks_dir)
    decks_path = decks_dir / "StrategicDecks.ndf"
    if not decks_path.exists():
        print(f"ERROR: StrategicDecks.ndf not found at {decks_path}")
        return 2

    if args.restore:
        return cmd_restore(decks_path)
    if args.list:
        return cmd_list(decks_path, args.nation)
    if args.deck:
        return cmd_trim(decks_path, args.deck, args.keep, args.apply, args.force)

    print("Nothing to do. Use --list, --deck <NAME> [--apply], or --restore. See --help.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
