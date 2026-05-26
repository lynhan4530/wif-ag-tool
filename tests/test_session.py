"""Session module tests — slugify, scope resolution, save/load roundtrip."""
from __future__ import annotations

from wif_ag_tool import session as smod


def test_slugify_basic():
    assert smod.slugify("CENTAG - DAY 7") == "centag-day-7"
    assert smod.slugify("The Left Hook") == "the-left-hook"
    assert smod.slugify("") == "session"
    assert smod.slugify("///") == "session"


def test_split_factions_compound():
    assert smod.split_factions(["UK_RFA", "SOV"]) == ["UK", "RFA", "SOV"]
    assert smod.split_factions(["US", "US"]) == ["US"]
    assert smod.split_factions([]) == []


def test_scope_decks_filters_by_nation_prefix():
    all_decks = [
        "Descriptor_Deck_pion_US_11ACR_4",
        "Descriptor_Deck_pion_RFA_1PzDiv_2",
        "Descriptor_Deck_pion_BEL_16Mech_1",
        "Descriptor_Deck_pion_SOV_3GTA_1",
        "Descriptor_Deck_pion_POL_10MSD_1",
    ]
    scoped = smod.scope_decks(["US", "RFA", "BEL"], all_decks)
    assert "Descriptor_Deck_pion_US_11ACR_4" in scoped
    assert "Descriptor_Deck_pion_RFA_1PzDiv_2" in scoped
    assert "Descriptor_Deck_pion_BEL_16Mech_1" in scoped
    assert "Descriptor_Deck_pion_SOV_3GTA_1" not in scoped
    assert "Descriptor_Deck_pion_POL_10MSD_1" not in scoped


def test_scope_decks_empty_scope():
    assert smod.scope_decks([], ["Descriptor_Deck_pion_US_X_1"]) == []


def test_create_session_seeds_scope_from_compound_factions(tmp_path):
    s = smod.create_session("The Left Hook", ["UK_RFA", "SOV"], ["Going West"], sessions_dir=tmp_path)
    assert s["slug"] == "the-left-hook"
    assert s["nation_scope"] == ["UK", "RFA", "SOV"]
    assert s["factions_from_save"] == ["UK_RFA", "SOV"]
    assert s["missions_seen"] == ["Going West"]


def test_create_session_disambiguates_duplicate_slug(tmp_path):
    smod.create_session("CENTAG DAY 7", ["US"], sessions_dir=tmp_path)
    s2 = smod.create_session("CENTAG DAY 7", ["US"], sessions_dir=tmp_path)
    assert s2["slug"] == "centag-day-7-2"


def test_save_load_session_roundtrip(tmp_path):
    s = smod.create_session("Test Camp", ["US"], sessions_dir=tmp_path)
    s["nation_scope"] = ["US", "RFA"]
    smod.save_session(s, sessions_dir=tmp_path)
    loaded = smod.load_session(s["slug"], sessions_dir=tmp_path)
    assert loaded["nation_scope"] == ["US", "RFA"]
    assert loaded["campaign"] == "Test Camp"


def test_list_sessions_sorted_by_updated_at(tmp_path):
    smod.create_session("Camp A", ["US"], sessions_dir=tmp_path)
    smod.create_session("Camp B", ["UK"], sessions_dir=tmp_path)
    listed = smod.list_sessions(tmp_path)
    assert len(listed) == 2
    # Most-recently-updated first
    assert listed[0]["updated_at"] >= listed[1]["updated_at"]


def test_delete_session(tmp_path):
    s = smod.create_session("Doomed", ["US"], sessions_dir=tmp_path)
    assert smod.delete_session(s["slug"], sessions_dir=tmp_path) is True
    assert smod.load_session(s["slug"], sessions_dir=tmp_path) is None
    assert smod.delete_session(s["slug"], sessions_dir=tmp_path) is False
