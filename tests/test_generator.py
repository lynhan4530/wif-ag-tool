"""Generator tests."""
from __future__ import annotations

from wif_ag_tool.models import Assignment, DeckState, WifUnit
from wif_ag_tool.generator.pack_generator import generate_pack
from wif_ag_tool.generator.group_generator import generate_combat_group
from wif_ag_tool.generator.deck_patcher import generate_deck_patch
from wif_ag_tool.generator.token_gen import make_token
from wif_ag_tool.generator.localisation import generate_platoons_rows


def test_gen_pack_ndf_syntax():
    out = generate_pack("WF_M1A2_SEPV2_Abrams_US", xp=1)
    assert "is DeckPackDescriptor" in out
    assert "Xp   = 1" in out
    assert "$/GFX/Unit/Descriptor_Unit_WF_M1A2_SEPV2_Abrams_US" in out


def test_gen_pack_no_transport_field():
    out = generate_pack("WF_M1A2_SEPV2_Abrams_US", xp=1)
    assert "Transport" not in out


def test_gen_combat_group_indices_start_at_next():
    deck = DeckState("Descriptor_Deck_pion_TEST_Alpha_1", ["p"] * 5, [])
    a = Assignment("Descriptor_Deck_pion_TEST_Alpha_1", "WF_M1A2_SEPV2_Abrams_US", xp_levels=[1])
    out = generate_combat_group(a, deck, set())
    assert "(5,1)" in out


def test_gen_combat_group_multi_xp_sequential_indices():
    deck = DeckState("Descriptor_Deck_pion_TEST_Alpha_1", ["p"] * 5, [])
    a = Assignment("Descriptor_Deck_pion_TEST_Alpha_1", "WF_M1A2_SEPV2_Abrams_US", xp_levels=[1, 2, 3])
    out = generate_combat_group(a, deck, set())
    assert "(5,1)" in out
    assert "(6,1)" in out
    assert "(7,1)" in out


def test_gen_deck_patch_appends_correct_count():
    patch = generate_deck_patch("TestDeck", ["Pack_A", "Pack_B"], ["Group_A"])
    assert patch.count("~/Pack_") == 2
    assert patch.count("~/Group_") == 1


def test_gen_token_length():
    t = make_token("WF_M1A2_SEPV2_Abrams_US", "Descriptor_Deck_pion_US_11ACR_4")
    assert len(t) == 10


def test_gen_token_uppercase():
    t = make_token("WF_M1A2_SEPV2_Abrams_US", "Descriptor_Deck_pion_US_11ACR_4")
    assert t == t.upper()


def test_gen_token_deterministic():
    t1 = make_token("WF_M1A2_SEPV2_Abrams_US", "Descriptor_Deck_pion_US_11ACR_4")
    t2 = make_token("WF_M1A2_SEPV2_Abrams_US", "Descriptor_Deck_pion_US_11ACR_4")
    assert t1 == t2


def test_gen_localisation_csv_row():
    unit = WifUnit(
        name="WF_M1A2_SEPV2_Abrams_US",
        guid="g",
        nation="US",
        attack=652,
        defense=497,
        xp_bonus=1,
        role="armor",
        name_token="WFM1ASV2",
    )
    row = generate_platoons_rows(
        [Assignment("d", "WF_M1A2_SEPV2_Abrams_US", xp_levels=[1])],
        {"WF_M1A2_SEPV2_Abrams_US": unit},
    )
    assert '";"' in row  # semicolon-quoted separator
    assert '"' in row
