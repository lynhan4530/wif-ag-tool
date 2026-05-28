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


def test_gen_pack_wif_unit_name_format():
    """WIF units keep the historical pack name format — no _v marker."""
    out = generate_pack("WF_M1A2_SEPV2_Abrams_US", xp=2, seq=0)
    assert "Descriptor_StrategicPack_WF_M1A2_SEPV2_Abrams_US_2 is DeckPackDescriptor" in out
    out_seq = generate_pack("WF_M1A2_SEPV2_Abrams_US", xp=2, seq=3)
    assert "Descriptor_StrategicPack_WF_M1A2_SEPV2_Abrams_US_3_2 is DeckPackDescriptor" in out_seq


def test_gen_pack_vanilla_unit_gets_v_marker():
    """Vanilla units must get a _v marker so the generated descriptor name doesn't
    collide with the pack Eugen already ships in StrategicPacks.ndf for the same
    unit+xp combo. Without this, the NDF compiler refuses duplicate definitions."""
    out = generate_pack("M1A1_Abrams_US", xp=2, seq=0)
    assert "Descriptor_StrategicPack_M1A1_Abrams_US_v_2 is DeckPackDescriptor" in out
    # seq>0 still works and stays unique
    out_seq = generate_pack("M1A1_Abrams_US", xp=2, seq=1)
    assert "Descriptor_StrategicPack_M1A1_Abrams_US_v_1_2 is DeckPackDescriptor" in out_seq
    # Unit ref points at the actual vanilla descriptor — only the pack name changes
    assert "$/GFX/Unit/Descriptor_Unit_M1A1_Abrams_US" in out


def test_assignment_pack_name_matches_generator_for_vanilla():
    """Assignment.pack_name and generate_pack must produce the same descriptor name
    or DeckPackList refs and pack definitions won't line up."""
    a = Assignment("Descriptor_Deck_pion_US_11ACR_1", "M1A1_Abrams_US", xp_levels=[2], count=4)
    generator_out = generate_pack(a.unit_id, xp=2, seq=a.seq)
    expected_name = a.pack_name(2)
    assert expected_name == "Descriptor_StrategicPack_M1A1_Abrams_US_v_2"
    assert f"{expected_name} is DeckPackDescriptor" in generator_out


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


def test_gen_combat_group_count_emits_consecutive_run_tuple():
    """count>1 → single SmartGroup tuple (start, count) covering count consecutive slots."""
    deck = DeckState("Descriptor_Deck_pion_TEST_Alpha_1", ["p"] * 5, [])
    a = Assignment(
        "Descriptor_Deck_pion_TEST_Alpha_1",
        "WF_M1A2_SEPV2_Abrams_US",
        xp_levels=[1],
        count=6,
    )
    out = generate_combat_group(a, deck, set())
    # Engine reads 6 consecutive packs starting at index 5
    assert "(5,6)" in out
    # A second tuple at (5,1) or (6,1) would mean overlap → none must be present
    assert "(6,6)" not in out


def test_gen_combat_group_multi_xp_count_offsets_by_count():
    """Two XP levels with count=6 → tuples (s, 6) and (s+6, 6), NOT (s, 6) (s+1, 6)."""
    deck = DeckState("Descriptor_Deck_pion_TEST_Alpha_1", ["p"] * 5, [])
    a = Assignment(
        "Descriptor_Deck_pion_TEST_Alpha_1",
        "WF_M1A2_SEPV2_Abrams_US",
        xp_levels=[1, 2],
        count=6,
    )
    out = generate_combat_group(a, deck, set())
    assert "(5,6)" in out
    assert "(11,6)" in out
    # No overlapping window like (6,6)/(7,6)
    assert "(6,6)" not in out
    assert "(7,6)" not in out


def test_grouped_smart_group_count_accumulates_across_assignments():
    """Two count>1 assignments in one combat group: second starts past first's full run."""
    deck = DeckState("Descriptor_Deck_pion_TEST_Alpha_1", [], [])
    a1 = Assignment(
        "Descriptor_Deck_pion_TEST_Alpha_1",
        "WF_M1A2_SEPV2_Abrams_US",
        xp_levels=[1],
        count=6,
        group_name="A",
        sub_group="1",
        order=0,
    )
    a2 = Assignment(
        "Descriptor_Deck_pion_TEST_Alpha_1",
        "WF_M2A4_Bradley_US",
        xp_levels=[1],
        count=4,
        group_name="A",
        sub_group="2",
        order=1,
    )
    out = generate_grouped_combat_group("A", deck.name, [a1, a2], deck, set())
    # First assignment occupies indices 0..5 → tuple (0,6)
    assert "(0,6)" in out
    # Second assignment must start at 6 (not 1) → tuple (6,4)
    assert "(6,4)" in out


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


def test_smart_group_token_matching():
    from wif_ag_tool.generator.group_generator import align_and_order_smart_groups, generate_grouped_combat_group
    from wif_ag_tool.parser.combatgroup_parser import SmartGroup, CombatGroup
    
    v_sg1 = SmartGroup(name="VANILLA_HQ_TOKEN", is_hq=True)
    v_sg2 = SmartGroup(name="VANILLA_PLT_TOKEN", is_hq=False)
    
    a1 = Assignment("d", "WF_Unit_HQ", xp_levels=[1], group_name="A", sub_group="HQ")
    a2 = Assignment("d", "WF_Unit_Plt", xp_levels=[1], group_name="A", sub_group="1")
    
    smart_group_items = [
        ("HQ", [a1]),
        ("1", [a2]),
    ]
    
    aligned = align_and_order_smart_groups(
        smart_group_items=smart_group_items,
        vanilla_smart_groups=[v_sg1, v_sg2],
        deck_name="d",
        gname="A",
        existing_tokens=set()
    )
    assert aligned[0] == ("VANILLA_HQ_TOKEN", True, [a1])
    assert aligned[1] == ("VANILLA_PLT_TOKEN", False, [a2])

    deck = DeckState("d", ["p"]*5, [])
    out = generate_grouped_combat_group(
        gname="A",
        deck_name="d",
        assignments=[a1, a2],
        deck_state=deck,
        existing_tokens=set(),
        vanilla_smart_groups=[v_sg1, v_sg2]
    )
    assert "VANILLA_HQ_TOKEN" in out
    assert "VANILLA_PLT_TOKEN" in out
    assert "IsHQ = True" in out

    cg = CombatGroup(name="Descriptor_CombatGroup_d_WIF_A", token="CG_TOKEN", smart_groups=[v_sg1, v_sg2])
    decks = {"d": deck}
    combat_groups = {"Descriptor_CombatGroup_d_WIF_A": cg}
    
    csv_text = generate_platoons_rows(
        assignments=[a1, a2],
        units={},
        decks=decks,
        combat_groups=combat_groups
    )
    assert "VANILLA_HQ_TOKEN" in csv_text
    assert "VANILLA_PLT_TOKEN" in csv_text

