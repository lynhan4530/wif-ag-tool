"""Parser tests — all use tests/fixtures/, never real game files."""
from __future__ import annotations

from wif_ag_tool.parser.unit_parser import parse_wif_units
from wif_ag_tool.parser.deck_parser import parse_deck, list_decks
from wif_ag_tool.parser.pack_parser import parse_strategic_packs


def test_parse_unit_extracts_guid(fixture_units_path):
    units = parse_wif_units(fixture_units_path)
    assert units["WF_M1A2_SEPV2_Abrams_US"].guid == "454ef2bc-ff1e-42fd-9c64-7988718c197d"


def test_parse_unit_extracts_strategic_values(fixture_units_path):
    units = parse_wif_units(fixture_units_path)
    u = units["WF_M1A2_SEPV2_Abrams_US"]
    assert u.attack == 652
    assert u.defense == 497
    assert u.xp_bonus == 1


def test_parse_unit_extracts_name_token(fixture_units_path):
    units = parse_wif_units(fixture_units_path)
    assert units["WF_M1A2_SEPV2_Abrams_US"].name_token == "WFM1ASV2"


def test_parse_unit_extracts_nation(fixture_units_path):
    units = parse_wif_units(fixture_units_path)
    assert units["WF_M1A2_SEPV2_Abrams_US"].nation == "US"


def test_parse_units_filter_by_nation(fixture_units_path):
    units = parse_wif_units(fixture_units_path, nation_filter="RUS")
    assert list(units.keys()) == ["WF_T90M_RUS"]


def test_parse_deck_pack_list_order(fixture_deck_path):
    deck = parse_deck(fixture_deck_path, "Descriptor_Deck_pion_TEST_Alpha_1")
    assert deck.pack_list[0] == "Descriptor_StrategicPack_UnitA_1"
    assert deck.pack_list[4] == "Descriptor_StrategicPack_UnitB_1"


def test_parse_deck_next_index(fixture_deck_path):
    deck = parse_deck(fixture_deck_path, "Descriptor_Deck_pion_TEST_Alpha_1")
    assert deck.next_index == 5


def test_parse_strategic_pack_no_transport(fixture_packs_path):
    packs = parse_strategic_packs(fixture_packs_path)
    p = packs["Descriptor_StrategicPack_UnitA_1"]
    assert p.xp == 1
    assert "Descriptor_Unit_UnitA" in p.unit
    assert p.transport is None


def test_parse_strategic_pack_with_transport(fixture_packs_path):
    packs = parse_strategic_packs(fixture_packs_path)
    p = packs["Descriptor_StrategicPack_WithTransport_0"]
    assert p.transport is not None
    assert "Descriptor_Unit_VehicleX" in p.transport


def test_list_decks_returns_all_pion(fixture_deck_path):
    names = list_decks(fixture_deck_path)
    assert "Descriptor_Deck_pion_TEST_Alpha_1" in names
    assert "Descriptor_Deck_pion_TEST_Bravo_1" in names
