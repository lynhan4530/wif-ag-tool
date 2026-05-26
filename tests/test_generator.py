"""Generator tests."""
from __future__ import annotations

from wif_ag_tool.models import Assignment, DeckState, WifUnit
from wif_ag_tool.generator.pack_generator import generate_pack
from wif_ag_tool.generator.group_generator import generate_combat_group, generate_grouped_combat_group
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


# ── Sub-group / platoon tests ────────────────────────────────────────────────

def _make_deck(n_packs=5):
    return DeckState("Descriptor_Deck_pion_US_11ACR_4", ["p"] * n_packs, [])


def _make_unit(name="WF_M1A2_SEPV2_Abrams_US"):
    return WifUnit(name=name, guid="g", nation="US", attack=100, defense=100,
                   xp_bonus=1, role="armor", name_token="TK")


def test_grouped_smart_group_aggregates_pack_indices():
    """Two assignments sharing sub_group='HQ' → one smart group with both indices."""
    deck = _make_deck(0)
    a1 = Assignment("Descriptor_Deck_pion_US_11ACR_4", "WF_Unit_A", xp_levels=[1],
                     group_name="A", sub_group="HQ", order=0)
    a2 = Assignment("Descriptor_Deck_pion_US_11ACR_4", "WF_Unit_B", xp_levels=[1],
                     group_name="A", sub_group="HQ", order=1)
    out = generate_grouped_combat_group("A", deck.name, [a1, a2], deck, set())
    # Both should contribute pack indices: (0,1), (1,1)
    assert "(0,1)" in out
    assert "(1,1)" in out
    # There should be one SmartGroup block for "HQ" with IsHQ = True
    assert "IsHQ = True" in out
    # Count TDeckSmartGroupDescriptor occurrences — should be exactly 1
    assert out.count("TDeckSmartGroupDescriptor") == 1


def test_grouped_smart_group_tactical_sort_order():
    """Smart groups sort: HQ → numbered → named → SPT → ungrouped."""
    deck = _make_deck(0)
    a_spt = Assignment("Descriptor_Deck_pion_US_11ACR_4", "WF_SPT", xp_levels=[1],
                        group_name="A", sub_group="SPT", order=3)
    a_recon = Assignment("Descriptor_Deck_pion_US_11ACR_4", "WF_RECON", xp_levels=[1],
                          group_name="A", sub_group="1ST RECON PLATOON", order=2)
    a_hq = Assignment("Descriptor_Deck_pion_US_11ACR_4", "WF_HQ", xp_levels=[1],
                       group_name="A", sub_group="HQ", order=0)
    a_ungrouped = Assignment("Descriptor_Deck_pion_US_11ACR_4", "WF_SOLO", xp_levels=[1],
                              group_name="A", sub_group=None, order=4)
    a_num = Assignment("Descriptor_Deck_pion_US_11ACR_4", "WF_NUM", xp_levels=[1],
                        group_name="A", sub_group="2", order=1)

    out = generate_grouped_combat_group(
        "A", deck.name, [a_spt, a_recon, a_hq, a_ungrouped, a_num], deck, set()
    )
    # Verify sort order by checking pack index positions:
    # HQ → index 2, NUM → index 4, RECON → index 1, SPT → index 0, UNGROUPED → index 3
    # In output: HQ(2,1), NUM(4,1), RECON(1,1), SPT(0,1), UNGROUPED(3,1)
    lines = out.split("\n")
    pack_lines = [l.strip() for l in lines if l.strip().startswith("(") and l.strip().endswith(",")]
    # HQ should be first, then numbered ("2"), then named ("1ST RECON PLATOON"), then SPT, then ungrouped
    assert pack_lines[0] == "(2,1),"   # HQ
    assert pack_lines[1] == "(4,1),"   # "2" (numbered)
    assert pack_lines[2] == "(1,1),"   # "1ST RECON PLATOON" (named)
    assert pack_lines[3] == "(0,1),"   # SPT
    assert pack_lines[4] == "(3,1),"   # ungrouped


def test_localisation_sub_group_display_names():
    """Sub-grouped assignments get human-readable platoon names in PLATOONS.csv."""
    unit = _make_unit()
    units = {unit.name: unit}
    assignments = [
        Assignment("d", unit.name, xp_levels=[1], group_name="A",
                   sub_group="HQ", order=0),
        Assignment("d", unit.name, xp_levels=[1], group_name="A",
                   sub_group="SPT", order=1, seq=1),
        Assignment("d", unit.name, xp_levels=[1], group_name="A",
                   sub_group="1ST RECON PLATOON", order=2, seq=2),
    ]
    csv = generate_platoons_rows(assignments, units)
    # Named groups get their name directly
    assert "1ST RECON PLATOON" in csv
    # HQ group → "WIF — A HQ"
    assert "WIF — A HQ" in csv
    # SPT group → "WIF — A SUPPORT"
    assert "WIF — A SUPPORT" in csv


def test_localisation_ungrouped_shows_unit_name():
    """Ungrouped (no sub_group) assignments produce WIF unit name in CSV."""
    unit = _make_unit("WF_Leopard_2A7_GER")
    units = {unit.name: unit}
    assignments = [
        Assignment("d", unit.name, xp_levels=[2], group_name="B",
                   sub_group=None, order=0),
    ]
    csv = generate_platoons_rows(assignments, units)
    # Should contain the pretty unit id
    assert "Leopard 2A7 GER" in csv


def test_replicas_hierarchical_save_and_flatten(tmp_path):
    """Hierarchical save produces groups and flatten correctly yields assignments."""
    from wif_ag_tool import replicas as rmod

    f = tmp_path / "wif_replicas.json"
    rmod.save_replica("Deck_A", [
        {"name": "HQ", "platoons": [
            {"name": "TROOP HQ", "units": [
                {"unit_id": "WF_M1A2", "xp": 1, "count": 2},
                {"unit_id": "WF_M577", "xp": 1, "count": 1},
            ]}
        ]},
        {"name": "A", "platoons": [
            {"name": "1ST RECON PLATOON", "units": [
                {"unit_id": "WF_M3A3", "xp": 2, "count": 1},
            ]}
        ]},
    ], path=f)

    store = rmod.load_replicas(f)
    entry = store["Deck_A"]
    assert len(entry["groups"]) == 2
    assert entry["groups"][0]["name"] == "HQ"
    assert entry["groups"][0]["platoons"][0]["name"] == "TROOP HQ"
    assert len(entry["groups"][0]["platoons"][0]["units"]) == 2

    # Flatten to assignments
    asn = rmod.replicas_to_assignments(store)
    assert len(asn) == 3
    # Check sub_group is set correctly
    hq_asn = [a for a in asn if a.group_name == "HQ"]
    assert all(a.sub_group == "TROOP HQ" for a in hq_asn)
    a_asn = [a for a in asn if a.group_name == "A"]
    assert all(a.sub_group == "1ST RECON PLATOON" for a in a_asn)
