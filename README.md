# WARNO WIF AG Deck Assignment Tool

An interactive web-based modding companion tool for **WARNO**'s Army General campaigns. It allows modders to seamlessly assign custom units—like the modern units from **A World in Flames (WIF)**—into Army General campaign decks, and outputs the necessary NDF and CSV patch files to build the mod.

The tool features a fully-featured Single Page Application (SPA) UI that mirrors WARNO's 4-tier battle order hierarchy (**Deck → Combat Group → Platoon/Smart Group → Unit**).

---

## Key Features

- **Hierarchical Deck Organization**: Organize unit packs structurally inside Combat Groups and Platoons rather than working with flat text files.
- **Platoon Picker Modal**: Eagerly extracts and lists authentic vanilla platoon/smart group names (e.g., `1ST RECON PLATOON`, `TROOP HQ`, `SUPPORT GROUP`) directly from the selected deck.
- **Smart Heuristic Fallbacks**: In cases where vanilla smart group tokens are compiled internally, the backend analyzes the unit composition (tanks, recon, infantry, support) to automatically resolve names matching the in-game UI.
- **Interactive Unit Browser**: Filter units by role and search by name. Support for assigning single-vehicle transports (such as IFVs or transport helicopters) directly with squads.
- **Drag-and-Drop Reordering**: Easily reorder units within a platoon or drag them across different platoons and combat groups.
- **One-Click Export**: Generates the structural NDF and CSV patch files (`StrategicPacks_additions.ndf`, `StrategicCombatGroups_additions.ndf`, `StrategicDecks_patch.ndf`, `PLATOONS_additions.csv`) ready to be integrated into your mod files.
- **Update-Resilience**: Designed to easily refresh unit/deck caches from vanilla assets when the base game receives updates or patches.

---

## Requirements

- **Python 3.10+**
- **WARNO** (with the modding tools installed)
- **A World in Flames** mod workspace (or custom mod workspace)

---

## Installation & Setup

1. Clone the repository into your project directory.
2. Install python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. *(Optional)* Configure path overrides in the environment variables if your Steam or Mod directories are in non-standard locations (see `src/wif_ag_tool/config.py` for default paths).

---

## How to Start the Tool

### Running the Web App
To start the local Flask server, run:
```bash
python -m wif_ag_tool serve
```
Alternatively, double-click the **`Start-WIF-AG.bat`** file.

Once started, open your web browser and navigate to:
**`http://127.0.0.1:5000`**

### Running Tests
To run the full suite of unit and integration tests:
```bash
pytest tests/ -v
```

### Refreshing Deck Cache
Whenever WARNO gets patched or you want to pull updated base deck statistics, re-parse the game files by running:
```bash
python -m wif_ag_tool refresh
```

---

## Modding Workflow

1. **Select a Campaign and Deck**: In the left sidebar, choose your campaign and select the active deck you want to mod.
2. **Add Combat Groups**: Click `+ Add Group` in the replica panel to create a new group tab (e.g., `A`, `B`, `HQ`).
3. **Add Platoons**: Click `+ Add Platoon` inside a group. Choose from authentic vanilla platoon names, standard options (like `1`, `2`, `HQ`, `SPT`), or type a custom name.
4. **Assign Units**: Click `+ Add Unit` inside a platoon. Select custom units and adjust experience levels, count, and transport overrides.
5. **Reorder/Refine**: Drag and drop unit rows to arrange your battle order.
6. **Save & Export**: Save your changes, click `Export`, and download the zip containing the compiled patch files.
7. **Build Mod**: Paste the files into your mod directory, run `GenerateMod.bat` inside your mod folder, and launch the game.

---

## Future Roadmap

While this tool is currently heavily optimized for **A World in Flames (WIF)** modern units and configuration paths:
* **Generic Mod Support**: The parser and assignment architecture is fully decoupled. Future updates will introduce support for importing other custom unit descriptors and mod paths.
* **Custom Campaigns**: Roadmap features include supporting custom-defined campaigns and deck hierarchies.
