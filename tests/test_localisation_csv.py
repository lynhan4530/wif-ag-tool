from pathlib import Path

from wif_ag_tool.parser.localisation_csv import load_units_csv

FIX = Path(__file__).parent / "fixtures" / "sample_units.csv"


def test_load_returns_token_reftext_pairs():
    m = load_units_csv(FIX)
    assert m["WFM1ASV2"] == "M1A2 SEPV2 Abrams"
    assert m["T54B01"] == "T-54B"


def test_load_skips_header_row():
    m = load_units_csv(FIX)
    assert "TOKEN" not in m


def test_load_missing_file_returns_empty_dict(tmp_path):
    assert load_units_csv(tmp_path / "nope.csv") == {}


def test_load_handles_bom(tmp_path):
    p = tmp_path / "u.csv"
    p.write_bytes(b'\xef\xbb\xbf"TOKEN";"REFTEXT"\n"AAA";"hello"\n')
    m = load_units_csv(p)
    assert m["AAA"] == "hello"
