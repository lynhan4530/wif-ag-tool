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
