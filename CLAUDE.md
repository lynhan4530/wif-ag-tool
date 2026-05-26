# WIF AG Tool — Claude Coding Instructions

## What this project is

A Python web tool that lets you interactively assign World in Flames (WIF) modern units to
WARNO Army General campaign decks, then exports the NDF patch files needed to build the mod.

**The core problem it solves:** The Army General deck integration is fragile — `PackIndexUnitNumberList`
references packs by *position index* in `DeckPackList`. Any WARNO game patch that adds/removes vanilla
packs silently breaks all combat groups. This tool recalculates indices automatically on every run, and
provides an interactive UI for assigning units instead of hand-editing 13 MB NDF files.

**Background context:** Full recon and architecture decisions are in `NDF_REFERENCE.md` (same directory).
Read it before writing any generator or parser code.

---

## Project layout (build this exactly)

```
G:\Warno_mod\wif_ag_tool\               ← cwd, also a git repo
├── src/wif_ag_tool/
│   ├── __init__.py
│   ├── models.py                        ✅ DONE
│   ├── config.py                        ✅ DONE
│   ├── parser/
│   │   ├── __init__.py
│   │   ├── unit_parser.py               ✅ DONE
│   │   ├── deck_parser.py               ← TODO
│   │   ├── pack_parser.py               ← TODO
│   │   └── save_parser.py               ← TODO
│   ├── generator/
│   │   ├── __init__.py
│   │   ├── token_gen.py                 ← TODO
│   │   ├── pack_generator.py            ← TODO
│   │   ├── group_generator.py           ← TODO
│   │   ├── deck_patcher.py              ← TODO
│   │   └── localisation.py             ← TODO
│   ├── validator/
│   │   ├── __init__.py
│   │   ├── unit_validator.py            ← TODO
│   │   ├── index_validator.py           ← TODO
│   │   └── token_validator.py           ← TODO
│   ├── cli.py                           ← TODO
│   └── web/
│       ├── __init__.py
│       ├── app.py                       ← TODO
│       ├── api.py                       ← TODO
│       └── static/
│           └── ui.html                  ← TODO
├── tests/
│   ├── conftest.py                      ← TODO (shared fixtures)
│   ├── fixtures/
│   │   ├── sample_units.ndf             ← TODO (hand-crafted, see NDF_REFERENCE.md)
│   │   ├── sample_deck.ndf              ← TODO
│   │   ├── sample_packs.ndf             ← TODO
│   │   └── sample_combatgroups.ndf      ← TODO
│   ├── test_parser.py                   ← TODO
│   ├── test_generator.py                ← TODO
│   ├── test_validator.py                ← TODO
│   └── test_integration.py             ← TODO
├── configs/
│   └── example_US_11ACR.yaml           ← TODO
├── assignments.json                     ← TODO (empty {})
├── pyproject.toml                       ← TODO
├── requirements.txt                     ← TODO
├── requirements-dev.txt                 ← TODO
├── .gitignore                           ← TODO
└── .github/
    └── workflows/
        └── test.yml                     ← TODO
```

---

## Files already created

### `src/wif_ag_tool/models.py` ✅
Defines: `WifUnit`, `DeckState`, `StrategicPack`, `Assignment` dataclasses.
- `WifUnit.unit_path` property → `$/GFX/Unit/Descriptor_Unit_WF_...`
- `DeckState.next_index` property → `len(pack_list)` (safe append index)
- `Assignment.pack_name(xp)` → `Descriptor_StrategicPack_WF_..._<xp>`
- `Assignment.combat_group_name()` → `Descriptor_CombatGroup_<deck_short>_WIF_<unit>`

### `src/wif_ag_tool/config.py` ✅
Path constants for WIF source, vanilla recon, WARNO install, saves dir.
All overrideable via environment variables (`WIF_ROOT`, `VANILLA_ROOT`, `WARNO_MODS_DIR`, `WARNO_SAVES_DIR`).
Tests must NOT use these constants — pass paths directly to parser functions.

### `src/wif_ag_tool/parser/unit_parser.py` ✅
`parse_wif_units(path: Path, nation_filter=None) -> dict[str, WifUnit]`
- Splits UniteDescriptor.ndf into per-unit blocks by scanning `^export Descriptor_Unit_WF_` lines
- Regex-extracts GUID, MotherCountry, UnitAttackValue, UnitDefenseValue, UnitBonusXpPerLevelValue,
  UnitRole, NameToken, SpecialtiesList from each block
- Returns dict keyed by unit name WITHOUT `Descriptor_Unit_` prefix

---

## Modules to build (in this order)

### 1. `parser/deck_parser.py`

```python
def parse_deck(path: Path, deck_name: str) -> DeckState:
    """Find deck_name in StrategicDecks.ndf and return its DeckState."""
```

**Algorithm:**
1. Scan file for line: `export {deck_name} is TDeckDescriptor`
2. From there, find `DeckPackList =` then collect all `~/Descriptor_StrategicPack_*,` lines
   until the closing `]`
3. Find `DeckCombatGroupList =` then collect all `~/Descriptor_CombatGroup_*,` lines
4. Strip `~/` prefix and trailing `,` from each item
5. Return `DeckState(name=deck_name, pack_list=[...], combat_group_list=[...])`

**Key:** `DeckState.next_index = len(pack_list)`. This is the index new packs start at.
For `Descriptor_Deck_pion_US_11ACR_4`: 93 existing packs → `next_index = 93`.

Also expose:
```python
def list_decks(path: Path, nation_prefix: str | None = None) -> list[str]:
    """Return all Descriptor_Deck_pion_* names. Filter by e.g. 'US', 'SOV', 'FR'."""
```

---

### 2. `parser/pack_parser.py`

```python
def parse_strategic_packs(path: Path) -> dict[str, StrategicPack]:
    """Parse all DeckPackDescriptor entries from StrategicPacks.ndf."""
```

Each entry looks like:
```
Descriptor_StrategicPack_Alpha_Jet_BEL_1 is DeckPackDescriptor
(
    Xp = 1
    Unit = $/GFX/Unit/Descriptor_Unit_Alpha_Jet_BEL
)
```
or with Transport:
```
Descriptor_StrategicPack_M113A1B_BEL_Rifles_AT_BEL_0 is DeckPackDescriptor
(
    Transport = $/GFX/Unit/Descriptor_Unit_M113A1B_BEL
    Unit = $/GFX/Unit/Descriptor_Unit_Rifles_AT_BEL
)
```
Note: `Xp` field is absent when 0. Return `dict[str, StrategicPack]` keyed by pack name.

---

### 3. `parser/save_parser.py`

```python
def list_campaigns(saves_dir: Path) -> list[dict]:
    """Parse .sav3 filenames → campaign info dicts. Save data is binary; filename only."""
```

Filename format: `Autosave - #US #SOV #medium{CENTAG - DAY 7} Highway 66.sav3`
Extract:
- `factions`: list of strings from `#WORD` tokens (e.g. `["US", "SOV"]`)
- `campaign`: string inside `{}` (e.g. `"CENTAG - DAY 7"`)
- `mission`: string after `}` (e.g. `"Highway 66"`)
- `path`: full Path to the file

Real save files live at:
`G:\Program Files (x86)\Steam\userdata\142459089\1611600\remote\*.sav3`

---

### 4. `generator/token_gen.py`

```python
def make_token(unit_id: str, deck_name: str, suffix: str = "") -> str:
    """Generate a deterministic 10-char uppercase token for NDF Name fields."""
```

Algorithm:
```python
import hashlib
key = f"{unit_id}:{deck_name}{suffix}"
return hashlib.md5(key.encode()).hexdigest()[:10].upper()
```

Always exactly 10 chars. Always uppercase. Same inputs → same output (idempotent).
`suffix` is used for collision resolution: if token already in existing_tokens set,
retry with suffix="1", "2", etc.

Also:
```python
def make_unique_token(unit_id: str, deck_name: str, existing: set[str]) -> str:
    """Like make_token but guaranteed unique against existing set."""
```

---

### 5. `generator/pack_generator.py`

```python
def generate_pack(unit_id: str, xp: int, transport_id: str | None = None) -> str:
    """Emit a DeckPackDescriptor NDF block as a string."""
```

Output (no transport):
```ndf
Descriptor_StrategicPack_WF_M1A2_SEPV2_Abrams_US_1 is DeckPackDescriptor
(
    Xp   = 1
    Unit = $/GFX/Unit/Descriptor_Unit_WF_M1A2_SEPV2_Abrams_US
)
```

Output (with transport):
```ndf
Descriptor_StrategicPack_WF_Rifles_CMD_US_1 is DeckPackDescriptor
(
    Xp        = 1
    Transport = $/GFX/Unit/Descriptor_Unit_WF_Stryker_ICV_US
    Unit      = $/GFX/Unit/Descriptor_Unit_WF_Rifles_CMD_US
)
```

Also:
```python
def generate_packs_for_assignment(assignment: Assignment) -> str:
    """Emit all packs for all XP levels in an assignment. Newline-separated."""
```

---

### 6. `generator/group_generator.py`

```python
def generate_combat_group(
    assignment: Assignment,
    deck_state: DeckState,
    existing_tokens: set[str],
) -> str:
    """Emit a TDeckCombatGroupDescriptor NDF block."""
```

Output (1 unit, xp=[1,2,3], deck.next_index=93):
```ndf
Descriptor_CombatGroup_pion_US_11ACR_4_WIF_WF_M1A2_SEPV2_Abrams_US is TDeckCombatGroupDescriptor
(
    Name = "A3F9B2C1D4"
    SmartGroupList =
    [
        TDeckSmartGroupDescriptor
        (
            Name = "B1E2F3A4C5"
            PackIndexUnitNumberList =
            [
                (93,1),
            ]
        ),
        TDeckSmartGroupDescriptor
        (
            Name = "C5D6E7F8A9"
            PackIndexUnitNumberList =
            [
                (94,1),
            ]
        ),
        TDeckSmartGroupDescriptor
        (
            Name = "D9A0B1C2E3"
            PackIndexUnitNumberList =
            [
                (95,1),
            ]
        ),
    ]
)
```

**Critical index rule:** For xp_levels=[1,2,3] with next_index=93:
- XP 1 pack → index 93
- XP 2 pack → index 94
- XP 3 pack → index 95

Tokens: group Name = `make_unique_token(unit_id, deck_name)`.
Each SmartGroup Name = `make_unique_token(unit_id + "_xp" + str(xp), deck_name)`.

---

### 7. `generator/deck_patcher.py`

```python
def generate_deck_patch(
    deck_name: str,
    new_pack_refs: list[str],
    new_group_refs: list[str],
) -> str:
    """Emit the lines to append to a deck's DeckPackList and DeckCombatGroupList."""
```

Output format — a human-readable patch file, NOT a diff:
```
// === WIF AG PATCH for Descriptor_Deck_pion_US_11ACR_4 ===
// Append these lines to DeckPackList (before the closing ]):

        ~/Descriptor_StrategicPack_WF_M1A2_SEPV2_Abrams_US_1,
        ~/Descriptor_StrategicPack_WF_M1A2_SEPV2_Abrams_US_2,
        ~/Descriptor_StrategicPack_WF_M2A4_Bradley_US_1,

// Append these lines to DeckCombatGroupList (before the closing ]):

        ~/Descriptor_CombatGroup_pion_US_11ACR_4_WIF_WF_M1A2_SEPV2_Abrams_US,
        ~/Descriptor_CombatGroup_pion_US_11ACR_4_WIF_WF_M2A4_Bradley_US,
```

Also implement auto-apply:
```python
def apply_deck_patch(strategic_decks_path: Path, deck_name: str,
                     new_pack_refs: list[str], new_group_refs: list[str]) -> None:
    """Directly modify StrategicDecks.ndf by inserting refs before closing ] of each list."""
```
Find the closing `]` of each list by tracking bracket depth from the list header.

---

### 8. `generator/localisation.py`

```python
def generate_platoons_rows(assignments: list[Assignment], units: dict[str, WifUnit]) -> str:
    """Emit PLATOONS.csv rows for all generated tokens."""
```

CSV format (semicolon-separated, double-quoted, no BOM):
```
"TOKEN";"REFTEXT"
"A3F9B2C1D4";"WIF M1A2 SEPV2 Abrams"
"B1E2F3A4C5";"WIF M1A2 SEPV2 Abrams XP1"
```

One row per CombatGroup Name, plus one per SmartGroup Name.
Display name = `"WIF " + unit.name_token_display` (look up from WIF UNITS.csv).

---

### 9. `validator/unit_validator.py`

```python
class UnitNotFoundError(Exception): pass

def validate_unit_exists(unit_id: str, units: dict[str, WifUnit]) -> None:
    """Raise UnitNotFoundError if unit_id not in units dict."""
```

---

### 10. `validator/index_validator.py`

```python
class IndexOutOfBoundsError(Exception): pass

def validate_pack_index(index: int, deck_state: DeckState) -> None:
    """Raise IndexOutOfBoundsError if index >= deck_state.next_index."""
```

Note: `next_index` is the NEXT safe append position. Valid existing indices are 0..next_index-1.
A new pack at next_index is valid (it will be appended). Index > next_index is invalid.

---

### 11. `validator/token_validator.py`

```python
class TokenLengthError(Exception): pass
class TokenCollisionError(Exception): pass

def validate_token(token: str) -> None:
    """Raise TokenLengthError if not exactly 10 chars."""

def validate_token_unique(token: str, existing: set[str]) -> None:
    """Raise TokenCollisionError if token already in existing set."""
```

---

### 12. `cli.py`

Three commands via `python -m wif_ag_tool <command>`:

```
refresh   Re-parse vanilla StrategicDecks.ndf, update .deck_cache.json
export    Read assignments.json, run full generator, write NDF files to ./output/
serve     Start Flask dev server on localhost:5000
```

```python
# cli.py
import sys, json
from pathlib import Path

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if cmd == "refresh": cmd_refresh()
    elif cmd == "export": cmd_export()
    elif cmd == "serve":  cmd_serve()
    else: print(f"Unknown command: {cmd}")

if __name__ == "__main__":
    main()
```

---

### 13. `web/app.py` + `web/api.py`

Flask app. `app.py` creates the Flask instance and registers the API blueprint.
`api.py` implements the REST endpoints:

| Method | Path | Returns |
|--------|------|---------|
| GET | `/api/campaigns` | `[{factions, campaign, mission, path}]` from .sav3 filenames |
| GET | `/api/decks?nation=US` | `[{name, next_index, pack_count}]` |
| GET | `/api/deck/<deck_name>` | `{name, pack_list, combat_group_list, next_index, assignments:[]}` |
| GET | `/api/wif_units?nation=US&role=armor&q=abrams` | `[WifUnit as dict]` |
| POST | `/api/assign` | body: Assignment JSON → saves to assignments.json |
| DELETE | `/api/assign/<deck>/<unit>` | removes from assignments.json |
| POST | `/api/export` | runs generator pipeline → returns zip file download |
| POST | `/api/refresh` | runs deck_parser.refresh → updates .deck_cache.json |

The WifUnit catalogue and DeckState cache are loaded once at startup and cached in memory.
`/api/refresh` reloads the deck cache from disk without restarting the server.

---

### 14. `web/static/ui.html`

Single HTML file, vanilla JS only (no React/Vue/build step). Reads from Flask API.

Layout:
```
┌────────────────────────────────────────────────────────────────────┐
│  🎮 WIF AG Tool    [Campaign: CENTAG DAY 7 — US vs SOV]            │
├──────────────────────────┬─────────────────────────────────────────┤
│  DECK SELECTOR           │  WIF UNIT BROWSER                       │
│  Nation: [US ▼]          │  Nation: [US ▼]  Role: [all ▼]  🔍      │
│                          │                                         │
│  ● pion_US_11ACR_4  93p  │  M1A2 SEPV2   ATK:652  DEF:497   [+]   │
│  ○ pion_US_11ACR_3       │  M1A2 SEPV3   ATK:720  DEF:535   [+]   │
│  ○ pion_US_11ACR_2       │  M2A4 Bradley ATK:171  DEF:86    [+]   │
│  ○ pion_US_11ACR_1       │  AH-64E       ATK:245  DEF:110   [+]   │
│                          │  M109A6       ATK:89   DEF:42    [+]   │
│  VANILLA UNITS:          │  HIMARS       ATK:95   DEF:30    [+]   │
│  UH60A Supply (x8)       │  ...                                    │
│  CH47 Chinook (x4)       │                                         │
│  OH58C Scout (x2)        │                                         │
│  AH1F Hog (x2)           │                                         │
│  ...                     │                                         │
├──────────────────────────┴─────────────────────────────────────────┤
│  ASSIGNED WIF UNITS (pion_US_11ACR_4)                 [Export NDF] │
│  M1A2 SEPV2  XP:[1✓ 2✓ 3✓]  ATK:[652] DEF:[497]  count:[1]  [✕]  │
│  M2A4 Brad   XP:[1✓ 2☐ 3☐]  ATK:[171] DEF:[86 ]  count:[1]  [✕]  │
└────────────────────────────────────────────────────────────────────┘
```

ATK/DEF fields in the bottom bar are editable (override WIF values).
[Export NDF] → POST /api/export → downloads zip.

---

## Test fixtures (hand-crafted NDF, no game files needed)

### `tests/fixtures/sample_units.ndf`
Three WF_ units (minimal valid blocks):

```ndf
export Descriptor_Unit_WF_M1A2_SEPV2_Abrams_US is TEntityDescriptor
(
    DescriptorId = GUID:{454ef2bc-ff1e-42fd-9c64-7988718c197d}
    ClassNameForDebug = 'Unit_WF_M1A2_SEPV2_Abrams_US'
    ModulesDescriptors = [
        TTypeUnitModuleDescriptor
        (
            Coalition = ECoalition/NATO
            MotherCountry = 'US'
        ),
        TDamageModuleDescriptor
        (
            HitRollECM = 0.0
        ),
        TStrategicDataModuleDescriptor
        (
            UnitAttackValue = 652
            UnitDefenseValue = 497
            UnitBonusXpPerLevelValue = 1
        ),
        TUnitUIModuleDescriptor
        (
            PriceCategory = 'tank_A'
            UnitRole = 'armor'
            SpecialtiesList = [
                '_smoke_launcher',
                'Thermals2',
            ]
            NameToken = 'WFM1ASV2'
        ),
    ]
)

export Descriptor_Unit_WF_M2A4_Bradley_US is TEntityDescriptor
(
    DescriptorId = GUID:{ac17b0b3-412f-46fe-b2f8-6344f3947eec}
    ClassNameForDebug = 'Unit_WF_M2A4_Bradley_US'
    ModulesDescriptors = [
        TTypeUnitModuleDescriptor
        (
            Coalition = ECoalition/NATO
            MotherCountry = 'US'
        ),
        TStrategicDataModuleDescriptor
        (
            UnitAttackValue = 171
            UnitDefenseValue = 86
            UnitBonusXpPerLevelValue = 1
        ),
        TUnitUIModuleDescriptor
        (
            PriceCategory = 'tank_A'
            UnitRole = 'ifv'
            SpecialtiesList = [
                '_ifv',
                '_eo_dazzler',
                'Thermals2',
                '_era',
                'MRAP',
            ]
            NameToken = 'WFM2BA4A'
        ),
    ]
)

export Descriptor_Unit_WF_T90M_RUS is TEntityDescriptor
(
    DescriptorId = GUID:{bbbbbbbb-0000-1111-2222-cccccccccccc}
    ClassNameForDebug = 'Unit_WF_T90M_RUS'
    ModulesDescriptors = [
        TTypeUnitModuleDescriptor
        (
            Coalition = ECoalition/PACT
            MotherCountry = 'RUS'
        ),
        TStrategicDataModuleDescriptor
        (
            UnitAttackValue = 580
            UnitDefenseValue = 440
            UnitBonusXpPerLevelValue = 1
        ),
        TUnitUIModuleDescriptor
        (
            PriceCategory = 'tank_A'
            UnitRole = 'armor'
            SpecialtiesList = [
                '_smoke_launcher',
                '_era',
            ]
            NameToken = 'WFT90M01'
        ),
    ]
)
```

### `tests/fixtures/sample_deck.ndf`
One deck with exactly 5 packs (next_index = 5):

```ndf
export Descriptor_Deck_pion_TEST_Alpha_1 is TDeckDescriptor
(
    DeckIdentifier = 'pion_TEST_Alpha_1'
    DeckDivision = $/GFX/Division/Descriptor_Deck_Division_TEST_solo
    Superior = $/UI/BattleOrder/TEST_Subordination
    DeckPackList =
    [
        ~/Descriptor_StrategicPack_UnitA_1,
        ~/Descriptor_StrategicPack_UnitB_1,
        ~/Descriptor_StrategicPack_UnitC_1,
        ~/Descriptor_StrategicPack_UnitA_1,
        ~/Descriptor_StrategicPack_UnitB_1,
    ]
    DeckCombatGroupList =
    [
        ~/Descriptor_CombatGroup_pion_TEST_Alpha_1_HQ,
        ~/Descriptor_CombatGroup_pion_TEST_Alpha_1_A,
    ]
)
```

### `tests/fixtures/sample_packs.ndf`
```ndf
Descriptor_StrategicPack_UnitA_1 is DeckPackDescriptor
(
    Xp = 1
    Unit = $/GFX/Unit/Descriptor_Unit_UnitA
)

Descriptor_StrategicPack_UnitB_1 is DeckPackDescriptor
(
    Xp = 1
    Unit = $/GFX/Unit/Descriptor_Unit_UnitB
)

Descriptor_StrategicPack_UnitC_1 is DeckPackDescriptor
(
    Xp = 1
    Unit = $/GFX/Unit/Descriptor_Unit_UnitC
)

Descriptor_StrategicPack_WithTransport_0 is DeckPackDescriptor
(
    Transport = $/GFX/Unit/Descriptor_Unit_VehicleX
    Unit = $/GFX/Unit/Descriptor_Unit_InfantryY
)
```

### `tests/fixtures/sample_combatgroups.ndf`
```ndf
Descriptor_CombatGroup_pion_TEST_Alpha_1_HQ is TDeckCombatGroupDescriptor
(
    Name = "AAAAAAAAAA"
    SmartGroupList =
    [
        TDeckSmartGroupDescriptor
        (
            Name = "BBBBBBBBBB"
            IsHQ = True
            PackIndexUnitNumberList =
            [
                (0,1),
            ]
        ),
    ]
)

Descriptor_CombatGroup_pion_TEST_Alpha_1_A is TDeckCombatGroupDescriptor
(
    Name = "CCCCCCCCCC"
    SmartGroupList =
    [
        TDeckSmartGroupDescriptor
        (
            Name = "DDDDDDDDDD"
            PackIndexUnitNumberList =
            [
                (1,2),
                (2,2),
            ]
        ),
    ]
)
```

---

## Test cases

### `tests/test_parser.py` (9 tests)
Use `Path("tests/fixtures/sample_units.ndf")` etc. — never real game paths.

```python
def test_parse_unit_extracts_guid():
    units = parse_wif_units(FIXTURE_UNITS)
    assert units["WF_M1A2_SEPV2_Abrams_US"].guid == "454ef2bc-ff1e-42fd-9c64-7988718c197d"

def test_parse_unit_extracts_strategic_values():
    units = parse_wif_units(FIXTURE_UNITS)
    u = units["WF_M1A2_SEPV2_Abrams_US"]
    assert u.attack == 652
    assert u.defense == 497
    assert u.xp_bonus == 1

def test_parse_unit_extracts_name_token():
    units = parse_wif_units(FIXTURE_UNITS)
    assert units["WF_M1A2_SEPV2_Abrams_US"].name_token == "WFM1ASV2"

def test_parse_unit_extracts_nation():
    units = parse_wif_units(FIXTURE_UNITS)
    assert units["WF_M1A2_SEPV2_Abrams_US"].nation == "US"

def test_parse_units_filter_by_nation():
    units = parse_wif_units(FIXTURE_UNITS, nation_filter="RUS")
    assert list(units.keys()) == ["WF_T90M_RUS"]

def test_parse_deck_pack_list_order():
    deck = parse_deck(FIXTURE_DECK, "Descriptor_Deck_pion_TEST_Alpha_1")
    assert deck.pack_list[0] == "Descriptor_StrategicPack_UnitA_1"
    assert deck.pack_list[4] == "Descriptor_StrategicPack_UnitB_1"

def test_parse_deck_next_index():
    deck = parse_deck(FIXTURE_DECK, "Descriptor_Deck_pion_TEST_Alpha_1")
    assert deck.next_index == 5

def test_parse_strategic_pack_no_transport():
    packs = parse_strategic_packs(FIXTURE_PACKS)
    p = packs["Descriptor_StrategicPack_UnitA_1"]
    assert p.xp == 1
    assert "Descriptor_Unit_UnitA" in p.unit
    assert p.transport is None

def test_parse_strategic_pack_with_transport():
    packs = parse_strategic_packs(FIXTURE_PACKS)
    p = packs["Descriptor_StrategicPack_WithTransport_0"]
    assert p.transport is not None
    assert "Descriptor_Unit_VehicleX" in p.transport
```

### `tests/test_generator.py` (9 tests)

```python
def test_gen_pack_ndf_syntax():
    out = generate_pack("WF_M1A2_SEPV2_Abrams_US", xp=1)
    assert "is DeckPackDescriptor" in out
    assert "Xp   = 1" in out
    assert "$/GFX/Unit/Descriptor_Unit_WF_M1A2_SEPV2_Abrams_US" in out

def test_gen_pack_no_transport_field():
    out = generate_pack("WF_M1A2_SEPV2_Abrams_US", xp=1)
    assert "Transport" not in out

def test_gen_combat_group_indices_start_at_next():
    deck = DeckState("Descriptor_Deck_pion_TEST_Alpha_1", ["p"]*5, [])
    a = Assignment("Descriptor_Deck_pion_TEST_Alpha_1", "WF_M1A2_SEPV2_Abrams_US", xp_levels=[1])
    out = generate_combat_group(a, deck, set())
    assert "(5,1)" in out

def test_gen_combat_group_multi_xp_sequential_indices():
    deck = DeckState("Descriptor_Deck_pion_TEST_Alpha_1", ["p"]*5, [])
    a = Assignment("Descriptor_Deck_pion_TEST_Alpha_1", "WF_M1A2_SEPV2_Abrams_US", xp_levels=[1,2,3])
    out = generate_combat_group(a, deck, set())
    assert "(5,1)" in out
    assert "(6,1)" in out
    assert "(7,1)" in out

def test_gen_deck_patch_appends_correct_count():
    patch = generate_deck_patch("TestDeck", ["~/Pack_A,", "~/Pack_B,"], ["~/Group_A,"])
    assert patch.count("~/Pack_") == 2
    assert patch.count("~/Group_") == 1

def test_gen_token_length():
    t = make_token("WF_M1A2_SEPV2_Abrams_US", "Descriptor_Deck_pion_US_11ACR_4")
    assert len(t) == 10

def test_gen_token_uppercase():
    t = make_token("WF_M1A2_SEPV2_Abrams_US", "Descriptor_Deck_pion_US_11ACR_4")
    assert t == t.upper()

def test_gen_token_deterministic():
    t1 = make_token("WF_M1A2_SEPV2_Abrams_US", "Descriptor_Deck_pion_US_11ACR_4")
    t2 = make_token("WF_M1A2_SEPV2_Abrams_US", "Descriptor_Deck_pion_US_11ACR_4")
    assert t1 == t2

def test_gen_localisation_csv_row():
    row = generate_platoons_rows(
        [Assignment("d", "WF_M1A2_SEPV2_Abrams_US", xp_levels=[1])],
        {"WF_M1A2_SEPV2_Abrams_US": WifUnit("WF_M1A2_SEPV2_Abrams_US","g","US",652,497,1,"armor","WFM1ASV2")}
    )
    assert '";"' in row   # semicolon separator
    assert '"' in row     # double-quoted
```

### `tests/test_validator.py` (6 tests)

```python
def test_valid_unit_exists():
    validate_unit_exists("WF_M1A2_SEPV2_Abrams_US", {"WF_M1A2_SEPV2_Abrams_US": ...})
    # no exception

def test_invalid_unit_raises():
    with pytest.raises(UnitNotFoundError):
        validate_unit_exists("WF_NONEXISTENT", {})

def test_valid_index_in_bounds():
    deck = DeckState("d", ["p"]*5, [])
    validate_pack_index(5, deck)   # 5 == next_index, valid for new append

def test_invalid_index_out_of_bounds_raises():
    deck = DeckState("d", ["p"]*5, [])
    with pytest.raises(IndexOutOfBoundsError):
        validate_pack_index(6, deck)

def test_token_valid_length():
    validate_token("ABCDEFGHIJ")   # no exception

def test_token_invalid_length_raises():
    with pytest.raises(TokenLengthError):
        validate_token("TOOSHORT")
```

### `tests/test_integration.py` (6 tests)

```python
def test_full_pipeline_one_unit(tmp_path):
    # Copy fixtures to tmp_path, run full export pipeline
    # Assert 3 output files created: StrategicPacks.ndf, CombatGroups.ndf, DecksPatch.ndf

def test_generated_pack_index_matches_next(tmp_path):
    # Assign to sample deck (next_index=5), check generated group has (5,1)

def test_idempotent_generation(tmp_path):
    # Run export twice, assert file contents identical

def test_multi_unit_assignment(tmp_path):
    # Assign 3 units, assert all 3 appear in StrategicPacks output

def test_attack_override_in_config(tmp_path):
    # Assignment with attack_override=300, verify it's stored in assignments.json
    # (Override affects future autoresolve tuning, not the NDF output in v1)

def test_export_produces_three_files(tmp_path):
    # Run export, assert StrategicPacks_additions.ndf,
    # StrategicCombatGroups_additions.ndf, StrategicDecks_patch.ndf all exist
```

---

## pyproject.toml

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "wif-ag-tool"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["flask>=3.0", "pyyaml>=6.0"]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov>=5.0"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

## requirements.txt
```
flask>=3.0
pyyaml>=6.0
```

## requirements-dev.txt
```
pytest>=8.0
pytest-cov>=5.0
```

## .gitignore
```
__pycache__/
*.pyc
*.egg-info/
dist/
build/
.coverage
assignments.json
.deck_cache.json
output/
```

---

## GitHub Actions CI

### `.github/workflows/test.yml`
```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - run: pytest tests/ -v --tb=short --cov=src/wif_ag_tool --cov-report=term-missing
```

**CI design principle:** All tests use `tests/fixtures/` only. They never reference
`G:\Warno_mod\` or `G:\Project\A-World-In-Flames\`. Those paths don't exist on GitHub runners.
Real NDF files are only touched by `cli.py refresh` at runtime on the user's Windows machine.

---

## Update-resilience workflow (after any WARNO patch)

```
1. UpdateMod.bat                  ← WME resolves vanilla NDF conflicts
2. py -m wif_ag_tool refresh      ← re-parses StrategicDecks.ndf, recounts pack indices
3. py -m wif_ag_tool export       ← regenerates all NDF additions with fresh indices
4. GenerateMod.bat                ← rebuilds .ndfbin
```

The refresh command re-reads the LIVE post-patch deck and recalculates `DeckState.next_index`.
The generator always uses this fresh value — index drift is impossible.

---

## Verification steps

1. `pytest tests/ -v` → all green (on any machine, no game files needed)
2. `py -m wif_ag_tool refresh` → no errors, `.deck_cache.json` updated
3. Assign M1A2 SEPV2 + M2A4 to `Descriptor_Deck_pion_US_11ACR_4` via UI → Export → check 3 files
4. Copy output to AGPatchTest mod Decks folder, run `GenerateMod.bat` → no errors
5. `LaunchModDevMode.bat` → F1 menu shows WF_ units in 11ACR deck

---

## May 2026 Updates & Enhancements (Implemented by Antigravity)

- **Vanilla Localisation Loading**: Configured [app.py](file:///g:/Project/wif-ag-tool/src/wif_ag_tool/web/app.py) to load vanilla names from the game's `Mods/ExampleAssets/Localisation/UNITS.csv` first and merge them with WIF's custom CSV. This resolves vanilla deck and unit name tokens to friendly display names and eliminates UI warning badges.
- **Role Fallback SVG Icons**: Implemented a CSS SVG role-based fallback system in [ui.html](file:///g:/Project/wif-ag-tool/src/wif_ag_tool/web/static/ui.html). If a unit's PNG thumbnail is missing from the local mod folder, the image gracefully hides to reveal a clean centered military silhouette matching the unit's role (Tank, Helicopter, Fighter Jet, Soldier, APC, Howitzer, AA, Recon, Supply, Engineer).
- **Catalogue Load Refresh**: Modified the asynchronous unit catalog loading to trigger `render()` once complete, ensuring assets display immediately upon page load.
- **WIF Combat Group Grouping & Name Formatting**:
  - Added support for grouping multiple WIF assignments under specific combat groups (like `"A"`, `"B"`, `"C"`, `"HQ"`) by adding `group_name` to `Assignment` in [models.py](file:///g:/Project/wif-ag-tool/src/wif_ag_tool/models.py).
  - Modified [group_generator.py](file:///g:/Project/wif-ag-tool/src/wif_ag_tool/generator/group_generator.py) to generate single grouped combat group descriptors bundling all assignments for the same group.
  - Implemented automatic sorting and grouping in [pipeline.py](file:///g:/Project/wif-ag-tool/src/wif_ag_tool/pipeline.py) and [localisation.py](file:///g:/Project/wif-ag-tool/src/wif_ag_tool/generator/localisation.py) to prevent NDF/CSV sequence mismatch.
  - Added UI grid support for the group dropdown and dynamically populated valid group choices in [ui.html](file:///g:/Project/wif-ag-tool/src/wif_ag_tool/web/static/ui.html).
  - Prettified raw NDF combat group descriptors in the UI to display clean, user-friendly names (e.g. `Descriptor_CombatGroup_pion_US_22TFS_A_22nd_TFS` -> `A-22ND TFS` and `US_22TFS_WIF_A` -> `WIF — A`).

*Credits: Designed & developed with ❤️ by **Antigravity**, your agentic AI coding companion from Google DeepMind's Advanced Agentic Coding team.*
