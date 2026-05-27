# WIF AG Tool — Developer Reference Guide

A Python web tool that lets you interactively assign World in Flames (WIF) modern units to WARNO Army General campaign decks, then exports the NDF patch files needed to build the mod.

## Core Commands

- **Run Dev Server**: `python -m wif_ag_tool serve` (Starts Flask server on `http://localhost:5000`)
- **Run Tests**: `pytest tests/ -v`
- **Re-parse Decks**: `python -m wif_ag_tool refresh` (Updates `.deck_cache.json` from vanilla NDF files)
- **Export NDF Mod Files**: `python -m wif_ag_tool export` (Applies assignments and writes NDF/CSV files to `./output/`)
- **Direct Export Endpoint**: POST `/api/sessions/<slug>/export_direct` (Writes additions directly to the mod's GameData or a custom export folder)
- **Build Mod Endpoint**: POST `/api/sessions/<slug>/build` (Compiles the mod in-browser by executing `GenerateMod.bat` in the active mod folder)

## Update-Resilience Workflow (After a WARNO Game Patch)

Whenever a game patch updates WARNO's vanilla assets:
1. Run `UpdateMod.bat` (WARNO Mod Editor resolves vanilla NDF conflicts).
2. Run `python -m wif_ag_tool refresh` (re-parses `StrategicDecks.ndf` and recounts vanilla pack indices) or trigger a catalog refresh from Settings.
3. Export files directly via the **📥 Export Mod** button on the UI (or manually via export zip).
4. Run the mod compiler via the **⚡ Build Mod** button on the UI (or manually run `GenerateMod.bat`).

## Key Technical Decisions & Constraints

- **Mod Settings & Workspace Paths**: Sessions support persistent settings for `target_mod_dir`, `game_dir`, and `export_dir` (stored in the session's JSON file).
- **Direct Export Directory Structure**:
  - Strategic additions are exported directly to `{export_dir}/Generated/Gameplay/Decks/...`
  - Platoons localisation CSV is exported to `{export_dir}/Localisation/{mod_name}/PLATOONS_additions.csv`
- **Browser-Triggered Compiler**: The backend executes `GenerateMod.bat` inside the configured `target_mod_dir` using `subprocess.run(..., timeout=90)`. Real-time exit status, stdout, and stderr logs are returned to the browser log console modal.
- **One-to-One Transports**: The WARNO engine operates on a 1-vehicle-to-1-squad transport rule. Transport capacity is handled at the squad level (all transport vehicles have `NbSeatsAvailable = 1` in `UniteDescriptor.ndf`), so no squad size calculation is needed.
- **DDR/RDA Mismatch**: East German decks are labeled `RDA` in deck names, but their units have MotherCountry `DDR` in the unit database. The tool maps them interchangeably.
- **Focus Preservation**: SPA view updates in `ui.html` must capture active element IDs and selection ranges before wiping `innerHTML` to avoid losing cursor focus during search/input typing.
- **WIF Combat Groups**: Combat groups are grouped under custom sub-categories (like `A`, `B`, `C`, `HQ`) and display cleanly formatted names in-game (e.g., `WIF — A`).
- **Hierarchical Platoon Structure**: The tool uses a 4-tier hierarchy: Deck → Combat Group → Platoon/Smart Group → Unit. Platoon names are resolved via `PLATOONS.csv` localisations or resolved using a heuristic based on unit contents if no translation is found.
- **Vanilla Localisation**: Vanilla unit name/deck tokens are loaded from the game files and merged with custom WIF units so that names resolve properly in the UI.
- **Test Integrity**: Unit tests must use mock paths in `tests/fixtures/` and never reference live game folders, ensuring they pass on CI. All API actions (settings configuration, direct export, and mod compiler mocking) are tested in `tests/test_web_api.py`.

## Project Layout

```
G:\Warno_mod\wif_ag_tool\
├── src/wif_ag_tool/
│   ├── models.py          # Core dataclasses (WifUnit, DeckState, StrategicPack, Assignment)
│   ├── config.py          # Path constants and environment overrides
│   ├── parser/
│   │   ├── unit_parser.py # Parses UniteDescriptor.ndf
│   │   ├── deck_parser.py # Parses StrategicDecks.ndf
│   │   ├── pack_parser.py # Parses StrategicPacks.ndf
│   │   └── save_parser.py # Parses save game .sav3 files
│   ├── generator/
│   │   ├── token_gen.py   # Generates unique, deterministic 10-character NDF name hashes
│   │   ├── pack_generator.py  # Generates DeckPackDescriptor NDF blocks
│   │   ├── group_generator.py # Generates TDeckCombatGroupDescriptor NDF blocks
│   │   ├── deck_patcher.py    # Modifies DeckPackList / DeckCombatGroupList
│   │   └── localisation.py   # Generates PLATOONS.csv name tables
│   ├── validator/         # Validates units, index bounds, and token rules
│   ├── cli.py             # CLI command orchestrator
│   └── web/
│       ├── app.py         # Flask app setup
│       ├── api.py         # REST endpoint implementation
│       └── static/
│           └── ui.html    # Single-page front-end SPA
└── tests/                 # Full unit/integration testing suite using mock fixtures
```
