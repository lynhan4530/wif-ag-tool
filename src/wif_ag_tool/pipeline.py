"""Pure export pipeline: assignments + deck state → 3 NDF files + 1 CSV.

Full-replacement model: a deck with a replica is defined *entirely* by that replica —
its DeckPackList and DeckCombatGroupList are rewritten to exactly what the replica says,
with pack indices counted from 0. A deck with no replica produces no assignments and is
left untouched. Decoupled from the CLI and Flask layers so tests can call it directly.
"""
from __future__ import annotations
import json
import os
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Any

from wif_ag_tool.models import Assignment, DeckState, WifUnit
from wif_ag_tool.parser.deck_parser import parse_deck
from wif_ag_tool.generator.pack_generator import generate_pack
from wif_ag_tool.generator.group_generator import (
    generate_grouped_combat_group,
    emission_ordered_assignments,
)
from wif_ag_tool.generator.deck_patcher import generate_deck_patch
from wif_ag_tool.generator.localisation import generate_platoons_rows
from wif_ag_tool import replicas as _replicas
from wif_ag_tool import config

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
            f"but {new_pack_refs_added} pack refs were built for DeckPackList. "
            "This would crash the game on pawn click. "
            "See NDF_REFERENCE.md §4 for the invariant."
        )


def build_export_blocks(
    assignments: list[Assignment],
    decks: dict[str, DeckState],
    units: dict[str, WifUnit],
    combat_groups: dict | None = None,
) -> tuple[list[str], list[str], dict[str, tuple[list[str], list[str]]]]:
    """Turn assignments into the export building blocks (full-replacement model).

    Returns ``(packs_blocks, groups_blocks, deck_lists)`` where:
      * *packs_blocks* — DeckPackDescriptor NDF blocks to append to StrategicPacks.ndf.
      * *groups_blocks* — TDeckCombatGroupDescriptor blocks for StrategicCombatGroups.ndf.
      * *deck_lists* — ``{deck_name: (pack_refs, group_refs)}``, the EXACT new contents of
        each replica'd deck's DeckPackList / DeckCombatGroupList (pack indices start at 0).

    Each replica group is mapped to its VANILLA combat-group name + token via
    ``resolve_cg_name`` (the campaign binds pre-placed battalions to vanilla combat-group
    names — renaming hangs the loader). *combat_groups* is the parsed vanilla
    StrategicCombatGroups map; pass ``{}`` in tests to avoid touching live game files.

    Raises ValueError if the pack-index invariant is ever violated.
    """
    if combat_groups is None:
        from wif_ag_tool.parser.combatgroup_parser import parse_combat_groups
        combat_groups = (
            parse_combat_groups(config.VANILLA_COMBAT_GROUPS)
            if config.VANILLA_COMBAT_GROUPS.exists() else {}
        )

    by_deck: dict[str, list[Assignment]] = {}
    for a in assignments:
        by_deck.setdefault(a.deck_name, []).append(a)
    for lst in by_deck.values():
        lst.sort(key=lambda a: (a.order, a.seq))

    packs_blocks: list[str] = []
    groups_blocks: list[str] = []
    deck_lists: dict[str, tuple[list[str], list[str]]] = {}
    existing_tokens: set[str] = set()
    seen_packs: set[str] = set()

    for deck_name, deck_assignments in by_deck.items():
        deck = decks[deck_name]
        # Replacement: start from an EMPTY deck so pack indices count from 0.
        running = DeckState(name=deck.name, pack_list=[], combat_group_list=[])

        groups_map: dict[str, list[Assignment]] = {}
        group_order: list[str] = []
        for a in deck_assignments:
            gname = a.group_name or "A"
            if gname not in groups_map:
                groups_map[gname] = []
                group_order.append(gname)
            groups_map[gname].append(a)

        from wif_ag_tool.generator.group_generator import resolve_all_cg_names
        cg_names_map = resolve_all_cg_names(deck_name, group_order, deck.combat_group_list)

        new_packs: list[str] = []
        new_groups: list[str] = []

        for gname in group_order:
            group_assignments = groups_map[gname]

            for a in group_assignments:
                for xp in a.xp_levels:
                    pname = a.pack_name(xp)
                    if pname not in seen_packs:
                        seen_packs.add(pname)
                        packs_blocks.append(generate_pack(a.unit_id, xp, transport_id=a.transport_id, seq=a.seq, deck_name=a.deck_name))

            # Reuse the vanilla combat-group name + token so the campaign keeps binding to
            # it; replace its content with this group's units.
            cg_name = cg_names_map[gname]
            vanilla = combat_groups.get(cg_name)
            cg_token = vanilla.token if vanilla else None
            is_hq = (gname == "HQ") or bool(vanilla and vanilla.is_hq)

            groups_blocks.append(generate_grouped_combat_group(
                gname=gname,
                deck_name=deck_name,
                assignments=group_assignments,
                deck_state=running,
                existing_tokens=existing_tokens,
                is_hq=is_hq,
                cg_name=cg_name,
                cg_token=cg_token,
            ))

            # Append DeckPackList refs in the SAME order generate_grouped_combat_group
            # assigns indices (emission order), so the (start,count) tuples and the refs
            # stay aligned slot-for-slot and the combat group is ascending/contiguous.
            # Engine reads `count` consecutive slots per tuple, so each ref appears
            # `a.count` times consecutively.
            for a in emission_ordered_assignments(group_assignments):
                for xp in a.xp_levels:
                    pack_ref = a.pack_name(xp)
                    for _ in range(a.count):
                        new_packs.append(pack_ref)
                        running.pack_list.append(pack_ref)

            new_groups.append(cg_name)
            running.combat_group_list.append(cg_name)

        # 1. Verify invariant on replica-added packs first
        _assert_pack_index_invariant(deck_name, deck_assignments, len(new_packs))

        # 2. Keep and append unmatched vanilla combat groups to avoid breaking pawn-to-group bindings
        matched_vanilla_cgs = set(cg_names_map.values())
        unmatched_vanilla_cgs = [cg for cg in deck.combat_group_list if cg not in matched_vanilla_cgs]

        for cg_name in unmatched_vanilla_cgs:
            if not cg_name.startswith("Descriptor_CombatGroup_"):
                continue
            vanilla = combat_groups.get(cg_name)
            if not vanilla:
                continue

            cg_token = vanilla.token
            is_hq = vanilla.is_hq

            from wif_ag_tool.generator.group_generator import generate_unmatched_combat_group
            groups_blocks.append(generate_unmatched_combat_group(
                cg_name=cg_name,
                cg_token=cg_token,
                is_hq=is_hq,
                smart_groups=vanilla.smart_groups,
                deck_pack_list=deck.pack_list,
                new_packs=new_packs,
                running_pack_list=running.pack_list,
            ))

            new_groups.append(cg_name)
            running.combat_group_list.append(cg_name)

        # Reorder new_groups to match the exact original order of combat groups in the deck,
        # keeping any new/extra (custom) groups appended at the end.
        vanilla_indices = {name: idx for idx, name in enumerate(deck.combat_group_list)}
        new_groups_orig = list(new_groups)
        new_groups.sort(key=lambda name: (
            0 if name in vanilla_indices else 1,
            vanilla_indices.get(name, 0) if name in vanilla_indices else new_groups_orig.index(name)
        ))
        running.combat_group_list = list(new_groups)

        deck_lists[deck_name] = (new_packs, new_groups)

    return packs_blocks, groups_blocks, deck_lists


def run_export(
    assignments: list[Assignment],
    decks: dict[str, DeckState],
    units: dict[str, WifUnit],
    output_dir: Path,
) -> dict[str, Path]:
    """Generate all 4 artifacts as sidecar files (zip-export path). Returns name → path."""
    output_dir.mkdir(parents=True, exist_ok=True)

    from wif_ag_tool.parser.combatgroup_parser import parse_combat_groups
    combat_groups = (
        parse_combat_groups(config.VANILLA_COMBAT_GROUPS)
        if config.VANILLA_COMBAT_GROUPS.exists() else {}
    )

    packs_blocks, groups_blocks, deck_lists = build_export_blocks(assignments, decks, units, combat_groups)
    deck_patches = [
        generate_deck_patch(deck_name, pack_refs, group_refs)
        for deck_name, (pack_refs, group_refs) in deck_lists.items()
    ]
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


def load_tactical_overrides() -> dict:
    if config.STATS_OVERRIDES_FILE.exists():
        try:
            return json.loads(config.STATS_OVERRIDES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"units": {}, "ammo": {}}


def export_direct(
    session: dict,
    decks_map: dict[str, DeckState],
    units: dict[str, WifUnit],
    combat_groups: dict,
    scope: str = "all",
) -> dict[str, Any]:
    """Apply replica assignments and patches directly to target mod source NDFs."""
    target_mod_dir = session.get("target_mod_dir", "").strip()
    custom_export_dir = session.get("export_dir", "").strip()

    if custom_export_dir:
        export_path = Path(custom_export_dir)
    elif target_mod_dir:
        export_path = Path(target_mod_dir) / "GameData"
    else:
        export_path = config.TOOL_ROOT / "output"

    export_path.mkdir(parents=True, exist_ok=True)

    if target_mod_dir:
        mod_name = Path(target_mod_dir).name
    else:
        mod_name = "CRM_ArmyGeneral"

    scoped = None
    if scope == "session":
        from wif_ag_tool import session as session_mod
        scoped = session_mod.scope_decks(session.get("nation_scope") or [], decks_map.keys())

    store = _replicas.load_replicas()
    assignments = _replicas.replicas_to_assignments(store, scope_decks=scoped)

    if not assignments:
        raise ValueError("No saved replicas in scope to export. Create a replica deck first.")

    decks_dir = export_path / "Generated" / "Gameplay" / "Decks"
    base_decks_ndf  = decks_dir / "StrategicDecks.ndf"
    base_packs_ndf  = decks_dir / "StrategicPacks.ndf"
    base_groups_ndf = decks_dir / "StrategicCombatGroups.ndf"
    base_csv        = export_path / "Localisation" / mod_name / "PLATOONS.csv"
    base_units_ndf  = export_path / "Generated" / "Gameplay" / "Gfx" / "UniteDescriptor.ndf"
    base_ammo_ndf   = export_path / "Generated" / "Gameplay" / "Gfx" / "Ammunition.ndf"
    base_ammo_missiles_ndf = export_path / "Generated" / "Gameplay" / "Gfx" / "AmmunitionMissiles.ndf"
    
    direct_paths = {
        "summary": decks_dir / "StrategicDecks_patch_summary.txt",
        "csv": base_csv
    }

    for p in direct_paths.values():
        p.parent.mkdir(parents=True, exist_ok=True)
    decks_dir.mkdir(parents=True, exist_ok=True)

    # Clean out stale sidecars
    for stale_name in (
        "StrategicPacks_additions.ndf",
        "StrategicCombatGroups_additions.ndf",
        "StrategicDecks_patch.ndf",
    ):
        stale = decks_dir / stale_name
        if stale.exists():
            try:
                stale.unlink()
            except Exception:
                pass

    base_files = [base_decks_ndf, base_packs_ndf, base_groups_ndf, base_csv]
    if base_units_ndf.exists():
        base_files.append(base_units_ndf)
    if base_ammo_ndf.exists():
        base_files.append(base_ammo_ndf)
    if base_ammo_missiles_ndf.exists():
        base_files.append(base_ammo_missiles_ndf)

    # Backup & Restore canvases
    for base in base_files:
        pristine = base.with_suffix(base.suffix + ".orig")
        
        if "PYTEST_CURRENT_TEST" not in os.environ:
            clean_source = None
            if base.name == "StrategicDecks.ndf":
                clean_source = config.VANILLA_STRATEGIC_DECKS
            elif base.name == "StrategicPacks.ndf":
                clean_source = config.VANILLA_STRATEGIC_PACKS
            elif base.name == "StrategicCombatGroups.ndf":
                clean_source = config.VANILLA_COMBAT_GROUPS

            pristine_bytes = None
            if clean_source and clean_source.exists():
                try:
                    pristine_bytes = clean_source.read_bytes()
                except Exception:
                    pass

            if pristine_bytes is None and target_mod_dir:
                base_zip_path = Path(target_mod_dir) / "base.zip"
                if base_zip_path.exists():
                    try:
                        with zipfile.ZipFile(base_zip_path, 'r') as z:
                            zip_internal_path = f"GameData/Generated/Gameplay/Decks/{base.name}"
                            if base.name == "PLATOONS.csv":
                                zip_internal_path = f"Localisation/{mod_name}/PLATOONS.csv"
                            pristine_bytes = z.read(zip_internal_path)
                    except Exception:
                        pass

            if pristine_bytes is not None:
                need_recreate = False
                if not pristine.exists():
                    need_recreate = True
                else:
                    try:
                        if pristine.read_bytes() != pristine_bytes:
                            need_recreate = True
                    except Exception:
                        need_recreate = True
                
                if need_recreate:
                    pristine.write_bytes(pristine_bytes)

        if base.exists() and not pristine.exists():
            pristine.write_bytes(base.read_bytes())
        elif pristine.exists():
            base.write_bytes(pristine.read_bytes())

    # Generate blocks and apply patches
    packs_blocks, groups_blocks, deck_lists = build_export_blocks(
        assignments, decks_map, units, combat_groups)

    deck_patches = []
    from wif_ag_tool.generator.deck_patcher import replace_deck_lists, apply_combat_group_patches
    for deck_name, (pack_refs, group_refs) in deck_lists.items():
        try:
            replace_deck_lists(base_decks_ndf, deck_name, pack_refs, group_refs)
        except KeyError:
            pass
        deck_patches.append(generate_deck_patch(deck_name, pack_refs, group_refs))

    csv_text = generate_platoons_rows(assignments, units, decks=decks_map, combat_groups=combat_groups)

    if packs_blocks:
        with base_packs_ndf.open("a", encoding="utf-8") as f:
            f.write(f"\n\n// === {config.MOD_TAG} additions ===\n\n")
            f.write("\n\n".join(packs_blocks))
            f.write("\n")
    if groups_blocks:
        apply_combat_group_patches(base_groups_ndf, groups_blocks)

    direct_paths["summary"].write_text("\n\n".join(deck_patches) + "\n", encoding="utf-8")

    new_rows = csv_text.split("\n", 1)[1] if "\n" in csv_text else ""
    existing_csv = base_csv.read_text(encoding="utf-8") if base_csv.exists() else ""
    if existing_csv.strip():
        merged = existing_csv if existing_csv.endswith("\n") else existing_csv + "\n"
        if new_rows.strip():
            merged += new_rows if new_rows.endswith("\n") else new_rows + "\n"
        base_csv.write_text(merged, encoding="utf-8")
    else:
        base_csv.write_text(csv_text, encoding="utf-8")

    # Merge tactical unit overrides and strategic attack/defense overrides
    tactical_overrides = load_tactical_overrides()
    unit_overrides = {}
    
    for uid, fields in tactical_overrides.get("units", {}).items():
        unit_overrides[uid] = dict(fields)
        
    for a in assignments:
        if a.attack_override is not None or a.defense_override is not None:
            if a.unit_id not in unit_overrides:
                unit_overrides[a.unit_id] = {}
            if isinstance(unit_overrides[a.unit_id], dict):
                if a.attack_override is not None:
                    unit_overrides[a.unit_id]["attack_override"] = a.attack_override
                if a.defense_override is not None:
                    unit_overrides[a.unit_id]["defense_override"] = a.defense_override
                    
    if base_units_ndf.exists() and unit_overrides:
        from wif_ag_tool.generator.unit_patcher import patch_unit_stats
        patch_unit_stats(base_units_ndf, unit_overrides)
        
    ammo_overrides = tactical_overrides.get("ammo", {})
    if ammo_overrides:
        from wif_ag_tool.generator.ammo_patcher import patch_ammo_stats
        if base_ammo_ndf.exists():
            patch_ammo_stats(base_ammo_ndf, ammo_overrides)
        if base_ammo_missiles_ndf.exists():
            patch_ammo_stats(base_ammo_missiles_ndf, ammo_overrides)

    return {
        "ok": True,
        "message": f"Successfully exported files directly to {export_path.resolve()}",
        "paths": {k: str(v.resolve()) for k, v in direct_paths.items()}
    }


__all__ = [
    "load_assignments",
    "save_assignments",
    "build_export_blocks",
    "run_export",
    "export_from_replicas",
    "migrate_legacy_assignments",
    "refresh_deck_cache",
    "load_deck_cache",
    "load_tactical_overrides",
    "export_direct",
    "PACKS_OUT",
    "GROUPS_OUT",
    "DECKS_OUT",
    "CSV_OUT",
]
