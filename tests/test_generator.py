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
    generator_out = generate_pack(a.unit_id, xp=2, seq=a.seq, deck_name=a.deck_name)
    expected_name = a.pack_name(2)
    assert expected_name == "Descriptor_StrategicPack_M1A1_Abrams_US_v_US_11ACR_1_2"
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


def test_replace_deck_lists_overwrites_only_target_deck(tmp_path):
    """replace_deck_lists rewrites the target deck's two lists wholesale and leaves
    every other deck (and the rest of the target block) untouched."""
    from wif_ag_tool.generator.deck_patcher import replace_deck_lists

    ndf = tmp_path / "StrategicDecks.ndf"
    ndf.write_text(
        "export Descriptor_Deck_pion_US_A is TDeckDescriptor\n"
        "(\n"
        "    DeckIdentifier = 'pion_US_A'\n"
        "    DeckPackList =\n"
        "    [\n"
        "        ~/Descriptor_StrategicPack_VANILLA_1,\n"
        "        ~/Descriptor_StrategicPack_VANILLA_2,\n"
        "    ]\n"
        "    DeckCombatGroupList =\n"
        "    [\n"
        "        ~/Descriptor_CombatGroup_VANILLA_A,\n"
        "    ]\n"
        ")\n"
        "\n"
        "export Descriptor_Deck_pion_US_B is TDeckDescriptor\n"
        "(\n"
        "    DeckPackList =\n"
        "    [\n"
        "        ~/Descriptor_StrategicPack_KEEPME,\n"
        "    ]\n"
        "    DeckCombatGroupList =\n"
        "    [\n"
        "        ~/Descriptor_CombatGroup_KEEPME,\n"
        "    ]\n"
        ")\n",
        encoding="utf-8",
    )

    replace_deck_lists(
        ndf, "Descriptor_Deck_pion_US_A",
        ["Descriptor_StrategicPack_WF_NEW_1", "Descriptor_StrategicPack_WF_NEW_1"],
        ["Descriptor_CombatGroup_US_A_WIF_A"],
    )
    out = ndf.read_text(encoding="utf-8")

    # Target deck: vanilla refs gone, exactly the new refs present (2 dup pack refs).
    assert "VANILLA_1" not in out and "VANILLA_2" not in out
    assert "Descriptor_CombatGroup_VANILLA_A" not in out
    assert out.count("~/Descriptor_StrategicPack_WF_NEW_1,") == 2
    assert out.count("~/Descriptor_CombatGroup_US_A_WIF_A,") == 1
    # Non-list content of the target block is preserved.
    assert "DeckIdentifier = 'pion_US_A'" in out
    # The other deck is completely untouched.
    assert "~/Descriptor_StrategicPack_KEEPME," in out
    assert "~/Descriptor_CombatGroup_KEEPME," in out

    # Re-parsing confirms the structure is still valid and reflects the replacement.
    from wif_ag_tool.parser.deck_parser import parse_deck
    d = parse_deck(ndf, "Descriptor_Deck_pion_US_A")
    assert d.pack_list == ["Descriptor_StrategicPack_WF_NEW_1", "Descriptor_StrategicPack_WF_NEW_1"]
    assert d.combat_group_list == ["Descriptor_CombatGroup_US_A_WIF_A"]
    d_b = parse_deck(ndf, "Descriptor_Deck_pion_US_B")
    assert d_b.pack_list == ["Descriptor_StrategicPack_KEEPME"]


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
    # Emission order is HQ → numbered → named → SPT → ungrouped, AND pack indices are
    # assigned in that same emission order, so the tuples ascend contiguously 0,1,2,3,4
    # (vanilla shape). A scrambled, non-monotonic layout hangs the AG campaign loader.
    lines = out.split("\n")
    pack_lines = [l.strip() for l in lines if l.strip().startswith("(") and l.strip().endswith(",")]
    assert pack_lines[0] == "(0,1),"   # HQ (emitted first → first index)
    assert pack_lines[1] == "(1,1),"   # "2" (numbered)
    assert pack_lines[2] == "(2,1),"   # "1ST RECON PLATOON" (named)
    assert pack_lines[3] == "(3,1),"   # SPT
    assert pack_lines[4] == "(4,1),"   # ungrouped


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


def test_combat_group_uses_wif_name_not_vanilla():
    """Full-replacement model: generated combat groups always use the WIF descriptor
    name; they never reuse / merge into a vanilla combat group."""
    from wif_ag_tool.generator.group_generator import generate_grouped_combat_group, wif_cg_name

    a = Assignment("Descriptor_Deck_pion_US_11ACR_4", "WF_M1A2_Abrams",
                   xp_levels=[1], group_name="A", sub_group="HQ")
    deck = DeckState("Descriptor_Deck_pion_US_11ACR_4", [], [])
    out = generate_grouped_combat_group("A", deck.name, [a], deck, set(), is_hq=True)

    assert wif_cg_name(deck.name, "A") == "Descriptor_CombatGroup_US_11ACR_4_WIF_A"
    assert "Descriptor_CombatGroup_US_11ACR_4_WIF_A is TDeckCombatGroupDescriptor" in out
    assert "IsHQ = True" in out


def test_build_export_blocks_replaces_from_index_zero():
    """build_export_blocks treats each deck as a clean slate: pack indices start at 0
    regardless of the vanilla deck's existing pack count, and deck_lists holds exactly
    the replica-derived refs (full replacement)."""
    from wif_ag_tool.pipeline import build_export_blocks

    deck_name = "Descriptor_Deck_pion_US_11ACR_4"
    # Vanilla deck already has 92 packs / 7 groups — none of which should leak through.
    decks = {deck_name: DeckState(deck_name, ["vanilla_pack"] * 92,
                                  ["vanilla_cg"] * 7)}
    assignments = [
        Assignment(deck_name, "WF_M1A2_Abrams", xp_levels=[1], count=2,
                   group_name="A", sub_group="1", order=0),
        Assignment(deck_name, "WF_T90M_RUS", xp_levels=[1], count=1,
                   group_name="A", sub_group="2", order=1, seq=1),
    ]
    packs_blocks, groups_blocks, deck_lists = build_export_blocks(assignments, decks, {}, {})

    pack_refs, group_refs = deck_lists[deck_name]
    # Exactly the replica's packs: 2 copies of the first unit + 1 of the second.
    assert len(pack_refs) == 3
    assert not any(r == "vanilla_pack" for r in pack_refs)
    # Exactly one WIF combat group, named for the replica group — no vanilla groups.
    assert group_refs == ["Descriptor_CombatGroup_US_11ACR_4_WIF_A"]
    # Indices start at 0 (clean slate), not at the vanilla pack count (92).
    one_group = groups_blocks[0]
    assert "(0,2)," in one_group   # first unit, count 2, at index 0
    assert "(2,1)," in one_group   # second unit, count 1, at index 2


def test_combat_group_tuples_monotonic_and_refs_aligned():
    """Regression for the AG campaign-loader hang: when platoon names reorder under the
    tactical sort, the combat group's (start,count) tuples must still ascend contiguously
    (vanilla shape) AND the DeckPackList refs must line up with the tuples slot-for-slot."""
    import re
    from wif_ag_tool.pipeline import build_export_blocks

    deck_name = "Descriptor_Deck_pion_US_X"
    decks = {deck_name: DeckState(deck_name, ["v"] * 50, ["cg"] * 3)}
    # Replica order (Zulu, Alpha, Mike) differs from the tactical/alphabetical emission
    # order (Alpha, Mike, Zulu) — exactly the situation that scrambled indices before.
    assignments = [
        Assignment(deck_name, "WF_ZZZ", xp_levels=[1], count=2, group_name="A", sub_group="Zulu Plt", order=0),
        Assignment(deck_name, "WF_AAA", xp_levels=[1], count=3, group_name="A", sub_group="Alpha Plt", order=1, seq=1),
        Assignment(deck_name, "WF_MMM", xp_levels=[1], count=1, group_name="A", sub_group="Mike Plt", order=2, seq=2),
    ]
    _packs, groups_blocks, deck_lists = build_export_blocks(assignments, decks, {}, {})
    pack_refs, _groups = deck_lists[deck_name]
    block = groups_blocks[0]
    tuples = [(int(a), int(b)) for a, b in re.findall(r"\((\d+),(\d+)\)", block)]

    # Tuples ascend contiguously and cover the whole DeckPackList with no gap/overlap.
    pos = 0
    for start, count in tuples:
        assert start == pos, f"non-monotonic/gap at {pos}: {tuples}"
        pos += count
    assert pos == len(pack_refs), "tuples don't cover the whole DeckPackList"

    # Refs are laid out in emission order (Alpha×3, Mike×1, Zulu×2) so each tuple's start
    # slot holds that platoon's unit.
    assert pack_refs[0].startswith("Descriptor_StrategicPack_WF_AAA")
    assert pack_refs[3].startswith("Descriptor_StrategicPack_WF_MMM")
    assert pack_refs[4].startswith("Descriptor_StrategicPack_WF_ZZZ")


def test_build_export_blocks_reuses_vanilla_combat_group_name_and_token():
    """A replica group that maps to a deck's vanilla combat group must reuse that vanilla
    NAME + TOKEN — the AG campaign binds pre-placed battalions to vanilla combat-group names,
    so renaming hangs the loader. Content is still fully replaced with the replica's units."""
    from wif_ag_tool.pipeline import build_export_blocks
    from wif_ag_tool.parser.combatgroup_parser import CombatGroup

    deck_name = "Descriptor_Deck_pion_US_11ACR_1"
    vanilla_cg = "Descriptor_CombatGroup_pion_US_11ACR_1_A_1_11th_ACR"
    decks = {deck_name: DeckState(deck_name, ["v"] * 30, [vanilla_cg])}
    combat_groups = {vanilla_cg: CombatGroup(name=vanilla_cg, token="VANILLATOK", smart_groups=[])}
    assignments = [
        Assignment(deck_name, "WF_M1A2_Abrams", xp_levels=[1], count=2,
                   group_name="A", sub_group="1"),
    ]
    _packs, groups_blocks, deck_lists = build_export_blocks(assignments, decks, {}, combat_groups)
    _pack_refs, group_refs = deck_lists[deck_name]

    # Deck references the VANILLA combat-group name (not _WIF_A).
    assert group_refs == [vanilla_cg]
    # The emitted block reuses the vanilla name + vanilla token, with WIF content.
    block = groups_blocks[0]
    assert f"{vanilla_cg} is TDeckCombatGroupDescriptor" in block
    assert 'Name = "VANILLATOK"' in block
    assert "(0,2)," in block  # the WIF unit's content, ascending from index 0


def test_build_export_blocks_enforces_pack_index_invariant():
    """A drifted (start,count) sum must raise before anything is written."""
    import pytest
    from wif_ag_tool.pipeline import build_export_blocks, _assert_pack_index_invariant

    deck_name = "Descriptor_Deck_pion_US_11ACR_4"
    # Sanity: the invariant helper raises when the numbers disagree.
    with pytest.raises(ValueError):
        _assert_pack_index_invariant(
            deck_name,
            [Assignment(deck_name, "WF_X", xp_levels=[1], count=6)],
            1,  # pretend only 1 ref was built for a 6-slot tuple
        )

