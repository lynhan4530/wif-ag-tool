from pathlib import Path

from wif_ag_tool.parser.division_parser import parse_divisions

FIX = Path(__file__).parent / "fixtures" / "sample_divisions.ndf"


def test_parse_extracts_cfg_name_and_token():
    d = parse_divisions(FIX)
    div = d["RDA_10MSD_solo"]
    assert div.cfg_name == "RDA_10MSD_solo"
    assert div.division_name_token == "DIV10MSD"
    assert div.coalition == "PACT"
    assert "RDA" in div.tags


def test_parse_handles_missing_division_name():
    d = parse_divisions(FIX)
    div = d["TEST_NoToken_solo"]
    assert div.cfg_name == "TEST_NoToken_solo"
    assert div.division_name_token == ""
    assert div.coalition == "NATO"


def test_parse_returns_dict_keyed_by_cfg_name():
    d = parse_divisions(FIX)
    assert "RDA_10MSD_solo" in d
    assert "TEST_NoToken_solo" in d
    assert len(d) == 2


def test_parse_extracts_emblem_texture():
    d = parse_divisions(FIX)
    assert d["RDA_10MSD_solo"].emblem_texture == "Texture_Division_Emblem_RDA_10MSD"
