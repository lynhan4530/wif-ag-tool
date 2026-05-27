# Handoff — WIFAG mod end-to-end test session

Last updated: 2026-05-28

## Where we are

We are mid-way through validating an end-to-end test of a `wif-ag-tool` export against a real WARNO mod (`WIFAG`). Tool-side bugs that blocked the build pipeline have been identified and fixed. The mod now builds cleanly with the AG patches included. The remaining open question is whether the slow first-load is a real bug or expected first-time AG state generation.

## Active mod under test

- Path: `G:\Program Files (x86)\Steam\steamapps\common\WARNO\Mods\WIFAG`
- Provenance: scaffolded via `Mods\CreateNewMod.bat WIFAG`, then merged with the WIF source tree from `G:\Project\A-World-In-Flames\` into `WIFAG\GameData\`. Internal `Localisation/A World in Flames/` and `ResourcePacks/A World in Flames/` were renamed to `WIFAG/`, and `ResourcePacks.ndf` was updated to match.
- Verified clean bare-WIF build produces `Gen\NDF\GFX\Deck.ndfbin` (~1,237 KB).
- Verified WIF units appear in the in-game Armory when this mod is active.

## Replica / patch under test

- Tool session: `centag-day-1`.
- One deck modified: `Descriptor_Deck_pion_US_11ACR_1` (vanilla 149 packs → 206 after patch).
- 52 unique strategic packs added across the deck's combat groups (M3A3 Bradley CFV variants, Mech Rifles, M1A2 SEPV2 Abrams, M109A6, etc.).
- Currently exported to disk:
  - `WIFAG\GameData\Generated\Gameplay\Decks\StrategicPacks.ndf` — 52 new `Descriptor_StrategicPack_WF_*` blocks under a `// === WIF AG additions ===` banner.
  - `WIFAG\GameData\Generated\Gameplay\Decks\StrategicCombatGroups.ndf` — new `Descriptor_CombatGroup_*_WIF_*` blocks for the deck.
  - `WIFAG\GameData\Generated\Gameplay\Decks\StrategicDecks.ndf` — `DeckPackList` and `DeckCombatGroupList` for `US_11ACR_1` mutated in place to reference the new packs/groups (52 `WF_` refs).
  - `.orig` snapshots present for all three above (idempotent baseline for re-exports).
  - `WIFAG\GameData\Localisation\WIFAG\PLATOONS_additions.csv` — platoon name table.
- Last build: `GenerateMod.bat` succeeded, `Deck.ndfbin` now 1,277 KB (≈40 KB bump over bare-WIF baseline).

## What's been resolved

1. **Wrong export path.** The user's `export_dir` was originally set to the mod root, so files landed under `WIFAG\Generated\…` instead of `WIFAG\GameData\Generated\…`. Resolved by clearing `export_dir` in tool settings; the default `<target_mod_dir>/GameData` is correct.

2. **Mod scaffolding produced no `Deck.ndfbin`.** The first WIFxAG mod (created via Mod Editor as a thin patch mod) never compiled the strategic-deck NDFs. AGPatchTest builds them, so we forked AGPatchTest, confirmed pipeline worked, then re-forked with full WIF source so the compiled `Unit` descriptors are present in the mod itself. End result: the mod is now standalone — no dependency on a separately-loaded "A World in Flames" mod.

3. **Export wrote a plain-text `StrategicDecks_patch.ndf` instead of patching.** The tool was calling `generate_deck_patch()` (returns human-readable "paste these refs by hand" text). Fixed in `api.py` — now calls `apply_deck_patch()` which mutates `StrategicDecks.ndf` in place. Sidecar file renamed to `StrategicDecks_patch_summary.txt` (kept for diffing).

4. **Sidecar `_additions.ndf` files were ignored by the compiler.** The WARNO compiler only ingests the canonical base files. Fixed in `api.py` — new packs/combat groups are now appended directly into `StrategicPacks.ndf` and `StrategicCombatGroups.ndf`. The `.orig` snapshots make re-exports idempotent.

5. **Tool's ⚡ Build Mod button false-fails.** `GenerateMod.bat` ends with `PAUSE`. The tool's 90-second `subprocess.run` timeout kills the script while it's waiting on a keypress, producing a misleading "Mod compilation failed" banner even when the build actually succeeded. Workaround: run `GenerateMod.bat` from a real cmd window. (See "Open issues" below.)

## What broke and was recovered along the way

- User attempted "delete `Gen/` and rebuild" but accidentally wiped most of `GameData\Generated\` too. Restored from `GameData\Generated.bak\` (still present in the mod folder — leave it as a safety copy until we're confident the live `Generated/` is fully valid).
- An export-then-export-again loop with a stale server process produced triplicated `Descriptor_StrategicPack_WF_*` blocks (`Namespace opened twice` errors). Files restored from `.orig`; future re-exports are idempotent only if the tool server has been restarted to pick up the new code.

## Open issues

1. **First-load AG campaign is very slow.** With WIFAG (no patches) active, AG load on `US_11ACR_1` takes ~5 seconds. With the 52-pack patch applied, AG load was killed after 5+ minutes with no completion. CPU profile during the hang: one core pinned ~100%, disk at 0%, game window still animated, no error dialog. Unclear whether this is expected first-time AG strategic-state generation (one-time cost) or a pathological scaling issue. **Next test: re-export, rebuild, launch WARNO, walk away for 20–30 minutes without Alt+F4. If it eventually loads, subsequent launches should be cached.** Backup plan: shrink the replica to 1–2 units and verify a minimal patch loads quickly; scale up to find the threshold.

2. **`Build Mod` API timeout.** `subprocess.run(..., timeout=90)` in `api.py:build` is too short for a from-scratch build of a WIF-sized mod (first compile = 10–20 min) and also fights the trailing `PAUSE` in `GenerateMod.bat`. Options: (a) bump timeout to ~30 min and patch the bat to skip `PAUSE` when invoked from the tool, (b) stream the build process and detect "Mod Generation Success" instead of waiting for exit. Either way the false-failure banner should be addressed.

3. **`Generated.bak/` is still on disk** inside the live mod folder. Harmless to the build but adds ~130 MB. Delete once we're confident the live `Generated/` round-trips correctly through a full export/build cycle.

## How to resume

1. Make sure the tool server is on the latest code (commit `d9b68bb` or newer):
   ```
   cd G:\Project\wif-ag-tool
   git log -1 --oneline
   ```
   Then restart it via `Start-WIF-AG.bat`.
2. Open the tool, load the `centag-day-1` session, the `US_11ACR_1` replica is already saved.
3. Click **📥 Export Mod** once. The `.orig` snapshots will restore-then-patch idempotently.
4. Verify with:
   ```
   (Select-String -Path 'G:\Program Files (x86)\Steam\steamapps\common\WARNO\Mods\WIFAG\GameData\Generated\Gameplay\Decks\StrategicPacks.ndf' -Pattern '^Descriptor_StrategicPack_WF_').Count
   ```
   Should print `52` (or higher if multiple XP levels per assignment). If it's a multiple of 52 → server was not restarted, see issue (2) above.
5. Run `GenerateMod.bat` from cmd inside `WIFAG\` (do NOT use the in-tool Build Mod button until issue (2) is fixed).
6. Wait for `Mod Generation Success`, press any key.
7. Verify `WIFAG\Gen\NDF\GFX\Deck.ndfbin` got a fresh timestamp and is ≈1.28 MB (bare-WIF was 1.24 MB, patch adds ~40 KB).
8. Launch WARNO → tick **WIFAG only** → Apply → AG campaign on `US_11ACR_1` → **wait at least 20 minutes** before assuming it's wedged.
