"""Tests for the StrategicCombatGroups.ndf parser."""
from __future__ import annotations

from wif_ag_tool.parser.combatgroup_parser import parse_combat_groups


def test_parse_two_combat_groups(fixture_combatgroups_path):
    cgs = parse_combat_groups(fixture_combatgroups_path)
    assert set(cgs.keys()) == {
        "Descriptor_CombatGroup_pion_TEST_Alpha_1_HQ",
        "Descriptor_CombatGroup_pion_TEST_Alpha_1_A",
    }


def test_combat_group_token_extracted(fixture_combatgroups_path):
    cgs = parse_combat_groups(fixture_combatgroups_path)
    assert cgs["Descriptor_CombatGroup_pion_TEST_Alpha_1_HQ"].token == "AAAAAAAAAA"
    assert cgs["Descriptor_CombatGroup_pion_TEST_Alpha_1_A"].token == "CCCCCCCCCC"


def test_hq_smart_group_flagged(fixture_combatgroups_path):
    cgs = parse_combat_groups(fixture_combatgroups_path)
    hq_cg = cgs["Descriptor_CombatGroup_pion_TEST_Alpha_1_HQ"]
    assert len(hq_cg.smart_groups) == 1
    assert hq_cg.smart_groups[0].is_hq is True
    assert hq_cg.smart_groups[0].pack_indices == [(0, 1)]


def test_non_hq_smart_group(fixture_combatgroups_path):
    cgs = parse_combat_groups(fixture_combatgroups_path)
    a_cg = cgs["Descriptor_CombatGroup_pion_TEST_Alpha_1_A"]
    assert a_cg.smart_groups[0].is_hq is False
    assert a_cg.smart_groups[0].pack_indices == [(1, 2), (2, 2)]
