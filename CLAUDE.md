# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# WIF AG Tool — Developer Reference Guide

A Python web tool that lets you interactively assign World in Flames (WIF) modern units to WARNO Army General campaign decks, then exports the NDF patch files needed to build the mod.

## Core Commands

- **Run Dev Server**: `python -m wif_ag_tool serve` (Starts Flask server on `http://localhost:5000`)
- **Run Tests**: `pytest tests/ -v`
- **Run a Single Test**: `pytest tests/test_web_api.py::test_name -v` (or `pytest -k "substring" -v` to filter by name)
- **Re-parse Decks**: `python -m wif_ag_tool refresh` (Updates `.deck_cache.json` from vanilla NDF files)
- **Export NDF Mod Files**: `python -m wif_ag_tool export` (Applies assignments and writes NDF/CSV files to `./output/`)
- **Direct Export Endpoint**: POST `/api/sessions/<slug>/export_direct` (Writes additions directly to the mod's GameData or a custom export folder)
- **Build Mod Endpoint**: POST `/api/sessions/<slug>/build` (Compiles the mod in-browser by executing `GenerateMod.bat` in the active mod folder)

CLI entry point is `src/wif_ag_tool/__main__.py`, which dispatches to subcommands defined in `src/wif_ag_tool/cli.py`.

## Update-Resilience Workflow (After a WARNO Game Patch)

Whenever a game patch updates WARNO's vanilla assets:
1. Run `UpdateMod.bat` from `<WARNO>\Mods\<YourMod>\` (the script ships with WARNO; it 3-way-merges the new vanilla baseline against your mod's tree).
2. Run `python -m wif_ag_tool refresh` (re-parses `StrategicDecks.ndf` and recounts vanilla pack indices) or trigger a catalog refresh from Settings.
3. Export files directly via the **📥 Export Mod** button on the UI (or manually via export zip).
4. Run the mod compiler via the **⚡ Build Mod** button on the UI (or manually run `GenerateMod.bat`).

## Key Technical Decisions & Constraints

- **Mod Settings & Workspace Paths**: Sessions support persistent settings for `target_mod_dir`, `game_dir`, and `export_dir` (stored in the session's JSON file under `sessions/`). **Leave `export_dir` empty** unless you have a reason to override — the default `<target_mod_dir>/GameData` is the only path the WARNO compiler reads from. Setting `export_dir` to the mod root puts files in `<mod>/Generated/...` which the compiler ignores.
- **Full-Replacement Export Model (content, not identity)**: A deck with a saved replica has its `DeckPackList`/`DeckCombatGroupList` rewritten to that replica's content; a deck with **no** replica is left untouched vanilla. `pipeline.build_export_blocks` is the shared core: it seeds an **empty** `DeckState` per deck so pack indices count from 0, and returns `{deck_name: (pack_refs, group_refs)}`. **Critical AG constraint**: each replica group must reuse its **vanilla combat-group descriptor name + token** (`group_generator.resolve_cg_name` + the token from parsed `StrategicCombatGroups`). The campaign binds pre-placed battalions to vanilla combat-group names; renaming a kept group (e.g. to `_WIF_A`) compiles fine but **hangs the campaign loader** (verified in-game 2026-05-29 — see memory `project_ag_combat_group_vanilla_names`). Removing a combat group is graceful (just omit it); renaming is fatal. Combat-group *contents* (smart groups/units) are freely replaced; their `(start,count)` tuples must stay ascending/contiguous (memory `project_ag_combat_group_ascending`).
- **Direct Export Writes In Place**: The WARNO compiler **only ingests the canonical `Strategic*.ndf` base files** in `GameData/Generated/Gameplay/Decks/`. Sidecar files named `*_additions.ndf` or `*_patch.ndf` are silently dropped. The direct-export endpoint therefore mutates the canonical files in place:
  - New `Descriptor_StrategicPack_*` blocks are **appended** to `StrategicPacks.ndf` under a `// === WIF AG additions ===` banner.
  - New `Descriptor_CombatGroup_*` blocks are written via `deck_patcher.apply_combat_group_patches()` (replace-by-name, else append) to `StrategicCombatGroups.ndf`.
  - `StrategicDecks.ndf` is mutated via `deck_patcher.replace_deck_lists()` which **overwrites** each replica'd deck's `DeckPackList` / `DeckCombatGroupList` with exactly the replica-derived refs (full replacement, not insertion). Orphaned vanilla packs/combat groups remain *defined* in their files but unreferenced by the replaced deck — harmless.
  - `PLATOONS.csv` is the mod's full localisation table. The export **appends** the new WIF token rows to it (dropping `generate_platoons_rows`' leading `"TOKEN";"REFTEXT"` header) — it must never overwrite the file, or every other platoon/unit name resolves to a missing token in-game.
  - A human-readable diff is written to `StrategicDecks_patch_summary.txt` (not `.ndf` — that name was the legacy plain-text format the compiler choked on).
- **`.orig` Snapshots Make Exports Idempotent**: On first export, each of the three base NDFs is snapshotted to `<file>.ndf.orig`. Every subsequent export restores from `.orig` before re-applying patches, so repeated clicks of 📥 Export Mod don't accumulate duplicates. If `.orig` files get deleted, the next export treats the current state as the new pristine baseline — which means **never delete `.orig` files while the live files contain WIF additions**, or you'll lock those additions in as the new "vanilla" baseline.
- **Browser-Triggered Compiler**: The backend executes `GenerateMod.bat` inside the configured `target_mod_dir` using `subprocess.run(..., timeout=90)`. Real-time exit status, stdout, and stderr logs are returned to the browser log console modal. **Caveat**: `GenerateMod.bat` ends with `PAUSE` waiting for a keypress, and a full WIF-sized first build takes 10–20 min, so the in-tool ⚡ Build Mod button frequently reports a false "Mod compilation failed" even when the build succeeded. For large mods, run `GenerateMod.bat` from a real cmd window and watch for `Mod Generation Success`.
- **Mod Structure Requirement — full-content, not patch-only**: WARNO mods that reference `WF_*` unit descriptors must include those descriptor definitions themselves (i.e., `GameData/Generated/Gameplay/Gfx/UniteDescriptor.ndf` and friends from the WIF source tree). A thin patch mod that depends on "A World in Flames" being co-activated does NOT work — the AG strategic packs resolve to dangling refs and the game silently falls back to vanilla. Scaffold a target mod via `<WARNO>\Mods\CreateNewMod.bat <Name>` (the script ships with WARNO at `<install>\Mods\`, alongside `UpdateMod.bat`, `modding_manual.pdf`, and `ndf_reference_manual.pdf`; the NDF compiler binaries live in `<WARNO>\Tools\`). Then merge the WIF source repo (`G:\Project\A-World-In-Flames\`) into `<Name>\GameData\`, renaming `Localisation\A World in Flames` → `Localisation\<Name>` (same for `ResourcePacks`) and updating `ResourcePacks.ndf` paths to match. Result: a self-contained ~5 GB mod that builds with `GenerateMod.bat`.
- **Pack-Count Schema — Duplicate Refs, Not a `Number` Field**: The Army General campaign uses a different recruitable-count encoding than skirmish. `StrategicPacks.ndf`'s `DeckPackDescriptor` has NO `Number` field (unlike skirmish's `DeckPacks.ndf`). To recruit `N` copies of a pack, the same `~/Descriptor_StrategicPack_*` ref must be **duplicated N times consecutively** in `DeckPackList`, and the SmartGroup tuple `(start_index, count)` reads exactly `count` consecutive slots starting at `start_index`. Getting this wrong silently produces an NDF that parses, compiles, and crashes only on pawn click (engine reads past the array). The export pipeline asserts `sum(SmartGroup counts) == DeckPackList growth` per deck via `pipeline._assert_pack_index_invariant` and refuses to write the export if violated. See NDF_REFERENCE.md §3-4 for the full rule and vanilla proof.
- **One-to-One Transports**: The WARNO engine operates on a 1-vehicle-to-1-squad transport rule. Transport capacity is handled at the squad level (all transport vehicles have `NbSeatsAvailable = 1` in `UniteDescriptor.ndf`), so no squad size calculation is needed.
- **DDR/RDA Mismatch**: East German decks are labeled `RDA` in deck names, but their units have MotherCountry `DDR` in the unit database. The tool maps them interchangeably.
- **Focus Preservation**: SPA view updates in `ui.html` must capture active element IDs and selection ranges before wiping `innerHTML` to avoid losing cursor focus during search/input typing.
- **WIF Combat Groups**: Combat groups are grouped under custom sub-categories (like `A`, `B`, `C`, `HQ`) and display cleanly formatted names in-game (e.g., `WIF — A`).
- **Hierarchical Platoon Structure**: The tool uses a 4-tier hierarchy: Deck → Combat Group → Platoon/Smart Group → Unit. Platoon names are resolved via `PLATOONS.csv` localisations or resolved using a heuristic based on unit contents if no translation is found.
- **Vanilla Localisation**: Vanilla unit name/deck tokens are loaded from the game files and merged with custom WIF units so that names resolve properly in the UI.
- **Test Integrity**: Unit tests must use mock paths in `tests/fixtures/` and never reference live game folders, ensuring they pass on CI. All API actions (settings configuration, direct export, and mod compiler mocking) are tested in `tests/test_web_api.py`.

## Project Layout

```
G:\Project\wif-ag-tool\
├── src/wif_ag_tool/
│   ├── models.py          # Core dataclasses (WifUnit, DeckState, StrategicPack, Assignment)
│   ├── config.py          # Path constants and environment overrides
│   ├── parser/
│   │   ├── unit_parser.py # Parses UniteDescriptor.ndf
│   │   ├── deck_parser.py # Parses StrategicDecks.ndf
│   │   ├── pack_parser.py # Parses StrategicPacks.ndf
│   │   └── save_parser.py # Parses save game .sav3 files
│   ├── generator/
│   │   ├── token_gen.py        # Generates unique, deterministic 10-character NDF name hashes
│   │   ├── pack_generator.py   # Generates DeckPackDescriptor NDF blocks
│   │   ├── group_generator.py  # Generates TDeckCombatGroupDescriptor NDF blocks
│   │   ├── deck_patcher.py     # Modifies DeckPackList / DeckCombatGroupList
│   │   └── localisation.py     # Generates PLATOONS.csv name tables
│   ├── validator/         # Validates units, index bounds, and token rules
│   ├── cli.py             # CLI command orchestrator (dispatched from __main__.py)
│   └── web/
│       ├── app.py         # Flask app setup
│       ├── api.py         # REST endpoint implementation
│       └── static/
│           └── ui.html    # Single-page front-end SPA
├── sessions/              # Per-session JSON state (settings + assignments)
├── data/                  # Cached parsed catalogs (.deck_cache.json etc.)
├── output/                # Default export target when no export_dir is set
└── tests/                 # Unit/integration suite using tests/fixtures/ mock data
```

See `NDF_REFERENCE.md` for notes on the NDF file formats this tool reads and patches.
