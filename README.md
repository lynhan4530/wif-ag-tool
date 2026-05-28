# WARNO WIF AG Deck Assignment Tool

An interactive, web-based modding companion tool for **WARNO**'s Army General campaigns. It allows modders to seamlessly assign custom units—like the modern units from **A World in Flames (WIF)**—into Army General campaign decks, and outputs/compiles the necessary NDF and CSV patch files to build the mod.

> **New here?** Read **[HOWTO.md](HOWTO.md)** for the full end-to-end walkthrough — scaffold a mod, copy WIF units in, build a replica deck, export, compile, and run. The same guide is available inside the tool via the **❓ How to** button in the header.

The tool features a high-performance Single Page Application (SPA) UI that mirrors WARNO's 4-tier battle order hierarchy (**Deck → Combat Group → Platoon/Smart Group → Unit**).

> [!NOTE]
> This tool is heavily optimized for **A World in Flames (WIF)** modern units and configuration paths, but is designed with a roadmap for other custom mods and generic units.

---

## Key Features

- **Hierarchical Deck Organization**: Organize unit packs structurally inside Combat Groups and Platoons rather than working with flat text files.
- **Platoon Picker Modal**: Eagerly extracts and lists authentic vanilla platoon/smart group names (e.g., `1ST RECON PLATOON`, `TROOP HQ`, `SUPPORT GROUP`) directly from the selected deck.
- **Smart Heuristic Fallbacks**: In cases where vanilla smart group tokens are compiled internally, the backend analyzes the unit composition (tanks, recon, infantry, support) to automatically resolve names matching the in-game UI.
- **Interactive Unit Browser**: Filter units by role and search by name. Support for assigning single-vehicle transports (such as IFVs or transport helicopters) directly with squads.
- **Drag-and-Drop Reordering**: Easily reorder units within a platoon or drag them across different platoons and combat groups.
- **Mod Folder & Workspace Settings**: Configure target paths for the WIF mod folder, WARNO game installation folder, and a custom export folder override directly within the web app settings modal.
- **One-Click Direct Export**: Generates and writes the NDF and CSV patch files (`StrategicPacks_additions.ndf`, `StrategicCombatGroups_additions.ndf`, `StrategicDecks_patch.ndf`, `PLATOONS_additions.csv`) directly to the mod's target workspace folders.
- **In-Browser Mod Compilation**: Run `GenerateMod.bat` directly from the browser interface and view compilation progress, stdout, and stderr logs in a scrollable console log modal in real time.
- **Update-Resilience**: Designed to easily refresh unit/deck caches from vanilla assets when the base game receives updates or patches.

---

## Requirements

- **Python 3.10+** (Python 3.11/3.12+ recommended)
- **WARNO** (with the official WARNO modding tools installed)
- **A World in Flames (WIF)** mod development folder (or custom mod workspace containing the `GenerateMod.bat` compile script)

---

## Installation & Setup

1. **Clone the repository** into your desired project directory:
   ```bash
   git clone https://github.com/lynhan4530/wif-ag-tool.git
   cd wif-ag-tool
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure default paths** (Optional):
   You can customize default paths inside `src/wif_ag_tool/config.py` (e.g., steam save files, game paths), or configure them interactively inside the web application Settings.

---

## How to Start the Tool

### Running the Web Server
To start the local Flask server, run:
```bash
python -m wif_ag_tool serve
```
Alternatively, double-click the **`Start-WIF-AG.bat`** file in the repository root.

Once started, open your web browser and navigate to:
**`http://127.0.0.1:5000`**

### Running the Automated Test Suite
To run the full suite of unit and integration tests (including the settings API, direct exports, and compiler mock tests):
```bash
pytest tests/ -v
```

### Refreshing the Deck Cache
Whenever WARNO gets patched or you want to pull updated base deck statistics, re-parse the game files by running:
```bash
python -m wif_ag_tool refresh
```
*(You can also trigger this directly inside the web UI Settings if paths are configured).*

---

## How to Use the Tool (Modding Workflow)

1. **Open/Create a Session**: In the campaign picker, choose your campaign save or create a manual session.
2. **Configure Mod Paths**: Click the **⚙ Settings** button in the header and configure:
   - **WIF Mod Folder**: Path to your active mod development folder (e.g., `G:\Program Files (x86)\Steam\steamapps\common\WARNO\Mods\CRM_ArmyGeneral`).
   - **Game Folder**: Path to the base WARNO installation folder.
   - **Export Folder** (Optional): Where files will be written (defaults to the mod's `GameData` folder).
3. **Select a Deck**: In the left sidebar, choose the active deck you want to modify.
4. **Create Combat Groups**: Click `+ Add Group` in the replica panel to create a new group tab (e.g., `A`, `B`, `HQ`).
5. **Create Platoons**: Click `+ Add Platoon` inside a group. Select from authentic vanilla platoon names, standard options (like `1`, `2`, `HQ`, `SPT`), or type a custom name.
6. **Assign Units**: Click `+ Add Unit` inside a platoon. Select custom units and adjust experience levels, count, and transport overrides.
7. **Reorder/Refine**: Drag and drop unit rows to arrange your battle order.
8. **Export Mod**: Click **📥 Export Mod** in the header. The tool will write the additions and patches directly to your configured mod directory structure.
9. **Compile Mod**: Click **⚡ Build Mod** in the header. This opens a modal running `GenerateMod.bat` in the background, logging stdout/stderr in real-time until successful completion.

---

## Future Roadmap

While this tool is currently heavily optimized for **A World in Flames (WIF)** modern units and configuration paths:
* **Generic Mod Support**: The parser and assignment architecture is fully decoupled. Future updates will introduce support for importing other custom unit descriptors and mod paths.
* **Custom Campaigns**: Roadmap features include supporting custom-defined campaigns and deck hierarchies.
