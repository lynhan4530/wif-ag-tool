"""Integration tests covering the full export pipeline using only on-disk fixtures."""
from __future__ import annotations
import json
from pathlib import Path

from wif_ag_tool.models import Assignment
from wif_ag_tool.parser.unit_parser import parse_wif_units
from wif_ag_tool.parser.deck_parser import parse_deck
from wif_ag_tool.pipeline import (
    run_export,
    load_assignments,
    save_assignments,
    PACKS_OUT,
    GROUPS_OUT,
    DECKS_OUT,
    CSV_OUT,
)


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


def test_generated_pack_index_matches_next(tmp_path, fixture_units_path, fixture_deck_path):
    units, decks = _build(fixture_units_path, fixture_deck_path, [])
    a = Assignment(DECK_NAME, "WF_M1A2_SEPV2_Abrams_US", xp_levels=[1])
    paths = run_export([a], decks, units, tmp_path / "out")
    groups_text = paths["groups"].read_text(encoding="utf-8")
    # Sample deck has 5 packs → first new index must be 5
    assert "(5,1)" in groups_text


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
