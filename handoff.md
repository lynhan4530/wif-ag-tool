# Handoff & Diagnosis Guide — WARNO WIF-AG Tool

This document provides a comprehensive overview of the **WIF AG Tool** project, outlines the current state, diagnoses why the mod crashes on your friend's PC but works on yours, and details a robust, universal fix for any user of this tool.

---

## 1. Project Goal & Overview

The **WIF AG Tool** is a Python web/CLI application that allows users to interactively map modern units from the *World in Flames (WIF)* mod into the campaign decks of WARNO's *Army General (AG)* campaigns. 
After assigning units (replicas), the tool generates NDF patches and compiles a self-contained WARNO mod.

### Key Commands:
*   **Run Dev Server**: `python -m wif_ag_tool serve` (Launches Flask UI on `http://localhost:5000`)
*   **Run Test Suite**: `.venv\Scripts\pytest` (Runs 130 unit/integration tests)
*   **Re-parse Decks**: `python -m wif_ag_tool refresh` (Updates `.deck_cache.json` from vanilla NDF files)
*   **Direct Export**: Executed via the **📥 Export Mod** button on the UI, which calls the POST `/api/sessions/<slug>/export_direct` endpoint to mutate NDFs in-place.
*   **Compile Mod**: Executed via the **⚡ Build Mod** button on the UI, which triggers Eugen's `GenerateMod.bat`.

---

## 2. The Current Problem: Mod Crashes on Friend's PC

*   **Symptom**: On your machine, the mod builds and loads perfectly. On your friend's machine, the mod compiles successfully, but the game crashes on startup (at the main menu loading screen).
*   **Root Cause**: Stale/Outdated `.orig` baseline backups on the friend's PC.
*   **Detailed Explanation**:
    1. The tool uses a snapshotting system: on the first export, it copies the clean vanilla files (`StrategicDecks.ndf`, `StrategicPacks.ndf`, `StrategicCombatGroups.ndf`, and `PLATOONS.csv`) to `<filename>.<ext>.orig` backups.
    2. On every subsequent export, the tool restores from these `.orig` files before applying WIF additions to keep the process idempotent.
    3. To support game updates, the tool checks if `.orig` files are contaminated with old WIF descriptors. In `src/wif_ag_tool/web/api.py`, it does:
       ```python
       text = pristine.read_text(encoding="utf-8")
       if "_v_" in text or "_WIF_" in text or "WIF AG" in text:
           need_recreate = True
       ```
    4. **The Mismatch**: If a game patch updates the vanilla game files (like `StrategicDecks.ndf`), the friend's PC will have `.orig` files created under the *previous* game patch. Since those old `.orig` files do not contain WIF tags (`_v_`, `_WIF_`, etc.), `need_recreate` is evaluated as `False`, so they are **not** overwritten with the new vanilla files from the updated `base.zip`.
    5. The tool restores from the outdated `.orig` files (missing new division mappings and changes from the game patch) and patches them. 
    6. When compiled, the mod contains out-of-date game files that mismatch the updated game engine, triggering a crash at startup.
    7. On your machine, the `G:\Warno_mod\vanilla_recon\` developer folder exists, and the `.orig` files were clean or recreated, which is why it did not crash for you.

---

## 3. The Universal Fix: Robust Byte Comparison

To make the tool work perfectly for **every user**, we must modify the backup recreation logic in `src/wif_ag_tool/web/api.py` to compare the existing `.orig` file directly against the game's current vanilla bytes (`pristine_bytes`). 

If the bytes do not match (either because of WIF contamination or because a game update modified the baseline), the tool will automatically recreate the `.orig` file from `base.zip` or the game directory.

### Proposed Code Change:
Modify `src/wif_ag_tool/web/api.py` lines 318–329:

```diff
             if pristine_bytes is not None:
                 need_recreate = False
                 if not pristine.exists():
                     need_recreate = True
                 else:
                     try:
-                        text = pristine.read_text(encoding="utf-8")
-                        if "_v_" in text or "_WIF_" in text or "WIF AG" in text:
-                            need_recreate = True
+                        # If the .orig file bytes differ from the clean baseline, it is either dirty or outdated
+                        if pristine.read_bytes() != pristine_bytes:
+                            need_recreate = True
                     except Exception:
                         need_recreate = True
```

---

## 4. Friend's Step-by-Step Recovery Instructions (using Antigravity)

When your friend opens this project, they should instruct their Antigravity agent with the following steps:

1.  **Apply the Fix**: Update `src/wif_ag_tool/web/api.py` as shown in the diff above.
2.  **Verify the Code**: Run the test suite using `.venv\Scripts\pytest` to verify all 130 tests pass.
3.  **Delete Stale Backups**: Delete the old `.orig` files inside the mod directory:
    *   `G:\Program Files (x86)\Steam\steamapps\common\WARNO\Mods\WIFAG\GameData\Generated\Gameplay\Decks\StrategicDecks.ndf.orig`
    *   `G:\Program Files (x86)\Steam\steamapps\common\WARNO\Mods\WIFAG\GameData\Generated\Gameplay\Decks\StrategicPacks.ndf.orig`
    *   `G:\Program Files (x86)\Steam\steamapps\common\WARNO\Mods\WIFAG\GameData\Generated\Gameplay\Decks\StrategicCombatGroups.ndf.orig`
    *   `G:\Program Files (x86)\Steam\steamapps\common\WARNO\Mods\WIFAG\GameData\Localisation\WIFAG\PLATOONS.csv.orig`
4.  **Re-run the Exporter & Compiler**:
    *   Start the web tool: `python -m wif_ag_tool serve`
    *   Go to the web page, select the session, click **Export Mod** (which extracts fresh baselines from `base.zip` and patches them).
    *   Click **Build Mod** (or run `GenerateMod.bat` in the mod folder).
5.  **Test the Game**: Launch WARNO and load the mod. It will load successfully without crashing!
