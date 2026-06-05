"""Tests for the REST API endpoints, specifically settings, direct export, and mod compilation."""
from __future__ import annotations
import pytest
from pathlib import Path
from wif_ag_tool import config
from wif_ag_tool.web.app import create_app
from wif_ag_tool.web.api import set_state
from wif_ag_tool.models import DeckState, WifUnit

@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(config, "REPLICAS_FILE", tmp_path / "data" / "wif_replicas.json")
    
    from wif_ag_tool import session as session_mod
    monkeypatch.setattr(session_mod.config, "SESSIONS_DIR", tmp_path / "sessions")
    
    from wif_ag_tool.web import api as api_mod
    monkeypatch.setattr(api_mod.config, "SESSIONS_DIR", tmp_path / "sessions")
    
    app = create_app(load_data=False)
    app.config.update({
        "TESTING": True,
    })
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_session_settings_patch(client):
    # First create a session
    resp = client.post("/api/sessions", json={"campaign": "CENTAG", "factions": ["US"]})
    assert resp.status_code == 201
    data = resp.get_json()
    slug = data["slug"]
    
    # Patch settings
    resp = client.patch(f"/api/sessions/{slug}", json={
        "target_mod_dir": "/path/to/mod",
        "game_dir": "/path/to/game",
        "export_dir": "/path/to/export"
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["target_mod_dir"] == "/path/to/mod"
    assert data["game_dir"] == "/path/to/game"
    assert data["export_dir"] == "/path/to/export"
    
    # Get session details to verify it's persisted
    resp = client.get(f"/api/sessions/{slug}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["target_mod_dir"] == "/path/to/mod"
    assert data["game_dir"] == "/path/to/game"
    assert data["export_dir"] == "/path/to/export"

def test_export_direct_no_decks(client):
    # Create session
    resp = client.post("/api/sessions", json={"campaign": "CENTAG", "factions": ["US"]})
    slug = resp.get_json()["slug"]
    
    # No decks mock loaded yet
    set_state(decks={})
    
    resp = client.post(f"/api/sessions/{slug}/export_direct")
    assert resp.status_code == 400
    assert "No deck cache loaded" in resp.get_json()["error"]

def test_export_direct_success(client, tmp_path, monkeypatch):
    # Setup mock folders
    mod_dir = tmp_path / "CRM_ArmyGeneral"
    mod_dir.mkdir()
    export_dir = tmp_path / "export_output"
    
    # Create required initial base files in export_dir
    decks_dir = export_dir / "Generated" / "Gameplay" / "Decks"
    decks_dir.mkdir(parents=True, exist_ok=True)
    (decks_dir / "StrategicDecks.ndf").write_text(
        "export Descriptor_Deck_pion_US_11ACR_4 is TDeckDescriptor\n(\n    DeckPackList = [\n    ]\n    DeckCombatGroupList = [\n    ]\n)\n",
        encoding="utf-8"
    )
    (decks_dir / "StrategicPacks.ndf").write_text("// packs\n", encoding="utf-8")
    (decks_dir / "StrategicCombatGroups.ndf").write_text("// groups\n", encoding="utf-8")
    
    csv_dir = export_dir / "Localisation" / "CRM_ArmyGeneral"
    csv_dir.mkdir(parents=True, exist_ok=True)
    (csv_dir / "PLATOONS.csv").write_text('"TOKEN";"REFTEXT"\n', encoding="utf-8")

    # Create session and patch settings
    resp = client.post("/api/sessions", json={"campaign": "CENTAG", "factions": ["US"]})
    slug = resp.get_json()["slug"]
    client.patch(f"/api/sessions/{slug}", json={
        "target_mod_dir": str(mod_dir),
        "export_dir": str(export_dir)
    })
    
    # Mock replicas
    from wif_ag_tool import replicas as rmod
    monkeypatch.setattr(rmod.config, "REPLICAS_FILE", tmp_path / "data" / "wif_replicas.json")
    
    deck_name = "Descriptor_Deck_pion_US_11ACR_4"
    rmod.save_replica(deck_name, [
        {"unit_id": "WF_M1A2_Abrams", "xp": 1, "count": 1, "transport_id": None}
    ], path=tmp_path / "data" / "wif_replicas.json")
    
    # Mock state decks and units
    mock_deck = DeckState(
        name=deck_name,
        division_ref="US_11ACR",
        pack_list=[],
        combat_group_list=[]
    )
    mock_unit = WifUnit(
        name="WF_M1A2_Abrams",
        guid="mock-guid-12345",
        nation="US",
        attack=10,
        defense=10,
        xp_bonus=1,
        role="armor",
        name_token="M1A2_ABRAMS_TOKEN",
        display_name="M1A2 Abrams"
    )
    set_state(
        decks={deck_name: mock_deck},
        units={"WF_M1A2_Abrams": mock_unit}
    )
    
    # Trigger export_direct
    resp = client.post(f"/api/sessions/{slug}/export_direct")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    
    # Verify files created in export_dir
    assert (export_dir / "Generated" / "Gameplay" / "Decks" / "StrategicPacks.ndf").exists()
    assert (export_dir / "Generated" / "Gameplay" / "Decks" / "StrategicCombatGroups.ndf").exists()
    assert (export_dir / "Generated" / "Gameplay" / "Decks" / "StrategicDecks.ndf").exists()
    assert (export_dir / "Localisation" / "CRM_ArmyGeneral" / "PLATOONS.csv").exists()

def test_export_direct_preserves_existing_platoons_csv(client, tmp_path, monkeypatch):
    """export_direct must APPEND to PLATOONS.csv, never clobber the mod's existing
    localisation rows (regression: the full table was being overwritten with only
    the few WIF AG tokens, breaking every other platoon name in-game)."""
    mod_dir = tmp_path / "CRM_ArmyGeneral"
    mod_dir.mkdir()
    export_dir = tmp_path / "export_output"

    decks_dir = export_dir / "Generated" / "Gameplay" / "Decks"
    decks_dir.mkdir(parents=True, exist_ok=True)
    (decks_dir / "StrategicDecks.ndf").write_text(
        "export Descriptor_Deck_pion_US_11ACR_4 is TDeckDescriptor\n(\n    DeckPackList = [\n    ]\n    DeckCombatGroupList = [\n    ]\n)\n",
        encoding="utf-8",
    )
    (decks_dir / "StrategicPacks.ndf").write_text("// packs\n", encoding="utf-8")
    (decks_dir / "StrategicCombatGroups.ndf").write_text("// groups\n", encoding="utf-8")

    csv_dir = export_dir / "Localisation" / "CRM_ArmyGeneral"
    csv_dir.mkdir(parents=True, exist_ok=True)
    csv_path = csv_dir / "PLATOONS.csv"
    # Pre-existing localisation rows that must survive the export.
    csv_path.write_text(
        '"TOKEN";"REFTEXT"\n"ADHGKXYYNT";"11th ACR Alpha"\n"HGXGZRSJDO";"Tank Platoon"\n',
        encoding="utf-8",
    )

    resp = client.post("/api/sessions", json={"campaign": "CENTAG", "factions": ["US"]})
    slug = resp.get_json()["slug"]
    client.patch(f"/api/sessions/{slug}", json={
        "target_mod_dir": str(mod_dir),
        "export_dir": str(export_dir),
    })

    from wif_ag_tool import replicas as rmod
    monkeypatch.setattr(rmod.config, "REPLICAS_FILE", tmp_path / "data" / "wif_replicas.json")
    deck_name = "Descriptor_Deck_pion_US_11ACR_4"
    rmod.save_replica(deck_name, [
        {"unit_id": "WF_M1A2_Abrams", "xp": 1, "count": 1, "transport_id": None}
    ], path=tmp_path / "data" / "wif_replicas.json")

    set_state(
        decks={deck_name: DeckState(name=deck_name, division_ref="US_11ACR", pack_list=[], combat_group_list=[])},
        units={"WF_M1A2_Abrams": WifUnit(
            name="WF_M1A2_Abrams", guid="g", nation="US", attack=10, defense=10,
            xp_bonus=1, role="armor", name_token="t", display_name="M1A2 Abrams")},
    )

    resp = client.post(f"/api/sessions/{slug}/export_direct")
    assert resp.status_code == 200, resp.get_json()

    text = csv_path.read_text(encoding="utf-8")
    # Pre-existing rows survive …
    assert '"ADHGKXYYNT";"11th ACR Alpha"' in text
    assert '"HGXGZRSJDO";"Tank Platoon"' in text
    # … exactly one header (we dropped the generated duplicate) …
    assert text.count('"TOKEN";"REFTEXT"') == 1
    # … and the export added new WIF rows on top.
    assert text.count("\n") > 3

    # Idempotent: a second export must not duplicate or drop the stock rows.
    resp = client.post(f"/api/sessions/{slug}/export_direct")
    assert resp.status_code == 200
    text2 = csv_path.read_text(encoding="utf-8")
    assert text2.count('"ADHGKXYYNT";"11th ACR Alpha"') == 1
    assert text2.count('"TOKEN";"REFTEXT"') == 1

def test_export_direct_replaces_deck_contents(client, tmp_path, monkeypatch):
    """Full-replacement model: export_direct rewrites the deck's DeckPackList /
    DeckCombatGroupList to exactly the replica — the vanilla refs must be gone, and the
    new WIF pack def must land in StrategicPacks.ndf."""
    mod_dir = tmp_path / "CRM_ArmyGeneral"
    mod_dir.mkdir()
    export_dir = tmp_path / "export_output"
    decks_dir = export_dir / "Generated" / "Gameplay" / "Decks"
    decks_dir.mkdir(parents=True, exist_ok=True)

    deck_name = "Descriptor_Deck_pion_US_11ACR_4"
    # A deck that already carries vanilla packs + combat groups.
    (decks_dir / "StrategicDecks.ndf").write_text(
        f"export {deck_name} is TDeckDescriptor\n"
        "(\n"
        "    DeckIdentifier = 'pion_US_11ACR_4'\n"
        "    DeckPackList =\n"
        "    [\n"
        "        ~/Descriptor_StrategicPack_VANILLA_TANK_1,\n"
        "        ~/Descriptor_StrategicPack_VANILLA_TANK_1,\n"
        "    ]\n"
        "    DeckCombatGroupList =\n"
        "    [\n"
        "        ~/Descriptor_CombatGroup_VANILLA_HQ,\n"
        "    ]\n"
        ")\n",
        encoding="utf-8",
    )
    (decks_dir / "StrategicPacks.ndf").write_text("// packs\n", encoding="utf-8")
    (decks_dir / "StrategicCombatGroups.ndf").write_text("// groups\n", encoding="utf-8")
    csv_dir = export_dir / "Localisation" / "CRM_ArmyGeneral"
    csv_dir.mkdir(parents=True, exist_ok=True)
    (csv_dir / "PLATOONS.csv").write_text('"TOKEN";"REFTEXT"\n', encoding="utf-8")

    resp = client.post("/api/sessions", json={"campaign": "CENTAG", "factions": ["US"]})
    slug = resp.get_json()["slug"]
    client.patch(f"/api/sessions/{slug}", json={
        "target_mod_dir": str(mod_dir), "export_dir": str(export_dir)})

    from wif_ag_tool import replicas as rmod
    monkeypatch.setattr(rmod.config, "REPLICAS_FILE", tmp_path / "data" / "wif_replicas.json")
    rmod.save_replica(deck_name, [
        {"unit_id": "WF_M1A2_Abrams", "xp": 1, "count": 1, "transport_id": None}
    ], path=tmp_path / "data" / "wif_replicas.json")

    set_state(
        decks={deck_name: DeckState(name=deck_name, division_ref="US_11ACR",
                                    pack_list=["x", "x"], combat_group_list=["VANILLA"])},
        units={"WF_M1A2_Abrams": WifUnit(
            name="WF_M1A2_Abrams", guid="g", nation="US", attack=10, defense=10,
            xp_bonus=1, role="armor", name_token="t", display_name="M1A2 Abrams")},
    )

    resp = client.post(f"/api/sessions/{slug}/export_direct")
    assert resp.status_code == 200, resp.get_json()

    decks_text = (decks_dir / "StrategicDecks.ndf").read_text(encoding="utf-8")
    packs_text = (decks_dir / "StrategicPacks.ndf").read_text(encoding="utf-8")
    # Vanilla contents replaced, not appended.
    assert "VANILLA_TANK" not in decks_text
    assert "Descriptor_CombatGroup_VANILLA_HQ" not in decks_text
    # The replica's WIF pack + combat group now define the deck.
    assert "~/Descriptor_StrategicPack_WF_M1A2_Abrams_US_11ACR_4_1," in decks_text
    assert "~/Descriptor_CombatGroup_US_11ACR_4_WIF_A," in decks_text
    # And the pack definition was appended to StrategicPacks.ndf.
    assert "Descriptor_StrategicPack_WF_M1A2_Abrams_US_11ACR_4_1 is DeckPackDescriptor" in packs_text


def test_build_mod_not_configured(client):
    resp = client.post("/api/sessions", json={"campaign": "CENTAG", "factions": ["US"]})
    slug = resp.get_json()["slug"]
    
    resp = client.post(f"/api/sessions/{slug}/build")
    assert resp.status_code == 400
    assert "No target mod directory configured" in resp.get_json()["error"]

def test_build_mod_not_exist(client):
    resp = client.post("/api/sessions", json={"campaign": "CENTAG", "factions": ["US"]})
    slug = resp.get_json()["slug"]
    client.patch(f"/api/sessions/{slug}", json={"target_mod_dir": "/nonexistent/path"})
    
    resp = client.post(f"/api/sessions/{slug}/build")
    assert resp.status_code == 400
    assert "Target mod directory does not exist" in resp.get_json()["error"]

def test_build_mod_missing_bat(client, tmp_path):
    resp = client.post("/api/sessions", json={"campaign": "CENTAG", "factions": ["US"]})
    slug = resp.get_json()["slug"]
    
    mod_dir = tmp_path / "mock_mod"
    mod_dir.mkdir()
    client.patch(f"/api/sessions/{slug}", json={"target_mod_dir": str(mod_dir)})
    
    resp = client.post(f"/api/sessions/{slug}/build")
    assert resp.status_code == 400
    assert "GenerateMod.bat not found" in resp.get_json()["error"]

def test_build_mod_missing_files(client, tmp_path):
    resp = client.post("/api/sessions", json={"campaign": "CENTAG", "factions": ["US"]})
    slug = resp.get_json()["slug"]
    
    mod_dir = tmp_path / "mock_mod"
    mod_dir.mkdir()
    (mod_dir / "GenerateMod.bat").write_text("echo building", encoding="utf-8")
    client.patch(f"/api/sessions/{slug}", json={"target_mod_dir": str(mod_dir)})
    
    resp = client.post(f"/api/sessions/{slug}/build")
    assert resp.status_code == 400
    assert "Pre-build check failed: Export files are missing" in resp.get_json()["error"]

def test_replica_save_accepts_vanilla_unit(client):
    """Both WIF and vanilla unit IDs should be accepted by PUT /decks/<n>/replica
    so the user can build replicas that mix custom + stock WARNO units."""
    from wif_ag_tool.models import DeckState, WifUnit

    deck_name = "Descriptor_Deck_pion_US_11ACR_4"
    set_state(
        decks={deck_name: DeckState(name=deck_name, pack_list=[], combat_group_list=[])},
        units={"WF_M1A2_Abrams": WifUnit(
            name="WF_M1A2_Abrams", guid="g1", nation="US",
            attack=600, defense=450, xp_bonus=1, role="armor", name_token="t1",
        )},
        vanilla_units={"M1A1_Abrams_US": WifUnit(
            name="M1A1_Abrams_US", guid="g2", nation="US",
            attack=400, defense=290, xp_bonus=1, role="armor", name_token="t2",
        )},
    )

    # Pure vanilla replica
    resp = client.put(f"/api/decks/{deck_name}/replica", json={
        "groups": [{"name": "A", "platoons": [
            {"name": "1ST TANK PLATOON", "units": [
                {"unit_id": "M1A1_Abrams_US", "xp": 2, "count": 4},
            ]},
        ]}],
    })
    assert resp.status_code == 200, resp.get_json()

    # Mixed WIF + vanilla in the same platoon
    resp = client.put(f"/api/decks/{deck_name}/replica", json={
        "groups": [{"name": "A", "platoons": [
            {"name": "MIXED", "units": [
                {"unit_id": "WF_M1A2_Abrams", "xp": 1, "count": 2},
                {"unit_id": "M1A1_Abrams_US", "xp": 2, "count": 4},
            ]},
        ]}],
    })
    assert resp.status_code == 200, resp.get_json()

    # Unknown id still gets rejected
    resp = client.put(f"/api/decks/{deck_name}/replica", json={
        "groups": [{"name": "A", "platoons": [
            {"name": "X", "units": [{"unit_id": "Totally_Fake_Unit", "xp": 1, "count": 1}]},
        ]}],
    })
    assert resp.status_code == 400


def test_wif_units_endpoint_tags_source(client):
    """Both unit endpoints must include a `source` field so the SPA can
    filter and badge units client-side."""
    from wif_ag_tool.models import WifUnit
    set_state(
        units={"WF_M1A2_Abrams": WifUnit(
            name="WF_M1A2_Abrams", guid="g1", nation="US",
            attack=600, defense=450, xp_bonus=1, role="armor", name_token="t1",
        )},
        vanilla_units={"M1A1_Abrams_US": WifUnit(
            name="M1A1_Abrams_US", guid="g2", nation="US",
            attack=400, defense=290, xp_bonus=1, role="armor", name_token="t2",
        )},
    )
    resp = client.get("/api/wif_units")
    assert all(u["source"] == "wif" for u in resp.get_json())
    resp = client.get("/api/vanilla_units")
    assert all(u["source"] == "vanilla" for u in resp.get_json())


def test_wif_units_role_filter_matches_canonical_buckets(client):
    """Picking 'plane' in the dropdown should return units with raw role
    'sead' / 'uav' (which used to silently return nothing because the API
    did exact-match on the raw role string)."""
    from wif_ag_tool.models import WifUnit
    mock_units = {
        "WF_F15_StrikeEagle_US": WifUnit(
            name="WF_F15_StrikeEagle_US", guid="g1", nation="US",
            attack=300, defense=180, xp_bonus=1, role="sead", name_token="t1",
        ),
        "WF_Reaper_US": WifUnit(
            name="WF_Reaper_US", guid="g2", nation="US",
            attack=120, defense=40, xp_bonus=1, role="uav", name_token="t2",
        ),
        "WF_M1A1_Abrams_US": WifUnit(
            name="WF_M1A1_Abrams_US", guid="g3", nation="US",
            attack=400, defense=290, xp_bonus=1, role="armor", name_token="t3",
        ),
        "WF_M1A1_CMD_US": WifUnit(
            name="WF_M1A1_CMD_US", guid="g4", nation="US",
            attack=400, defense=290, xp_bonus=1, role="hq_tank", name_token="t4",
        ),
        "WF_M109A6_US": WifUnit(
            name="WF_M109A6_US", guid="g5", nation="US",
            attack=89, defense=42, xp_bonus=1, role="howitzer", name_token="t5",
        ),
    }
    set_state(units=mock_units)

    # plane → both sead and uav
    resp = client.get("/api/wif_units?role=plane")
    assert resp.status_code == 200
    names = {u["name"] for u in resp.get_json()}
    assert names == {"WF_F15_StrikeEagle_US", "WF_Reaper_US"}

    # artillery → howitzer (would have returned nothing before the fix)
    resp = client.get("/api/wif_units?role=artillery")
    assert {u["name"] for u in resp.get_json()} == {"WF_M109A6_US"}

    # armor → both armor and hq_tank (hq_tank's primary bucket is armor)
    resp = client.get("/api/wif_units?role=armor")
    assert {u["name"] for u in resp.get_json()} == {"WF_M1A1_Abrams_US", "WF_M1A1_CMD_US"}

    # command → only the hq_tank, not the regular Abrams
    resp = client.get("/api/wif_units?role=command")
    assert {u["name"] for u in resp.get_json()} == {"WF_M1A1_CMD_US"}

    # all → everything
    resp = client.get("/api/wif_units?role=all")
    assert len(resp.get_json()) == 5


def test_howto_returns_markdown(client):
    """GET /api/howto streams the HOWTO.md repo doc as text/markdown so the SPA
    can render it without needing a second source of truth."""
    resp = client.get("/api/howto")
    assert resp.status_code == 200
    assert "markdown" in resp.headers.get("Content-Type", "")
    text = resp.get_data(as_text=True)
    # Guard the load-bearing sections so the doc can't silently lose them.
    assert "How To" in text
    assert "Make a new mod" in text
    assert "Drop WIF into the mod" in text
    assert "Build a replica deck" in text
    assert "Export the patches" in text
    assert "Compile" in text
    assert "After a WARNO patch" in text


def test_status_endpoint(client, monkeypatch):
    from wif_ag_tool import config
    
    class MockPath:
        def __init__(self, exists_val):
            self.exists_val = exists_val
        def exists(self):
            return self.exists_val

    # Test when file exists
    monkeypatch.setattr(config, "VANILLA_STRATEGIC_DECKS", MockPath(True))
    resp = client.get("/api/status")
    assert resp.status_code == 200
    assert resp.get_json()["raw_files_available"] is True

    # Test when file is missing
    monkeypatch.setattr(config, "VANILLA_STRATEGIC_DECKS", MockPath(False))
    resp = client.get("/api/status")
    assert resp.status_code == 200
    assert resp.get_json()["raw_files_available"] is False


def test_build_mod_success(client, tmp_path, monkeypatch):
    resp = client.post("/api/sessions", json={"campaign": "CENTAG", "factions": ["US"]})
    slug = resp.get_json()["slug"]
    
    mod_dir = tmp_path / "mock_mod"
    mod_dir.mkdir()
    (mod_dir / "GenerateMod.bat").write_text("echo building", encoding="utf-8")
    client.patch(f"/api/sessions/{slug}", json={"target_mod_dir": str(mod_dir)})
    
    # Create required files
    export_path = mod_dir / "GameData"
    required_files = [
        export_path / "Generated" / "Gameplay" / "Decks" / "StrategicPacks.ndf",
        export_path / "Generated" / "Gameplay" / "Decks" / "StrategicCombatGroups.ndf",
        export_path / "Generated" / "Gameplay" / "Decks" / "StrategicDecks.ndf",
        export_path / "Localisation" / "mock_mod" / "PLATOONS.csv"
    ]
    for rf in required_files:
        rf.parent.mkdir(parents=True, exist_ok=True)
        rf.write_text("content", encoding="utf-8")
        
    # Mock subprocess.run
    import subprocess
    from unittest.mock import MagicMock
    mock_run = MagicMock()
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "Build Output Success"
    mock_run.return_value.stderr = "No errors"
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    resp = client.post(f"/api/sessions/{slug}/build")
    assert resp.status_code == 200
    json_data = resp.get_json()
    assert json_data["ok"] is True
    assert json_data["stdout"] == "Build Output Success"
    assert json_data["stderr"] == "No errors"
    
    # Verify subprocess.run args
    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert str(mod_dir / "GenerateMod.bat") in args[0]
    assert kwargs["cwd"] == str(mod_dir)


def test_get_localized_fallback_name():
    from wif_ag_tool.web.api import _get_localized_fallback_name

    # German artillery deck cases
    assert _get_localized_fallback_name("TANK", is_hq=True, count=1, cg_name="1_355__Artillerie", deck_name="pion_RFA_12PzD_3555Art") == "STAB"
    assert _get_localized_fallback_name("TANK", is_hq=False, count=2, cg_name="1_355__Artillerie", deck_name="pion_RFA_12PzD_3555Art") == "2. BATTERIE"
    
    # German regular deck cases
    assert _get_localized_fallback_name("TANK", is_hq=False, count=3, cg_name="A_12th_ACR", deck_name="pion_RFA_12PzD") == "3. PANZERZUG"
    assert _get_localized_fallback_name("RECON", is_hq=False, count=1, cg_name="A_12th_ACR", deck_name="pion_RFA_12PzD") == "1. AUFKLÄRUNGSZUG"
    assert _get_localized_fallback_name("RIFLE", is_hq=False, count=2, cg_name="A_12th_ACR", deck_name="pion_DDR_11MSD") == "2. INFANTERIEZUG"
    
    # French cases
    assert _get_localized_fallback_name("TANK", is_hq=True, count=1, cg_name="1_Art", deck_name="pion_FR_107Art") == "PELOTON DE COMMANDEMENT"
    assert _get_localized_fallback_name("TANK", is_hq=False, count=1, cg_name="1_Art", deck_name="pion_FR_107Art") == "1ère BATTERIE"
    assert _get_localized_fallback_name("TANK", is_hq=False, count=2, cg_name="1_Art", deck_name="pion_FR_107Art") == "2e BATTERIE"
    assert _get_localized_fallback_name("TANK", is_hq=False, count=2, cg_name="A_Tank", deck_name="pion_FR_107") == "2e PELOTON DE CHARS"

    # Russian cases
    assert _get_localized_fallback_name("TANK", is_hq=True, count=1, cg_name="A_Tank", deck_name="pion_SOV_11") == "SHTAB"
    assert _get_localized_fallback_name("TANK", is_hq=False, count=1, cg_name="A_Tank", deck_name="pion_SOV_11") == "1-Y TANKOVYY VZVOD"
    assert _get_localized_fallback_name("RIFLE", is_hq=False, count=3, cg_name="A_Rifle", deck_name="pion_SOV_11") == "3-Y MOTOSTRELKOVYY VZVOD"

    # Default English cases
    assert _get_localized_fallback_name("TANK", is_hq=True, count=1, cg_name="A_Tank", deck_name="pion_US_11") == "COMPANY HQ"
    assert _get_localized_fallback_name("TANK", is_hq=False, count=2, cg_name="A_Tank", deck_name="pion_US_11") == "2ND TANK PLATOON"
    assert _get_localized_fallback_name("ENGINEER", is_hq=False, count=1, cg_name="A_Eng", deck_name="pion_US_11") == "1ST ENGINEER PLATOON"
    assert _get_localized_fallback_name("AA", is_hq=False, count=1, cg_name="A_AA", deck_name="pion_US_11") == "1ST AIR DEFENSE PLATOON"
    assert _get_localized_fallback_name("LOGISTICS", is_hq=False, count=1, cg_name="A_Spt", deck_name="pion_US_11") == "1ST SUPPLY PLATOON"

    # US Cavalry / ACR cases
    assert _get_localized_fallback_name("TANK", is_hq=True, count=1, cg_name="HQ-1 11TH ACR", deck_name="pion_US_11ACR_1") == "TROOP HQ"
    assert _get_localized_fallback_name("ENGINEER", is_hq=False, count=1, cg_name="1_58ENG", deck_name="pion_US_11ACR_1") == "1/58ENG"
    assert _get_localized_fallback_name("ENGINEER", is_hq=False, count=2, cg_name="1_58ENG", deck_name="pion_US_11ACR_1") == "2/58ENG"
    assert _get_localized_fallback_name("AA", is_hq=False, count=1, cg_name="AIR DEFENSE PLATO", deck_name="pion_US_11ACR_1") == "AIR DEFENSE PLATO"
    assert _get_localized_fallback_name("LOGISTICS", is_hq=False, count=1, cg_name="LOGISTICS GROUP", deck_name="pion_US_11ACR_1") == "LOGISTICS GROUP"
    assert _get_localized_fallback_name("LOGISTICS", is_hq=False, count=2, cg_name="LOGISTICS GROUP", deck_name="pion_US_11ACR_1") == "LOGISTICS GROUP 2"
    assert _get_localized_fallback_name("RECON", is_hq=False, count=1, cg_name="RECON GROUP", deck_name="pion_US_11ACR_1") == "RECON GROUP"
    assert _get_localized_fallback_name("RECON", is_hq=False, count=2, cg_name="RECON GROUP", deck_name="pion_US_11ACR_1") == "RECON GROUP 2"
    assert _get_localized_fallback_name("SUPPORT", is_hq=False, count=1, cg_name="SUPPORT GROUP", deck_name="pion_US_11ACR_1") == "SUPPORT GROUP"
    assert _get_localized_fallback_name("SUPPORT", is_hq=False, count=2, cg_name="SUPPORT GROUP", deck_name="pion_US_11ACR_1") == "SUPPORT GROUP 2"

    # Extra localization coverage for new roles
    # German:
    assert _get_localized_fallback_name("ENGINEER", is_hq=False, count=1, cg_name="1_Eng", deck_name="pion_RFA_12PzD") == "1. PIONIERZUG"
    assert _get_localized_fallback_name("AA", is_hq=False, count=1, cg_name="1_AA", deck_name="pion_RFA_12PzD") == "1. FLUGABWEHRZUG"
    assert _get_localized_fallback_name("LOGISTICS", is_hq=False, count=1, cg_name="1_Log", deck_name="pion_RFA_12PzD") == "NACHSCHUBGRUPPE"
    assert _get_localized_fallback_name("LOGISTICS", is_hq=False, count=2, cg_name="1_Log", deck_name="pion_RFA_12PzD") == "NACHSCHUBGRUPPE 2"

    # French:
    assert _get_localized_fallback_name("ENGINEER", is_hq=False, count=1, cg_name="1_Eng", deck_name="pion_FR_107") == "1ère SECTION DU GENIE"
    assert _get_localized_fallback_name("AA", is_hq=False, count=1, cg_name="1_AA", deck_name="pion_FR_107") == "1ère SECTION SOL-AIR"
    assert _get_localized_fallback_name("LOGISTICS", is_hq=False, count=1, cg_name="1_Log", deck_name="pion_FR_107") == "GROUPE LOGISTIQUE"
    assert _get_localized_fallback_name("LOGISTICS", is_hq=False, count=2, cg_name="1_Log", deck_name="pion_FR_107") == "GROUPE LOGISTIQUE 2"

    # Russian:
    assert _get_localized_fallback_name("ENGINEER", is_hq=False, count=1, cg_name="1_Eng", deck_name="pion_SOV_11") == "1-Y SAPERNYY VZVOD"
    assert _get_localized_fallback_name("AA", is_hq=False, count=1, cg_name="1_AA", deck_name="pion_SOV_11") == "1-Y ZENITNYY VZVOD"
    assert _get_localized_fallback_name("LOGISTICS", is_hq=False, count=1, cg_name="1_Log", deck_name="pion_SOV_11") == "VZVOD OBESPECHENIYA"
    assert _get_localized_fallback_name("LOGISTICS", is_hq=False, count=2, cg_name="1_Log", deck_name="pion_SOV_11") == "VZVOD OBESPECHENIYA 2"

