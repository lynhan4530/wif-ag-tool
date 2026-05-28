"""Pure export pipeline: assignments + deck state → 3 NDF files + 1 CSV.

Decoupled from the CLI and the Flask layer so integration tests can call it directly.
"""
from __future__ import annotations
import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from wif_ag_tool.models import Assignment, DeckState, WifUnit
from wif_ag_tool.parser.unit_parser import parse_wif_units
from wif_ag_tool.parser.deck_parser import parse_deck
from wif_ag_tool.generator.pack_generator import generate_packs_for_assignment
from wif_ag_tool.generator.group_generator import generate_combat_group, generate_grouped_combat_group
from wif_ag_tool.generator.deck_patcher import generate_deck_patch
from wif_ag_tool.generator.localisation import generate_platoons_rows
from wif_ag_tool import replicas as _replicas

# Output filenames inside the user-supplied output dir
PACKS_OUT = "StrategicPacks_additions.ndf"
GROUPS_OUT = "StrategicCombatGroups_additions.ndf"
DECKS_OUT = "StrategicDecks_patch.ndf"
CSV_OUT = "PLATOONS_additions.csv"


def load_assignments(assignments_path: Path) -> list[Assignment]:
    raw = json.loads(assignments_path.read_text(encoding="utf-8") or "{}")
    # Accept either {"deck": [Assignment...]} or {"assignments": [...]} flat form
    if isinstance(raw, list):
        items = raw
    elif "assignments" in raw:
        items = raw["assignments"]
    else:
        items = []
        for deck_name, lst in raw.items():
            for a in lst:
                a = dict(a)
                a.setdefault("deck_name", deck_name)
                items.append(a)
    return [Assignment(**a) for a in items]


def save_assignments(assignments_path: Path, assignments: list[Assignment]) -> None:
    payload = {"assignments": [asdict(a) for a in assignments]}
    assignments_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _assert_pack_index_invariant(
    deck_name: str,
    assignments: list[Assignment],
    new_pack_refs_added: int,
) -> None:
    """Defense-in-depth check that the (start_index, count) tuples we emit match the
    DeckPackList growth slot-for-slot.

    Each assignment consumes `len(xp_levels) * count` consecutive DeckPackList slots
    (one per XP level, each duplicated `count` times). If those two numbers ever drift
    apart, the SmartGroup tuples will read out-of-bounds at runtime and the campaign
    pawn-click UI crashes. Raise loudly here so the regression never reaches the disk.
    """
    expected = sum(len(a.xp_levels) * a.count for a in assignments)
    if expected != new_pack_refs_added:
        raise ValueError(
            f"Pack-index invariant violated for {deck_name}: "
            f"SmartGroup tuples sum to {expected} consecutive slots "
            f"but {new_pack_refs_added} pack refs were appended to DeckPackList. "
            "This would crash the game on pawn click. "
            "See NDF_REFERENCE.md §4 for the invariant."
        )


def run_export(
    assignments: list[Assignment],
    decks: dict[str, DeckState],
    units: dict[str, WifUnit],
    output_dir: Path,
) -> dict[str, Path]:
    """Generate all 4 artifacts. Returns mapping of artifact-name → written path."""
    output_dir.mkdir(parents=True, exist_ok=True)

    from wif_ag_tool.parser.combatgroup_parser import parse_combat_groups
    from wif_ag_tool import config
    combat_groups = {}
    if config.VANILLA_COMBAT_GROUPS.exists():
        try:
            combat_groups = parse_combat_groups(config.VANILLA_COMBAT_GROUPS)
        except Exception:
            pass

    # Group assignments by deck so indices accumulate correctly per deck.
    # Within a deck, sort by the explicit `order` field (drag-reorder persistence)
    # then by sequence so duplicates stay grouped.
    by_deck: dict[str, list[Assignment]] = {}
    for a in assignments:
        by_deck.setdefault(a.deck_name, []).append(a)
    for lst in by_deck.values():
        lst.sort(key=lambda a: (a.order, a.seq))

    packs_blocks: list[str] = []
    groups_blocks: list[str] = []
    deck_patches: list[str] = []
    existing_tokens: set[str] = set()

    for deck_name, deck_assignments in by_deck.items():
        deck = decks[deck_name]
        # Track an evolving DeckState so each new assignment's indices come after the previous'
        running = DeckState(
            name=deck.name,
            pack_list=list(deck.pack_list),
            combat_group_list=list(deck.combat_group_list),
        )
        
        # Group deck assignments by group_name while keeping order
        groups_map: dict[str, list[Assignment]] = {}
        group_order: list[str] = []
        for a in deck_assignments:
            gname = a.group_name or "A"
            if gname not in groups_map:
                groups_map[gname] = []
                group_order.append(gname)
            groups_map[gname].append(a)

        new_packs: list[str] = []
        new_groups: list[str] = []

        for gname in group_order:
            group_assignments = groups_map[gname]
            
            # Generate packs for all assignments in this group
            for a in group_assignments:
                packs_blocks.append(generate_packs_for_assignment(a, transport_id=a.transport_id))
                
            from wif_ag_tool.generator.group_generator import resolve_cg_name
            cg_name = resolve_cg_name(deck_name, gname, deck.combat_group_list)
            vanilla_token = None
            is_hq = (gname == "HQ")
            vanilla_smart_groups = None
            if cg_name in combat_groups:
                vanilla_token = combat_groups[cg_name].token
                is_hq = combat_groups[cg_name].is_hq
                vanilla_smart_groups = combat_groups[cg_name].smart_groups

            # Generate the single combat group for this group
            combat_group_block = generate_grouped_combat_group(
                gname=gname,
                deck_name=deck_name,
                assignments=group_assignments,
                deck_state=running,
                existing_tokens=existing_tokens,
                vanilla_token=vanilla_token,
                is_hq=is_hq,
                vanilla_smart_groups=vanilla_smart_groups,
            )
            groups_blocks.append(combat_group_block)
            
            # Append packs to running deck and new_packs list.
            # The campaign engine reads `count` consecutive entries per SmartGroup
            # tuple, so each pack ref must appear `a.count` times in DeckPackList.
            for a in group_assignments:
                for xp in a.xp_levels:
                    pack_ref = a.pack_name(xp)
                    for _ in range(a.count):
                        new_packs.append(pack_ref)
                        running.pack_list.append(pack_ref)
                    
            new_groups.append(cg_name)
            running.combat_group_list.append(cg_name)

        vanilla_groups = set(deck.combat_group_list)
        groups_to_append = [g for g in new_groups if g not in vanilla_groups]
        _assert_pack_index_invariant(deck_name, deck_assignments, len(new_packs))
        deck_patches.append(generate_deck_patch(deck_name, new_packs, groups_to_append))

    csv_text = generate_platoons_rows(assignments, units, decks=decks, combat_groups=combat_groups)

    paths = {
        "packs": output_dir / PACKS_OUT,
        "groups": output_dir / GROUPS_OUT,
        "decks": output_dir / DECKS_OUT,
        "csv": output_dir / CSV_OUT,
    }
    paths["packs"].write_text("\n\n".join(packs_blocks) + "\n", encoding="utf-8")
    paths["groups"].write_text("\n\n".join(groups_blocks) + "\n", encoding="utf-8")
    paths["decks"].write_text("\n\n".join(deck_patches) + "\n", encoding="utf-8")
    paths["csv"].write_text(csv_text, encoding="utf-8")
    return paths


def refresh_deck_cache(
    strategic_decks_path: Path,
    deck_names: list[str],
    cache_path: Path,
) -> dict[str, DeckState]:
    """Re-parse the live StrategicDecks.ndf and persist a cache of deck states."""
    decks: dict[str, DeckState] = {}
    for name in deck_names:
        decks[name] = parse_deck(strategic_decks_path, name)
    cache_payload = {
        name: {
            "name": d.name,
            "pack_list": d.pack_list,
            "combat_group_list": d.combat_group_list,
            "next_index": d.next_index,
            "division_ref": d.division_ref,
            "superior_ref": d.superior_ref,
        }
        for name, d in decks.items()
    }
    cache_path.write_text(json.dumps(cache_payload, indent=2), encoding="utf-8")
    return decks


def load_deck_cache(cache_path: Path) -> dict[str, DeckState]:
    if not cache_path.exists():
        return {}
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    return {
        name: DeckState(
            name=d["name"],
            pack_list=d["pack_list"],
            combat_group_list=d["combat_group_list"],
            division_ref=d.get("division_ref", ""),
            superior_ref=d.get("superior_ref", ""),
        )
        for name, d in payload.items()
    }


def export_from_replicas(
    decks: dict[str, DeckState],
    units: dict[str, WifUnit],
    output_dir: Path,
    *,
    scope_decks: Iterable[str] | None = None,
    replicas: dict | None = None,
) -> dict[str, Path]:
    """Build the export from the global replicas store.

    *scope_decks* limits which replicas are flattened into the export. ``None`` =
    export all saved replicas.
    """
    assignments = _replicas.replicas_to_assignments(replicas, scope_decks=scope_decks)
    return run_export(assignments, decks, units, output_dir)


def migrate_legacy_assignments(
    legacy_path: Path | None = None,
    replicas_path: Path | None = None,
) -> int:
    """One-shot migration: legacy ``assignments.json`` → ``wif_replicas.json``.

    Runs at most once. Returns the number of replicas written. After a successful
    migration the legacy file is renamed to ``<path>.migrated`` so this is idempotent.
    """
    from wif_ag_tool import config
    legacy = legacy_path or config.ASSIGNMENTS_FILE
    if not legacy.exists():
        return 0
    target = replicas_path or config.REPLICAS_FILE
    if target.exists():
        # Replicas already populated — refuse to overwrite. Move legacy aside.
        legacy.rename(legacy.with_suffix(legacy.suffix + ".migrated"))
        return 0

    assignments = load_assignments(legacy)
    by_deck: dict[str, list[dict]] = {}
    for a in assignments:
        for xp in a.xp_levels or [1]:
            by_deck.setdefault(a.deck_name, []).append({
                "unit_id": a.unit_id,
                "xp": xp,
                "count": a.count,
                "attack_override": a.attack_override,
                "defense_override": a.defense_override,
            })
    written = 0
    for deck_name, rows in by_deck.items():
        if rows:
            _replicas.save_replica(deck_name, rows, path=target)
            written += 1
    legacy.rename(legacy.with_suffix(legacy.suffix + ".migrated"))
    return written


__all__ = [
    "load_assignments",
    "save_assignments",
    "run_export",
    "export_from_replicas",
    "migrate_legacy_assignments",
    "refresh_deck_cache",
    "load_deck_cache",
    "PACKS_OUT",
    "GROUPS_OUT",
    "DECKS_OUT",
    "CSV_OUT",
]
