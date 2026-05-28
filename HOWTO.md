# How To — End-to-End Guide

This is the full walkthrough: scaffold a fresh WARNO mod, merge the WIF source into it, build a replica deck in the tool, export the patches, compile, and run the mod in-game. Follow it top-to-bottom the first time; later runs only need steps 5 onward.

> **Prerequisite check.** You need WARNO installed, the official WARNO Mod Editor installed alongside it, the WIF source tree at `G:\Project\A-World-In-Flames\` (or your own path — adjust as you go), and Python 3.10+ with this tool's dependencies (`pip install -r requirements.txt`). If you skipped these, the rest of this guide will fail.

---

## Step 1 — Scaffold a new mod

The mod has to be a **full-content** mod, not a thin patch — WIF's `WF_*` unit descriptors must live inside the mod folder itself or the campaign engine will silently fall back to vanilla.

1. Open a Command Prompt in `<WARNO Mod Editor>\Mods\` — the path is typically:
   ```
   G:\Program Files (x86)\Steam\steamapps\common\WARNO Mod Editor\Mods\
   ```
2. Run:
   ```
   CreateNewMod.bat CRM_ArmyGeneral
   ```
   (Replace `CRM_ArmyGeneral` with any name you want — call it `Your_AG_Mod` if you prefer. The rest of this guide uses `CRM_ArmyGeneral` as the running example.)
3. Confirm the new folder exists and contains `GenerateMod.bat`, `Config.ini`, and an initial `GameData\` subtree.
4. Open `Config.ini` and confirm/set:
   ```ini
   [Config]
   Version = 1
   DeckFormatVersion = 1
   CosmeticOnly = 0
   ```
   `CosmeticOnly = 0` is mandatory for any mod that touches gameplay (Army General decks are gameplay).

---

## Step 2 — Copy WIF units into the mod

This is the "full-content, not patch-only" rule from [CLAUDE.md](CLAUDE.md). The mod folder needs every `WF_*` descriptor file, not just a patch that references them.

1. Locate the WIF source repo, e.g. `G:\Project\A-World-In-Flames\`.
2. Copy the entire `GameData\` subtree from WIF into your new mod, **overwriting** the skeleton:
   ```
   COPY: G:\Project\A-World-In-Flames\GameData\*
   INTO: <Mods>\CRM_ArmyGeneral\GameData\
   ```
   Make sure `UniteDescriptor.ndf`, `WeaponDescriptor.ndf`, `Ammunition.ndf` and the rest end up under `<mod>\GameData\Generated\Gameplay\Gfx\`.
3. Rename the localisation folder so it matches the mod name:
   ```
   FROM: <mod>\GameData\Localisation\A World in Flames\
   TO:   <mod>\GameData\Localisation\CRM_ArmyGeneral\
   ```
   (And rename `<mod>\GameData\ResourcePacks\A World in Flames\` the same way.)
4. Open `<mod>\GameData\Generated\Gameplay\Decks\ResourcePacks.ndf` (or wherever `ResourcePacks.ndf` lives in your tree) and rewrite every `A World in Flames` path to `CRM_ArmyGeneral`.

End state: a self-contained ~5 GB mod folder. No "co-activate WIF too" requirement at runtime.

---

## Step 3 — Start the tool

1. From the `wif-ag-tool` repo root, double-click **`Start-WIF-AG.bat`** (or run `python -m wif_ag_tool serve` in a terminal).
2. Open <http://127.0.0.1:5000> in a browser.
3. You should see the campaign picker. If it's empty, that's fine for now — you can create a manual session in Step 4.

---

## Step 4 — Create a session and point the tool at your mod

A **session** is the tool's per-campaign workspace. It stores which nations are in scope and where your mod lives.

1. On the campaign picker, click an existing campaign (auto-detected from your WARNO `.sav3` files) **or** click `+ New session (manual)` and give it a name + faction list like `US,SOV` or `RFA,RDA`.
2. Once the session opens, click **⚙ Settings** in the header and fill in:
   - **WIF Mod Folder** → the mod folder from Step 1, e.g. `G:\Program Files (x86)\Steam\steamapps\common\WARNO Mod Editor\Mods\CRM_ArmyGeneral`.
   - **Game Folder** → your base WARNO install path.
   - **Export Folder** → **leave empty**. The default `<mod>\GameData` is the only path the WARNO compiler reads from; overriding it almost always breaks the build.
3. Save the settings.

---

## Step 5 — Refresh the deck cache

The tool ships with a cached parse of vanilla `StrategicDecks.ndf`, but you should refresh it once against your installed game so the indices line up with whatever patch level you're on.

- Click **Refresh decks** in the header, **or** run `python -m wif_ag_tool refresh` in a terminal.
- A successful refresh updates `data/.deck_cache.json` and the deck list in the left pane.

Do this again any time WARNO patches and `UpdateMod.bat` resolves new vanilla conflicts.

---

## Step 6 — Build a WIF replica for a deck

This is where you actually decide what WIF units land in which Army General deck.

1. **Pick a deck** in the left pane (e.g. `pion_US_11ACR_1` = 1-11th ACR battalion in the 11th ACR campaign deck). The center pane shows the vanilla composition for reference; the right pane is your replica.
2. **Add Combat Groups** in the replica panel with `+ Add Group`. Vanilla AG decks usually have `A`, `B`, `C`, `D`, `HQ` — match that or invent your own (`E`, `F`, etc.).
3. **Add Platoons** inside a group with `+ Add Platoon`. The Platoon Picker shows authentic vanilla names extracted from this deck plus standard fallbacks (`HQ`, `1`, `2`, `SPT`, custom). The name you pick drives the in-game platoon header.
4. **Add Units** inside a platoon with `+ Add Unit`. For each unit:
   - Pick the `WF_*` unit from the catalog (filter by role, search by name).
   - Set **XP level(s)** — 1 / 2 / 3 are common. Each XP level becomes a separate strategic pack.
   - Set **count** — how many recruitable copies of this pack the platoon gets per pawn (e.g. `6` for a Bradley squad).
   - Optionally set a **transport** override (e.g. `WF_M2A4_Bradley_US` for a Rifles squad).
5. **Reorder** with drag-and-drop until the platoon and group layouts match what you want.
6. **Save session** in the header once you're happy. The replica is now persisted in `data/wif_replicas.json` and survives restarts.

> Replicas are **global, not per-session** — each deck has at most one saved replica, shared across all sessions. That's why a friend working on Red-team decks doesn't conflict with you working on Blue-team decks: as long as your scopes don't overlap, your `wif_replicas.json` files can be merged by simple dict union.

---

## Step 7 — Export the patches into the mod

1. Click **📥 Export Mod** in the header.
2. The tool will:
   - Snapshot `StrategicDecks.ndf`, `StrategicPacks.ndf`, `StrategicCombatGroups.ndf` to `*.ndf.orig` on first run (idempotency safety net).
   - Restore from `.orig` and re-apply your replicas in place on every subsequent run.
   - Append `Descriptor_StrategicPack_*` blocks to `StrategicPacks.ndf` under a `// === WIF AG additions ===` banner.
   - Append `Descriptor_CombatGroup_*` blocks to `StrategicCombatGroups.ndf` the same way.
   - Insert `~/Descriptor_StrategicPack_*` and `~/Descriptor_CombatGroup_*` refs into each patched deck's `DeckPackList` / `DeckCombatGroupList`.
   - Write `PLATOONS_additions.csv` into `<mod>\GameData\Localisation\<ModName>\PLATOONS_additions.csv`.
   - Verify a runtime invariant: `sum(SmartGroup counts) == DeckPackList growth` per deck (see [NDF_REFERENCE.md §4](NDF_REFERENCE.md)). If it ever fails, the export aborts with an error rather than writing a crash-bait file.

If anything goes wrong, the response surfaces the failing deck name and reason.

> **Never delete `.ndf.orig` files** while the live files still contain WIF additions — the next export would treat your additions as the new "vanilla" baseline and lock them in permanently.

---

## Step 8 — Compile the mod

1. Click **⚡ Build Mod** in the header. The browser opens a console-log modal and runs `GenerateMod.bat` inside your mod folder.
2. Watch the log for `Mod Generation Success`.
3. **Big caveat for first builds:** `GenerateMod.bat` ends with `PAUSE` waiting for a keypress, and a full WIF-sized first build takes 10–20 minutes. The in-tool button frequently reports a false "Mod compilation failed" even when the build actually succeeded. **For first builds**, run `GenerateMod.bat` from a real cmd window so you can see the entire log and hit a key at the end. Subsequent incremental builds usually finish well under the 300s in-app timeout.

---

## Step 9 — Run the mod in WARNO

1. Launch WARNO. (Optionally use `LaunchModDevMode.bat` from `<WARNO Mod Editor>\Mods\` to start with F1 spawn-menu debug.)
2. Enable your mod under `Game → Mods`.
3. Start or load an Army General campaign that includes one of the decks you modified.
4. Click the pawn that uses your modified deck. The composition UI should open and show your WIF units in the groups / platoons / counts you configured.

If the pawn click crashes the game: it means the export wrote a `(start_index, count)` tuple that points past the deck's `DeckPackList`. This bug class was fixed on 2026-05-28; if you're seeing it again, you're either running an old build of this tool (commit older than `84f0efa`) or you bypassed the export-time invariant. Re-pull `main`, re-export, re-build, and run again.

---

## Update workflow (after a WARNO game patch)

When WARNO ships a new patch:

1. Run `UpdateMod.bat` from `<Mods>\CRM_ArmyGeneral\` (or wherever your mod lives). The Mod Editor resolves vanilla NDF conflicts in a 3-way merge.
2. In the tool, click **Refresh decks** (or run `python -m wif_ag_tool refresh`). This re-parses `StrategicDecks.ndf` so the pack indices line up with the new vanilla baseline.
3. **📥 Export Mod** → **⚡ Build Mod** as in Steps 7-8.
4. Re-check the pawn click in WARNO as in Step 9.

---

## Collaborating with a teammate (red-team / blue-team split)

The replica storage (`data/wif_replicas.json`) is keyed by deck descriptor name, and AG deck names embed the nation prefix (`pion_US_*`, `pion_SOV_*`, `pion_RDA_*`, etc.). So if you and a friend split by faction (you do NATO, he does Warsaw Pact), your saved keys are disjoint and merging is trivial.

Recommended workflow:

1. Both clone the repo and pull `main` so the generator agrees byte-for-byte.
2. Each person sets their session's **Nation scope** to their side and edits only those decks.
3. To merge: share each other's `data/wif_replicas.json`, then dict-union them (`{**mine, **his}`) into the machine that will run the build. There's no schema-level conflict unless you both saved the same deck.
4. Build the mod on **one** machine — only that machine sees the union of replicas.

A built-in import endpoint may land later; until then, the manual merge takes ~10 seconds and is the simplest path.

---

## Quick reference

| Step | Action | Time |
|---|---|---|
| 1 | `CreateNewMod.bat <Name>` | ~10 s |
| 2 | Copy WIF source into `<mod>\GameData\` | ~2 min (copy time) |
| 3 | Start the tool | ~5 s |
| 4 | Configure mod + game paths in Settings | ~30 s |
| 5 | Refresh deck cache | ~5 s |
| 6 | Build replicas (per deck) | varies, often 5-30 min for a real battalion |
| 7 | 📥 Export Mod | <5 s |
| 8 | ⚡ Build Mod | 30 s incremental, 10-20 min first build |
| 9 | Launch + click the pawn in WARNO | depends on you |

For deeper reference material:
- [CLAUDE.md](CLAUDE.md) — engineering decisions and constraints.
- [NDF_REFERENCE.md](NDF_REFERENCE.md) — NDF file formats and the SmartGroup tuple invariant.
- [handoff.md](handoff.md) — postmortem of the 2026-05-28 pawn-click crash that motivated the runtime invariant check.
