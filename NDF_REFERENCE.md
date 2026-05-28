# NDF Reference — WARNO Army General Integration

Complete NDF syntax reference for the WIF AG Tool. Every code example here is
verified against real game files. Use this when writing parsers and generators.

---

## 1. File locations

### Source files (input — read only)

| Role | Path |
|------|------|
| WIF unit descriptors | `G:\Project\A-World-In-Flames\Generated\Gameplay\Gfx\UniteDescriptor.ndf` |
| WIF weapon descriptors | `G:\Project\A-World-In-Flames\Generated\Gameplay\Gfx\WeaponDescriptor.ndf` |
| WIF ammo | `G:\Project\A-World-In-Flames\Generated\Gameplay\Gfx\Ammunition.ndf` |
| WIF MP packs (reference) | `G:\Project\A-World-In-Flames\Generated\Gameplay\Decks\DeckPacks.ndf` |
| WIF UNITS.csv | `G:\Project\A-World-In-Flames\Localisation\A World in Flames\UNITS.csv` |
| WIF PLATOONS.csv | `G:\Project\A-World-In-Flames\Localisation\A World in Flames\PLATOONS.csv` |
| Vanilla StrategicDecks | `G:\Warno_mod\vanilla_recon\GameData\Generated\Gameplay\Decks\StrategicDecks.ndf` |
| Vanilla StrategicPacks | `G:\Warno_mod\vanilla_recon\GameData\Generated\Gameplay\Decks\StrategicPacks.ndf` |
| Vanilla CombatGroups | `G:\Warno_mod\vanilla_recon\GameData\Generated\Gameplay\Decks\StrategicCombatGroups.ndf` |
| Vanilla UniteDescriptor | `G:\Warno_mod\vanilla_recon\GameData\Generated\Gameplay\Gfx\UniteDescriptor.ndf` |

### Mod output files (append-only)
These live inside the mod's source tree (whatever mod name is chosen):
```
<WARNO>\Mods\<ModName>\GameData\Generated\Gameplay\Decks\StrategicPacks.ndf
<WARNO>\Mods\<ModName>\GameData\Generated\Gameplay\Decks\StrategicCombatGroups.ndf
<WARNO>\Mods\<ModName>\GameData\Generated\Gameplay\Decks\StrategicDecks.ndf
<WARNO>\Mods\<ModName>\GameData\Localisation\<ModName>\PLATOONS.csv
```

### WARNO save files (campaign state — filename only)
`G:\Program Files (x86)\Steam\userdata\142459089\1611600\remote\*.sav3`

Example filenames:
```
Autosave - #US #SOV #medium{CENTAG - DAY 7} Highway 66.sav3
Autosave - #RFA #SOV #medium{CENTAG - DAY 1} Airborne Assault.sav3
Autosave - #UK_RFA #SOV #medium{CENTAG - DAY 4} The Left Hook.sav3
```
Save data is binary. Only the filename is human-readable.

---

## 2. UniteDescriptor.ndf — WF_ unit block structure

### File stats
- Size: 33.5 MB (WIF), 25 MB (vanilla)
- WIF units: **684 total** (`WF_` prefix), across US(163), RUS(268), FR(90), GER(61),
  BEL(37), DNR(25), NL(18), UK(16), LUX(5), SOV(1)
- Each unit is an `export Descriptor_Unit_* is TEntityDescriptor(...)` block

### Exact block layout (M1A2 SEPV2 at WIF line 706279)
```ndf
export Descriptor_Unit_WF_M1A2_SEPV2_Abrams_US is TEntityDescriptor
(
    DescriptorId       = GUID:{454ef2bc-ff1e-42fd-9c64-7988718c197d}
    ClassNameForDebug  = 'Unit_WF_M1A2_SEPV2_Abrams_US'
    ModulesDescriptors = [
        TTypeUnitModuleDescriptor
        (
            Coalition     = ECoalition/NATO
            MotherCountry = 'US'
            AcknowUnitTypes = [ ~/TAcknowUnitType_Tank, ]
        ),
        TFormationModuleDescriptor(TypeUnitFormation = 'Char'),
        TankFlagsModuleDescriptor,
        VehicleApparenceModuleDescriptor
        (
            MimeticName  = "WF_M1A2_SEPV2_Abrams_US"
            BlackHoleKey = "WF_M1A2_SEPV2_Abrams_US"
            ReferenceMesh = $/GFX/DepictionResources/Modele_M1A2_SEPV2_Abrams_US
        ),
        $/GFX/Weapon/WeaponDescriptor_WF_M1A2_SEPV2_Abrams_US
,       TDamageModuleDescriptor
        (
            BlindageProperties = TBlindageProperties
            (
                ResistanceFront = TResistanceTypeRTTI(Family=ResistanceFamily_blindage Index=24)
                ResistanceSides = TResistanceTypeRTTI(Family=ResistanceFamily_blindage Index=8)
                ResistanceRear  = TResistanceTypeRTTI(Family=ResistanceFamily_blindage Index=5)
                ResistanceTop   = TResistanceTypeRTTI(Family=ResistanceFamily_blindage Index=3)
                ExplosiveReactiveArmor = False
            )
            HitRollECM = 0.0
        ),
        TGenericMovementModuleDescriptor
        (
            MaxSpeedInKmph = 65
            PathfindType   = $/Pathfind/PathfindTypes/Vehicle
        ),
        TCapaciteModuleDescriptor
        (
            DefaultSkillList = [
                $/GFX/EffectCapacity/Capacite_thermals2,
            ]
        ),
        TStrategicDataModuleDescriptor               ← REQUIRED for AG
        (
            UnitAttackValue          = 652
            UnitDefenseValue         = 497
            UnitBonusXpPerLevelValue = 1
        ),
        TUnitUIModuleDescriptor
        (
            PriceCategory = 'tank_A'
            UnitRole      = 'armor'
            SpecialtiesList = [
                '_smoke_launcher',
                'Thermals2',
            ]
            NameToken                 = 'WFM1ASV2'
            InfoPanelConfigurationToken = 'Default'
            DisplayRoadSpeedInKmph    = 75
            UpgradeFromUnit = Descriptor_Unit_WF_M1A2_SEPV2_Abrams_CMD_US
            MenuIconTexture           = 'Texture_RTS_H_Armor_heavy'
            ButtonTexture             = 'Texture_Button_Unit_M1A2_SEPV2'
            TypeStrategicCount        = ETypeStrategicDetailedCount/Armor_Heavy
        ),
    ]
)
```

### Key fields for the parser

| Field | Regex | Example value |
|-------|-------|---------------|
| Unit name | `^export (Descriptor_Unit_WF_\S+) is TEntityDescriptor` | `Descriptor_Unit_WF_M1A2_SEPV2_Abrams_US` |
| GUID | `GUID:\{([^}]+)\}` | `454ef2bc-ff1e-42fd-9c64-7988718c197d` |
| Nation | `MotherCountry\s*=\s*'(\w+)'` | `US` |
| Attack | `UnitAttackValue\s*=\s*(\d+)` | `652` |
| Defense | `UnitDefenseValue\s*=\s*(\d+)` | `497` |
| XP bonus | `UnitBonusXpPerLevelValue\s*=\s*(\d+)` | `1` |
| Role | `UnitRole\s*=\s*'(\w+)'` | `armor` |
| Name token | `NameToken\s*=\s*'(\w+)'` | `WFM1ASV2` |
| Specialties | Inside `SpecialtiesList\s*=\s*\[([^\]]*)\]` | `['_smoke_launcher', 'Thermals2']` |

### Splitting blocks
Each block starts at a line matching `^export Descriptor_Unit_WF_` and ends just before
the next such line (or EOF). Block boundaries are top-level export lines only.

---

## 3. StrategicPacks.ndf — DeckPackDescriptor

### Without transport (most WF_ combat units)
```ndf
Descriptor_StrategicPack_WF_M1A2_SEPV2_Abrams_US_1 is DeckPackDescriptor
(
    Xp   = 1
    Unit = $/GFX/Unit/Descriptor_Unit_WF_M1A2_SEPV2_Abrams_US
)
```

### With transport (infantry in APC)
```ndf
Descriptor_StrategicPack_WF_Rifles_CMD_US_1 is DeckPackDescriptor
(
    Xp        = 1
    Transport = $/GFX/Unit/Descriptor_Unit_WF_Stryker_ICV_US
    Unit      = $/GFX/Unit/Descriptor_Unit_WF_Rifles_CMD_US
)
```

### Without XP (Xp=0 or absent, for support/supply)
```ndf
Descriptor_StrategicPack_M113A1B_BEL_Rifles_AT_BEL_0 is DeckPackDescriptor
(
    Transport = $/GFX/Unit/Descriptor_Unit_M113A1B_BEL
    Unit      = $/GFX/Unit/Descriptor_Unit_Rifles_AT_BEL
)
```

**Important distinctions:**
- `DeckPackDescriptor` — NO `T` prefix. Not `TDeckPackDescriptor`.
- AG packs (StrategicPacks.ndf) have NO `Number` field.
- MP packs (DeckPacks.ndf) DO have a `Number` field — don't confuse them.
- Pack naming: `Descriptor_StrategicPack_<UnitName>_<XP>`

### How AG encodes "recruitable count" (no `Number` field)
Because AG packs lack a `Number` field, the multi-copy semantics live in the **deck**, not the
pack. A pack provides *one* recruitable instance per `DeckPackList` slot it occupies. To make a
pack recruitable N times, the `~/Descriptor_StrategicPack_*` reference is duplicated N times
**consecutively** in `DeckPackList`, and the combat group's `(start_index, count)` tuple reads
that N-slot run. See Section 4 for the tuple invariant and Section 5 for the deck-side proof.

---

## 4. StrategicCombatGroups.ndf — TDeckCombatGroupDescriptor

### Real vanilla example (11ACR_4 group N, lines 409899–409947)
```ndf
Descriptor_CombatGroup_pion_US_11ACR_4_N_4_11th_ACR is TDeckCombatGroupDescriptor
(
    Name = "ADHGKXYYNT"
    SmartGroupList =
    [
        TDeckSmartGroupDescriptor
        (
            Name = "HGXGZRSJDO"
            PackIndexUnitNumberList =
            [
                (22,2),
            ]
        ),
        TDeckSmartGroupDescriptor
        (
            Name = "FCKVNCDEGV"
            PackIndexUnitNumberList =
            [
                (24,2),
            ]
        ),
        TDeckSmartGroupDescriptor
        (
            Name = "NGWQRHJXTX"
            PackIndexUnitNumberList =
            [
                (26,2),
            ]
        ),
        TDeckSmartGroupDescriptor
        (
            Name = "ZAOTDLDJOR"
            PackIndexUnitNumberList =
            [
                (28,2),
            ]
        ),
        TDeckSmartGroupDescriptor
        (
            Name = "TBGNDTPKJD"
            IsHQ = True
            PackIndexUnitNumberList =
            [
                (30,1),
                (31,1),
            ]
        ),
    ]
)
```

### For WIF unit additions — simpler structure (1 SmartGroup per XP level)
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

### Rules
- `Name` = exactly 10 uppercase chars, maps to PLATOONS.csv token
- `PackIndexUnitNumberList` tuples = `(start_index, count)` where `start_index` is 0-based in parent DeckPackList
- **`count` is the number of CONSECUTIVE `DeckPackList` slots to consume**, NOT a squad-size
  multiplier on a single pack ref. The engine reads exactly `count` entries starting at
  `start_index`. If `DeckPackList` doesn't have that many slots in range, the engine reads
  out-of-bounds garbage and the game crashes on first pawn click in that deck.
- **NEVER insert mid-list** — always append packs and use `next_index` for new packs
- `IsHQ = True` is optional, marks command unit

### Invariant: tuple-sum equals list-growth
For any new combat group your generator emits into a deck:
```
sum(count for (start_index, count) in all SmartGroups in this CombatGroup)
  == number of new ~/Descriptor_StrategicPack_* refs appended to DeckPackList for this group
```
Vanilla proof (`Descriptor_CombatGroup_pion_US_11ACR_1_A_*`):
`(0,6)+(6,2)+(8,4)+(12,6)+(18,2)+(20,4)+(24,2)+(26,1)+(27,1)+(28,2) = 30` matches the
30 slots that group A's contiguous run occupies in `DeckPackList`. Each subsequent group
(B, C, D, HQ) starts at the slot immediately after the previous group's last slot.

The export pipeline asserts this invariant per-deck (`pipeline._assert_pack_index_invariant`)
and refuses to write the export if it ever fails — defense in depth against future generator
regressions.

---

## 5. StrategicDecks.ndf — TDeckDescriptor

### Real example: Descriptor_Deck_pion_US_11ACR_4 (line 196376)
```ndf
export Descriptor_Deck_pion_US_11ACR_4 is TDeckDescriptor
(
    DeckIdentifier = 'pion_US_11ACR_4'
    DeckDivision   = $/GFX/Division/Descriptor_Deck_Division_US_11ACR_solo
    Superior       = $/UI/BattleOrder/US_11ACR_Subordination
    DeckPackList =
    [
        ~/Descriptor_StrategicPack_UH60A_Supply_US_2,       ← index 0
        ~/Descriptor_StrategicPack_UH60A_Supply_US_2,       ← index 1
        ~/Descriptor_StrategicPack_UH60A_Supply_US_2,       ← index 2
        ~/Descriptor_StrategicPack_UH60A_Supply_US_2,       ← index 3
        ~/Descriptor_StrategicPack_UH60A_Supply_US_2,       ← index 4
        ~/Descriptor_StrategicPack_UH60A_Supply_US_2,       ← index 5
        ~/Descriptor_StrategicPack_UH60A_Supply_US_2,       ← index 6
        ~/Descriptor_StrategicPack_UH60A_Supply_US_2,       ← index 7
        ~/Descriptor_StrategicPack_CH47_Super_Chinook_US_2, ← index 8
        ... (93 total packs, indices 0–92)
        ~/Descriptor_StrategicPack_UH60A_CO_US_2,           ← index 92
    ]
    DeckCombatGroupList =
    [
        ~/Descriptor_CombatGroup_pion_US_11ACR_4_HQ_4_11th_ACR,
        ~/Descriptor_CombatGroup_pion_US_11ACR_4_N_4_11th_ACR,
        ~/Descriptor_CombatGroup_pion_US_11ACR_4_O_4_11th_ACR,
        ~/Descriptor_CombatGroup_pion_US_11ACR_4_P_4_11th_ACR,
        ~/Descriptor_CombatGroup_pion_US_11ACR_4_Q_4_11th_ACR,
        ~/Descriptor_CombatGroup_pion_US_11ACR_4_R_4_11th_ACR,
        ~/Descriptor_CombatGroup_pion_US_11ACR_4_S_4_11th_ACR,
    ]
)
```

**`Descriptor_Deck_pion_US_11ACR_4` has 93 packs. `next_index = 93`.**

### AG vs MP distinction
- AG decks: `DeckDivision = .../Descriptor_Deck_Division_*_solo`
- MP decks: `DeckDivision = .../Descriptor_Deck_Division_*_multi`
- Only `_solo` decks appear in Army General campaigns.

### What to append (shown as patch)
```ndf
// Add to DeckPackList (before closing ]):
        ~/Descriptor_StrategicPack_WF_M1A2_SEPV2_Abrams_US_1,   // index 93
        ~/Descriptor_StrategicPack_WF_M1A2_SEPV2_Abrams_US_2,   // index 94
        ~/Descriptor_StrategicPack_WF_M1A2_SEPV2_Abrams_US_3,   // index 95

// Add to DeckCombatGroupList (before closing ]):
        ~/Descriptor_CombatGroup_pion_US_11ACR_4_WIF_WF_M1A2_SEPV2_Abrams_US,
```

---

## 6. PLATOONS.csv — localisation tokens

### Format
Semicolon-separated, double-quoted fields. No BOM. UTF-8.
```csv
"TOKEN";"REFTEXT"
"ADHGKXYYNT";"11th ACR Alpha"
"A3F9B2C1D4";"WIF M1A2 SEPV2"
```

- Every `Name` field in `TDeckCombatGroupDescriptor` and `TDeckSmartGroupDescriptor`
  must have a row here or the game logs a missing-token warning.
- Token is exactly **10 uppercase alphanumeric chars** (the game enforces length).
- Tokens in the fixture files use repeated letters (`AAAAAAAAAA`) for clarity — real tokens
  should be MD5-based (see token_gen.py spec in CLAUDE.md).

---

## 7. WIF unit catalogue — key AG-relevant units by nation

### US (163 units, maps to vanilla `pion_US_*` decks)

| Unit name | Role | ATK | DEF | Notes |
|-----------|------|-----|-----|-------|
| `WF_M1A2_SEPV2_Abrams_US` | armor | 652 | 497 | Main MBT |
| `WF_M1A2_SEPV2_ERA_Abrams_US` | armor | ~680 | ~520 | ERA variant |
| `WF_M1A2_SEPV3_Abrams_US` | armor | 720 | 535 | Top-tier MBT |
| `WF_M1A2_SEPV3_ERA_Abrams_US` | armor | ~750 | ~560 | ERA variant |
| `WF_M1A1HA_Abrams_US` | armor | ~420 | ~320 | Interim HA |
| `WF_M1A1SA_Abrams_US` | armor | ~380 | ~290 | SA variant |
| `WF_M2A4_Bradley_US` | ifv | 171 | 86 | IFV (fully researched) |
| `WF_M2A3_Bradley_2B_US` | ifv | ~140 | ~70 | Previous gen |
| `WF_AH64_Apache_E_US` | helicopter | ~245 | ~110 | AH-64E |
| `WF_AH64_Apache_Longbow_US` | helicopter | ~230 | ~100 | D Longbow |
| `WF_M109A6_US` | artillery | ~89 | ~42 | M109A6 Paladin |
| `WF_M109A6_Excalibur_US` | artillery | ~110 | ~42 | PGM variant |
| `WF_M270A1_GMLRS_US` | artillery | ~120 | ~35 | MLRS |
| `WF_HIMARS_GMLRS_US` | artillery | ~95 | ~30 | HIMARS |
| `WF_Stryker_MGS_US` | armor | ~180 | ~90 | MGS |
| `WF_Stryker_ICV_US` | ifv | ~80 | ~40 | APC |
| `WF_F15E_StrikeEagle_US` | plane | ~320 | ~180 | Strike |
| `WF_F15C_Eagle_AA_US` | plane | ~280 | ~160 | Air superiority |

### RUS (268 units, maps to vanilla `pion_SOV_*` decks)

| Unit name | Role | ATK | DEF | Notes |
|-----------|------|-----|-----|-------|
| `WF_T14_RUS` | armor | ~900 | ~700 | Armata MBT (top) |
| `WF_T90M_RUS` | armor | 580 | 440 | T-90M |
| `WF_T90M_ERA_RUS` | armor | ~600 | ~460 | ERA variant |
| `WF_T90M_ARENA_RUS` | armor | ~620 | ~480 | APS variant |
| `WF_T90A_RUS` | armor | ~520 | ~390 | T-90A |
| `WF_T80BVM_RUS` | armor | ~560 | ~430 | T-80BVM |
| `WF_T72B3M_RUS` | armor | ~380 | ~290 | T-72B3M |
| `WF_T15_RUS` | ifv | ~300 | ~200 | Armata IFV |
| `WF_BMP_3_ERA_RUS` | ifv | ~160 | ~80 | BMP-3 ERA |
| `WF_BMPT_RUS` | ifv | ~280 | ~200 | Terminator |
| `WF_Ka_52_RUS` | helicopter | ~280 | ~130 | Ka-52 |
| `WF_MI_28NM_RUS` | helicopter | ~270 | ~125 | Mi-28NM |
| `WF_2S35_RUS` | artillery | ~140 | ~50 | Koalitsiya |
| `WF_2S19M2_MstaS_RUS` | artillery | ~100 | ~45 | Msta-S |
| `WF_Pantsir_S1_RUS` | aa | ~200 | ~90 | SPAAG |
| `WF_Su_57_AA1_RUS` | plane | ~400 | ~220 | Su-57 (top) |
| `WF_Su_34_AT_RUS` | plane | ~310 | ~170 | Su-34 |

### FR (90 units, maps to `pion_FR_*`)
- `WF_Leclerc_XLR_FR`, `WF_VBCI_FR`, `WF_EBRC_FR`, `WF_CAESAR_FR`

### GER (61 units, maps to `pion_RFA_*`)
- Leopard 2A7+, Puma IFV, Tiger UHT variants — check UniteDescriptor for exact names

---

## 8. Vanilla AG division coverage

### Nations with both vanilla AG decks AND WIF units

| Vanilla code | AG decks | WIF nation code | WIF units |
|---|---|---|---|
| `US` | 233 | `_US` | 163 |
| `SOV` | 506 | `_RUS` | 268 |
| `FR` | 113 | `_FR` | 90 |
| `RFA` | 399 | `_GER` | 61 |
| `BEL` | 53 | `_BEL` | 37 |
| `NL` | 69 | `_NL` | 18 |
| `UK` | 99 | `_UK` | 16 |

### Nations with vanilla AG decks but NO WIF units
`POL` (233), `RDA` (238), `TCH` (227), `ESP` (20), `CAN` (17)

---

## 9. Modding toolchain commands (bundled with WARNO)

The scripts below ship inside the WARNO install — there is no separate "Mod Editor" download. Run them from:
```
G:\Program Files (x86)\Steam\steamapps\common\WARNO\Mods\
```
(Compiler binaries — `AssetCooker.exe`, `DataPacker.exe`, etc. — live next door in `<WARNO>\Tools\`. Eugen's own `modding_manual.pdf` and `ndf_reference_manual.pdf` also ship in `<WARNO>\Mods\`.)

| Command | What it does |
|---------|-------------|
| `CreateNewMod.bat <ModName>` | Extract base.zip into new mod folder |
| `GenerateMod.bat` | Compile .ndf source → .ndfbin binaries |
| `LaunchModDevMode.bat` | Launch game with mod + F1 debug spawn menu |
| `UpdateMod.bat` | 3-way merge after WARNO patch (resolves conflicts) |
| `UploadMod.bat` | Push to Steam Workshop |

### Lazy compilation
`GenerateMod.bat` only emits `.ndfbin` packages for source files that differ from `base.zip`.
A mod touching only StrategicDecks.ndf produces exactly one output: `Gen/NDF/GFX/Deck.ndfbin`.

### Config.ini fields (mod runtime config)
Located at `C:\Users\lynha\Saved Games\EugenSystems\WARNO\mod\<ModName>\Config.ini`
```ini
[Config]
Version = 1                  ; bump on gameplay changes
DeckFormatVersion = 1        ; must be >= 1; bumping invalidates all saves
CosmeticOnly = 0             ; 0 = gameplay mod (required for AG content)
```

### Package collision rule
WARNO hard-refuses two active mods that modify the same compiled package.
Any mod touching StrategicDecks.ndf compiles into `GFX/Deck` — same package CRMxWIF ships.
**This is why we fork WIF instead of patching it.** One mod = no collision.

---

## 10. CRMxWIF architecture context

`CRMxWIF = CRM (chinofchrist's realism tuning) + WIF (etouffement's modern units)`

- **WIF source** is available at `G:\Project\A-World-In-Flames` — this is what the tool uses
- **CRM source** is NOT available (chinofchrist hasn't shared it)
- CRM tweaks vanilla unit stats (M1A1 Abrams, M2A2 Bradley, etc.) — not needed for AG
- WIF provides the `WF_` modern units — that's what we add to AG decks
- Our mod = WIF source + AG chain additions. Vanilla unit stats remain vanilla.

---

## 11. Key gotchas

1. **PackIndexUnitNumberList uses 0-based index in DeckPackList** — not the pack name.
   Reorder or insert mid-list → all combat groups silently break.
   **Always append. Never insert.**

1b. **`(start_index, count)` is a CONSECUTIVE RUN, not a multiplier on one pack ref.**
   `count=6` means the engine reads 6 DeckPackList entries starting at `start_index`.
   So a SmartGroup with `(start, 6)` requires 6 consecutive `~/Descriptor_StrategicPack_*`
   entries in DeckPackList — usually the same ref duplicated 6×. Emitting `(start, 6)` next
   to a single pack ref makes the engine read 5 unrelated entries; at the deck's end this
   reads out-of-bounds and crashes the pawn-click UI. (Bug fixed 2026-05-28; regression
   guarded by `tests/test_generator.py::test_gen_combat_group_count_emits_consecutive_run_tuple`.)

2. **`_solo` vs `_multi`** — AG uses `_solo` divisions; MP uses `_multi`.
   Wrong suffix = broken deck with no error message.

3. **`DeckPackDescriptor` has no `T` prefix** — it's not `TDeckPackDescriptor`.

4. **AG packs have no `Number` field** — that's MP-only.

5. **`DeckFormatVersion >= 1`** required for gameplay mods. New mod skeleton starts at 0.

6. **Save files break on every `DeckFormatVersion` bump.** Expected behavior.

7. **WIF's `TStrategicDataModuleDescriptor` values are already set** in every WF_ unit.
   These are higher than vanilla (e.g. M1A2 SEPV2 = 652 vs vanilla M1A1 = ~211).
   This is intentional WIF balance — within-WIF comparisons are what matter for AG autoresolve.

8. **Token length is exactly 10 chars** — game enforces this for PLATOONS.csv tokens.
   The MD5 approach (first 10 hex chars uppercased) always produces valid tokens.
