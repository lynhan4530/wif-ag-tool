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
