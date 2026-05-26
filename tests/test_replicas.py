"""Replica store tests — CRUD, empty rejection, seq disambiguation."""
from __future__ import annotations
import pytest

from wif_ag_tool import replicas as rmod


def test_save_and_load_replica(tmp_path):
    f = tmp_path / "wif_replicas.json"
    rmod.save_replica("Descriptor_Deck_pion_US_X_1", [
        {"unit_id": "WF_M1A2_SEPV2_Abrams_US", "xp": 1, "count": 1},
    ], path=f)
    store = rmod.load_replicas(f)
    assert "Descriptor_Deck_pion_US_X_1" in store
    entry = store["Descriptor_Deck_pion_US_X_1"]
    assert entry["saved"] is True
    assert entry["groups"][0]["name"] == "A"
    assert entry["groups"][0]["platoons"][0]["name"] == "none"
    assert entry["groups"][0]["platoons"][0]["units"][0]["unit_id"] == "WF_M1A2_SEPV2_Abrams_US"
    assert entry["groups"][0]["platoons"][0]["units"][0]["xp"] == 1


def test_empty_units_rejected(tmp_path):
    f = tmp_path / "wif_replicas.json"
    with pytest.raises(ValueError):
        rmod.save_replica("Descriptor_Deck_pion_US_X_1", [], path=f)


def test_delete_replica(tmp_path):
    f = tmp_path / "wif_replicas.json"
    rmod.save_replica("Descriptor_Deck_pion_US_X_1",
                      [{"unit_id": "WF_M1A2_SEPV2_Abrams_US", "xp": 1}], path=f)
    assert rmod.delete_replica("Descriptor_Deck_pion_US_X_1", path=f) is True
    store = rmod.load_replicas(f)
    assert "Descriptor_Deck_pion_US_X_1" not in store
    assert rmod.delete_replica("missing", path=f) is False


def test_xp_validation(tmp_path):
    f = tmp_path / "wif_replicas.json"
    with pytest.raises(ValueError):
        rmod.save_replica("D", [{"unit_id": "U", "xp": 9}], path=f)


def test_replicas_to_assignments_seq_for_duplicate_unit(tmp_path):
    # Same unit appears 3 times in one deck → seq = 0, 1, 2
    store = {
        "Descriptor_Deck_pion_US_X_1": {
            "saved": True,
            "units": [
                {"unit_id": "WF_M1A2_SEPV2_Abrams_US", "xp": 1, "count": 1},
                {"unit_id": "WF_M2A4_Bradley_US", "xp": 1, "count": 1},
                {"unit_id": "WF_M1A2_SEPV2_Abrams_US", "xp": 2, "count": 1},
                {"unit_id": "WF_M1A2_SEPV2_Abrams_US", "xp": 3, "count": 1},
            ],
        }
    }
    asn = rmod.replicas_to_assignments(store)
    abrams = [a for a in asn if a.unit_id == "WF_M1A2_SEPV2_Abrams_US"]
    assert [a.seq for a in abrams] == [0, 1, 2]
    bradley = [a for a in asn if a.unit_id == "WF_M2A4_Bradley_US"][0]
    assert bradley.seq == 0
    # Order field is preserved from list position
    assert [a.order for a in asn] == [0, 1, 2, 3]


def test_replicas_to_assignments_scope_filter():
    store = {
        "Descriptor_Deck_pion_US_A_1": {"saved": True, "units": [{"unit_id": "WF_M1A2_SEPV2_Abrams_US", "xp": 1}]},
        "Descriptor_Deck_pion_US_B_1": {"saved": True, "units": [{"unit_id": "WF_M2A4_Bradley_US", "xp": 1}]},
        "Descriptor_Deck_pion_US_C_1": {"saved": False, "units": [{"unit_id": "WF_T90M_RUS", "xp": 1}]},
    }
    asn = rmod.replicas_to_assignments(store, scope_decks=["Descriptor_Deck_pion_US_A_1"])
    assert {a.deck_name for a in asn} == {"Descriptor_Deck_pion_US_A_1"}
    # Unsaved replicas are skipped even when in scope
    asn_all = rmod.replicas_to_assignments(store)
    assert {a.deck_name for a in asn_all} == {
        "Descriptor_Deck_pion_US_A_1", "Descriptor_Deck_pion_US_B_1",
    }
