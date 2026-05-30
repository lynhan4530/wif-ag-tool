"""Integration tests covering the full export pipeline using only on-disk fixtures."""
from __future__ import annotations
import json
from pathlib import Path

from wif_ag_tool.models import Assignment
from wif_ag_tool.parser.unit_parser import parse_wif_units
from wif_ag_tool.parser.deck_parser import parse_deck
from wif_ag_tool.pipeline import (
    run_export,
    export_from_replicas,
    load_assignments,
    save_assignments,
    migrate_legacy_assignments,
    PACKS_OUT,
    GROUPS_OUT,
    DECKS_OUT,
    CSV_OUT,
)
from wif_ag_tool import replicas as rmod


DECK_NAME = "Descriptor_Deck_pion_TEST_Alpha_1"


def _build(units_path: Path, deck_path: Path, assignments: list[Assignment]):
    units = parse_wif_units(units_path)
    decks = {DECK_NAME: parse_deck(deck_path, DECK_NAME)}
    return units, decks


def test_full_pipeline_one_unit(tmp_path, fixture_units_path, fixture_deck_path):
    units, decks = _build(fixture_units_path, fixture_deck_path, [])
    a = Assignment(DECK_NAME, "WF_M1A2_SEPV2_Abrams_US", xp_levels=[1])
    paths = run_export([a], decks, units, tmp_path / "out")
    for key in ("packs", "groups", "decks", "csv"):
        assert paths[key].exists()


def test_generated_pack_index_starts_at_zero(tmp_path, fixture_units_path, fixture_deck_path):
    units, decks = _build(fixture_units_path, fixture_deck_path, [])
    a = Assignment(DECK_NAME, "WF_M1A2_SEPV2_Abrams_US", xp_levels=[1])
    paths = run_export([a], decks, units, tmp_path / "out")
    groups_text = paths["groups"].read_text(encoding="utf-8")
    # Full replacement: the deck is rebuilt from scratch, so the first index is 0
    # (not the vanilla pack count).
    assert "(0,1)" in groups_text


def test_idempotent_generation(tmp_path, fixture_units_path, fixture_deck_path):
    units, decks = _build(fixture_units_path, fixture_deck_path, [])
    a = Assignment(DECK_NAME, "WF_M1A2_SEPV2_Abrams_US", xp_levels=[1, 2])
    p1 = run_export([a], decks, units, tmp_path / "out1")
    # Re-parse to avoid mutated DeckState
    units2, decks2 = _build(fixture_units_path, fixture_deck_path, [])
    p2 = run_export([a], decks2, units2, tmp_path / "out2")
    for key in ("packs", "groups", "decks", "csv"):
        assert p1[key].read_text(encoding="utf-8") == p2[key].read_text(encoding="utf-8")


def test_multi_unit_assignment(tmp_path, fixture_units_path, fixture_deck_path):
    units, decks = _build(fixture_units_path, fixture_deck_path, [])
    assignments = [
        Assignment(DECK_NAME, "WF_M1A2_SEPV2_Abrams_US", xp_levels=[1]),
        Assignment(DECK_NAME, "WF_M2A4_Bradley_US", xp_levels=[1]),
        Assignment(DECK_NAME, "WF_T90M_RUS", xp_levels=[1]),
    ]
    paths = run_export(assignments, decks, units, tmp_path / "out")
    packs_text = paths["packs"].read_text(encoding="utf-8")
    assert "Descriptor_StrategicPack_WF_M1A2_SEPV2_Abrams_US_1" in packs_text
    assert "Descriptor_StrategicPack_WF_M2A4_Bradley_US_1" in packs_text
    assert "Descriptor_StrategicPack_WF_T90M_RUS_1" in packs_text


def test_attack_override_in_config(tmp_path):
    a = Assignment(DECK_NAME, "WF_M1A2_SEPV2_Abrams_US", xp_levels=[1], attack_override=300)
    f = tmp_path / "assignments.json"
    save_assignments(f, [a])
    loaded = load_assignments(f)
    assert loaded[0].attack_override == 300


def test_export_produces_three_files(tmp_path, fixture_units_path, fixture_deck_path):
    units, decks = _build(fixture_units_path, fixture_deck_path, [])
    a = Assignment(DECK_NAME, "WF_M1A2_SEPV2_Abrams_US", xp_levels=[1])
    paths = run_export([a], decks, units, tmp_path / "out")
    output_dir = tmp_path / "out"
    assert (output_dir / PACKS_OUT).exists()
    assert (output_dir / GROUPS_OUT).exists()
    assert (output_dir / DECKS_OUT).exists()


# ── replica-driven pipeline ──────────────────────────────────────────────────

def test_export_from_replicas_end_to_end(tmp_path, fixture_units_path, fixture_deck_path):
    units, decks = _build(fixture_units_path, fixture_deck_path, [])
    replicas_file = tmp_path / "wif_replicas.json"
    rmod.save_replica(DECK_NAME, [
        {"unit_id": "WF_M1A2_SEPV2_Abrams_US", "xp": 1, "count": 1, "transport_id": "WF_M2A4_Bradley_US"},
        {"unit_id": "WF_M2A4_Bradley_US", "xp": 2, "count": 1},
    ], path=replicas_file)
    store = rmod.load_replicas(replicas_file)
    paths = export_from_replicas(decks, units, tmp_path / "out", replicas=store)
    packs_text = paths["packs"].read_text(encoding="utf-8")
    groups_text = paths["groups"].read_text(encoding="utf-8")
    assert "Descriptor_StrategicPack_WF_M1A2_SEPV2_Abrams_US_1" in packs_text
    assert "Transport = $/GFX/Unit/Descriptor_Unit_WF_M2A4_Bradley_US" in packs_text
    assert "Descriptor_StrategicPack_WF_M2A4_Bradley_US_2" in packs_text
    # Full replacement: indices count from 0
    assert "(0,1)" in groups_text
    assert "(1,1)" in groups_text


def test_pack_index_invariant_raises_on_mismatch():
    """The defense-in-depth assertion must trip if a future generator regression
    causes SmartGroup tuple sum to drift from DeckPackList growth."""
    import pytest
    from wif_ag_tool.pipeline import _assert_pack_index_invariant

    # 1 assignment with count=6 → expects 6 pack refs appended. Pretend only 1 was.
    a = Assignment(DECK_NAME, "WF_M1A2_SEPV2_Abrams_US", xp_levels=[1], count=6)
    with pytest.raises(ValueError, match="Pack-index invariant violated"):
        _assert_pack_index_invariant(DECK_NAME, [a], new_pack_refs_added=1)

    # Matching case must NOT raise.
    _assert_pack_index_invariant(DECK_NAME, [a], new_pack_refs_added=6)


def test_export_from_replicas_count_duplicates_pack_refs(tmp_path, fixture_units_path, fixture_deck_path):
    """count>1: DeckPackList must contain `count` consecutive refs per pack, and the
    SmartGroup tuple must read `count` slots starting at the assignment's start index."""
    units, decks = _build(fixture_units_path, fixture_deck_path, [])
    replicas_file = tmp_path / "wif_replicas.json"
    rmod.save_replica(DECK_NAME, [
        {"unit_id": "WF_M1A2_SEPV2_Abrams_US", "xp": 1, "count": 6},
        {"unit_id": "WF_M2A4_Bradley_US", "xp": 1, "count": 4},
    ], path=replicas_file)
    store = rmod.load_replicas(replicas_file)
    paths = export_from_replicas(decks, units, tmp_path / "out", replicas=store)
    decks_text = paths["decks"].read_text(encoding="utf-8")
    groups_text = paths["groups"].read_text(encoding="utf-8")

    # DeckPackList patch must contain 6 Abrams + 4 Bradley refs
    assert decks_text.count("~/Descriptor_StrategicPack_WF_M1A2_SEPV2_Abrams_US_1") == 6
    assert decks_text.count("~/Descriptor_StrategicPack_WF_M2A4_Bradley_US_1") == 4

    # Full replacement: Abrams runs [0..5] = (0,6); Bradley starts at 6 = (6,4)
    assert "(0,6)" in groups_text
    assert "(6,4)" in groups_text


def test_replicas_export_seq_disambiguates_duplicates(tmp_path, fixture_units_path, fixture_deck_path):
    units, decks = _build(fixture_units_path, fixture_deck_path, [])
    replicas_file = tmp_path / "wif_replicas.json"
    rmod.save_replica(DECK_NAME, [
        {"unit_id": "WF_M1A2_SEPV2_Abrams_US", "xp": 1, "count": 1, "group_name": "A"},
        {"unit_id": "WF_M1A2_SEPV2_Abrams_US", "xp": 3, "count": 1, "group_name": "B"},
    ], path=replicas_file)
    store = rmod.load_replicas(replicas_file)
    paths = export_from_replicas(decks, units, tmp_path / "out", replicas=store)
    packs_text = paths["packs"].read_text(encoding="utf-8")
    groups_text = paths["groups"].read_text(encoding="utf-8")
    # First seq has no suffix; second gets _1
    assert "Descriptor_StrategicPack_WF_M1A2_SEPV2_Abrams_US_1" in packs_text
    assert "Descriptor_StrategicPack_WF_M1A2_SEPV2_Abrams_US_1_3" in packs_text
    # Group A maps to the deck's vanilla combat group → reuses its vanilla name (required so
    # AG can load the deck). Group B has no vanilla match → WIF name.
    assert "Descriptor_CombatGroup_pion_TEST_Alpha_1_A is" in groups_text
    assert "Descriptor_CombatGroup_TEST_Alpha_1_WIF_B is" in groups_text
    # The unmatched vanilla group (HQ) is preserved and appended
    assert "Descriptor_CombatGroup_pion_TEST_Alpha_1_HQ is" in groups_text


def test_migrate_legacy_assignments(tmp_path):
    legacy = tmp_path / "assignments.json"
    target = tmp_path / "wif_replicas.json"
    save_assignments(legacy, [
        Assignment(DECK_NAME, "WF_M1A2_SEPV2_Abrams_US", xp_levels=[1, 2]),
    ])
    n = migrate_legacy_assignments(legacy_path=legacy, replicas_path=target)
    assert n == 1
    store = rmod.load_replicas(target)
    entry = store[DECK_NAME]
    # Now hierarchical
    units = entry["groups"][0]["platoons"][0]["units"]
    assert len(units) == 2          # XP1 + XP2 each become a row
    assert units[0]["xp"] == 1
    assert units[1]["xp"] == 2
    # legacy renamed
    assert not legacy.exists()
    assert (tmp_path / "assignments.json.migrated").exists()
