# How To — Mod WARNO Army General with WIF Units

This walks you from "nothing set up" to "I just clicked my modded pawn in-game and it worked." Read it top to bottom the first time. Once you've shipped a build, you only really care about Steps 5 onward.

## What you need before you start

- WARNO installed via Steam. The modding scripts (`CreateNewMod.bat`, `GenerateMod.bat`, `UpdateMod.bat`) and the NDF compiler all ship inside the WARNO install folder — you don't need to download anything extra.
- The WIF source tree somewhere on disk. Mine is at `G:\Project\A-World-In-Flames\`; yours might be wherever you cloned it.
- Python 3.10 or newer, and this tool's dependencies (`pip install -r requirements.txt` in the repo root).

That's it. If you've got those, the rest of this guide just works.

---

## Step 1 — Make a new mod

The Army General campaign won't load WIF units from a "patch only" mod that depends on WIF being co-activated — that path silently falls back to vanilla and you'll spend an hour debugging nothing. The mod has to carry the WIF unit descriptors itself.

Open a command prompt here:

```
G:\Program Files (x86)\Steam\steamapps\common\WARNO\Mods\
```

You'll find Eugen's `modding_manual.pdf` and `ndf_reference_manual.pdf` in that folder too if you ever want the dry reference. Run:

```
CreateNewMod.bat CRM_ArmyGeneral
```

Pick whatever name you like — I'm using `CRM_ArmyGeneral` for the rest of the guide. It'll create a new folder next to the script with `GenerateMod.bat`, `Config.ini`, and an empty-ish `GameData\` subtree.

Open `Config.ini` and make sure it looks like this:

```ini
[Config]
Version = 1
DeckFormatVersion = 1
CosmeticOnly = 0
```

`CosmeticOnly = 0` is the only one that really matters — Army General is gameplay, so if you leave it at 1 the game will refuse to load your campaign decks.

---

## Step 2 — Drop WIF into the mod

This is the "carry the descriptors yourself" part. Copy the entire `GameData\` folder out of the WIF source tree and into your new mod, overwriting the skeleton:

```
FROM: G:\Project\A-World-In-Flames\GameData\*
INTO: G:\Program Files (x86)\Steam\steamapps\common\WARNO\Mods\CRM_ArmyGeneral\GameData\
```

It's about 5 GB so go make coffee.

When the copy finishes, you've still got two folders named `A World in Flames` to deal with. Rename both of them to match your mod name:

```
<mod>\GameData\Localisation\A World in Flames\    →   <mod>\GameData\Localisation\CRM_ArmyGeneral\
<mod>\GameData\ResourcePacks\A World in Flames\   →   <mod>\GameData\ResourcePacks\CRM_ArmyGeneral\
```

Then open `<mod>\GameData\Generated\Gameplay\Decks\ResourcePacks.ndf` (or wherever `ResourcePacks.ndf` lives in your tree) and find-replace every `A World in Flames` path with your mod name. Save.

That's all the manual file-pushing you'll ever do.

---

## Step 3 — Start the tool

From the `wif-ag-tool` repo root, double-click `Start-WIF-AG.bat`. (Or run `python -m wif_ag_tool serve` if you'd rather see the log in a terminal.)

Open <http://127.0.0.1:5000> in a browser. You should land on the campaign picker.

---

## Step 4 — Point the tool at your mod

Pick a campaign from the list (the tool auto-detects them from your WARNO save files) or click **+ New session (manual)** and type a name + the factions you care about, like `US,SOV` or `RFA,RDA`.

Once the session opens, hit **⚙ Settings** at the top and fill in:

- **WIF Mod Folder** — the mod folder from Step 1, e.g. `G:\Program Files (x86)\Steam\steamapps\common\WARNO\Mods\CRM_ArmyGeneral`.
- **Game Folder** — wherever WARNO itself is installed.
- **Export Folder** — leave this blank. Seriously, the default is the only path the compiler actually reads from. Override it only if you know what you're doing.

Save.

---

## Step 5 — Refresh the deck cache

The tool caches a parse of vanilla `StrategicDecks.ndf` so it knows what every campaign deck looks like before you start touching it. After a fresh install — or any time WARNO gets patched — click **Refresh decks** in the header (or run `python -m wif_ag_tool refresh`). Takes a few seconds.

Skip this and your pack indices will line up with the wrong baseline. Don't skip this.

---

## Step 6 — Build a replica deck

This is the part you'll spend most of your time in. Pick a deck on the left (`pion_US_11ACR_1` is the 1-11th ACR battalion if you want a concrete example). The middle pane shows the vanilla composition so you can see what you're replacing; the right pane is yours to fill in.

Work top-down:

1. **Add a Combat Group** (`+ Add Group`). Vanilla decks usually run `A`, `B`, `C`, `D`, `HQ` — match that or invent your own. The group letter shows up in-game.
2. **Add a Platoon** inside it (`+ Add Platoon`). The picker offers the authentic platoon names pulled out of this specific deck — pick one of those if you want it to feel native, or roll your own.
3. **Add Units** inside the platoon (`+ Add Unit`). For each unit:
   - Pick the `WF_*` unit from the catalog. Filter by role, search by name.
   - Pick the **XP level(s)**. 1/2/3 are normal; each level becomes its own strategic pack so the player can recruit veterans separately from rookies.
   - Set the **count**. This is how many of that pack are recruitable per pawn. A Bradley platoon is 6, a tank platoon is usually 4, a Humvee section is 2.
   - Optional: pick a **transport**, e.g. give your rifles squad a Bradley to ride in.
4. **Drag** rows around to reorder. Drop units between platoons or groups if you mis-placed them.
5. Hit **Save session** in the header. Your work persists to `data/wif_replicas.json` and survives restarts.

Repeat for every deck you want to mod. The tool's left pane shows a badge on decks that already have a saved replica so you can tell what's done.

---

## Step 7 — Export the patches

Click **📥 Export Mod** in the header. The tool writes everything straight into your mod folder:

- Appends your new `Descriptor_StrategicPack_*` blocks to `StrategicPacks.ndf`.
- Appends your new `Descriptor_CombatGroup_*` blocks to `StrategicCombatGroups.ndf`.
- Splices `~/Descriptor_StrategicPack_*` and `~/Descriptor_CombatGroup_*` refs into each deck's `DeckPackList` and `DeckCombatGroupList`.
- Writes the platoon names into `PLATOONS_additions.csv`.

The first time it exports, it snapshots each of the three NDF files to a `.ndf.orig` sibling so every later export can roll back and re-apply cleanly. Don't delete those `.orig` files. If you delete them while the live files already have your additions in them, the next export thinks your additions are the new vanilla baseline and bakes them in permanently. Annoying to recover from.

The export also runs a sanity check: it makes sure the number of pack slots it claims in the combat groups matches the number of pack refs it actually appended to the deck. If those ever disagree, the export aborts loudly with the name of the bad deck instead of writing a file that'd crash WARNO on pawn click. You shouldn't see that error in normal use; if you do, save the message and ping me.

---

## Step 8 — Compile

Click **⚡ Build Mod**. A log console pops up and you'll watch `GenerateMod.bat` run. When it prints `Mod Generation Success` you're done.

Two practical notes:

- **The very first build of a full WIF-sized mod takes 10 to 20 minutes.** All 5 GB of source needs to compile. The in-tool button times out at 5 minutes and will tell you the build "failed" even when it didn't. For first builds, **open a real cmd window**, cd into your mod folder, run `GenerateMod.bat` yourself, and watch for the success line. Once you've done a successful first build, every subsequent build is incremental and finishes in 30 seconds — at that point the in-tool button is fine.
- `GenerateMod.bat` ends with `PAUSE`. In a real terminal you'll see "Press any key to continue..." at the end. That's normal. Hit a key, close the window.

---

## Step 9 — Run it

Launch WARNO. Enable your mod in `Game → Mods`. Start or load an Army General campaign that touches one of the decks you modded. Click the pawn for that deck.

If the composition UI opens and you can see your WIF units in the platoons and counts you set, you're done. Drag a unit out, fight a battle, save the campaign. Ship it.

If WARNO crashes the moment you click the pawn — and only on the modded pawn — you're running an out-of-date version of this tool. Pull the latest `main`, run the export and build again, retry. The pre-export sanity check should catch this before it ever hits disk, but if you skipped the rebuild after pulling, you're running stale code.

---

## After a WARNO patch

Eugen pushes a patch every couple of months and rewrites bits of vanilla NDF. Here's the dance:

1. Run `UpdateMod.bat` from inside your mod folder. It does a 3-way merge between your mod, the old vanilla baseline, and the new patched vanilla. Most things auto-resolve. The ones that don't show up in the console — fix them by hand.
2. Hit **Refresh decks** in the tool so the cached pack indices match the new vanilla.
3. **📥 Export Mod** → **⚡ Build Mod** like before.
4. Click your pawn in-game and make sure nothing regressed.

---

## Splitting work with a friend

If you're doing NATO decks and your friend is doing Warsaw Pact, the merge is basically free. Replicas are saved keyed by deck name, and deck names embed the nation (`pion_US_*`, `pion_SOV_*`, `pion_RDA_*`, etc.) — so as long as you each stay in your lane, you never touch the same key.

How to actually share:

1. Both of you clone the repo and pull `main` so you're running the same generator. Otherwise one of you produces NDFs the other's build can't reproduce.
2. Each of you opens the tool, sets your session's **Nation scope** to your side, and only edits decks you can see.
3. To merge: he sends you his `data/wif_replicas.json`. You union it with yours (literally `{...mine, ...his}` — a 5-line script or any JSON tool). Save the union back to `data/wif_replicas.json` on the machine that'll build the mod.
4. Build on **one** machine — only that machine has both your replicas.

If you both end up editing the same deck somehow, the union's a "last write wins" — keep an eye on it.

---

## Quick cheat sheet

| Step | What | Roughly how long |
|---|---|---|
| 1 | `CreateNewMod.bat <Name>` | seconds |
| 2 | Copy WIF source into the mod | 2 minutes (most of it copy time) |
| 3 | Start the tool | 5 seconds |
| 4 | Settings in the UI | 30 seconds |
| 5 | Refresh deck cache | 5 seconds |
| 6 | Build replicas | the actual work — varies wildly |
| 7 | 📥 Export Mod | under 5 seconds |
| 8 | ⚡ Build Mod | 30s incremental, 10-20 min first build |
| 9 | Click the pawn in WARNO | up to you |

That's the whole loop. Once you've done it once, you can churn out new decks in minutes.
