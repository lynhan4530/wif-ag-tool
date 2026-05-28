"""Tests for the role-normalisation table.

The set of raw UnitRole values below was extracted from the live
UniteDescriptor.ndf files (vanilla + WIF) on 2026-05-29. If Eugen or WIF
adds a new role string, add it here with the bucket it should land in.
"""
from __future__ import annotations
import pytest

from wif_ag_tool.role_normalize import (
    CANONICAL_BUCKETS,
    bucket_matches,
    normalize_role,
)


# (raw value as it appears in NDF, primary bucket)
RAW_TO_BUCKET = [
    ("AA",         "aa"),
    ("AT",         "infantry"),     # anti-tank teams are foot
    ("appui",      "supply"),       # French "support" — mortar/aa/supply teams
    ("armor",      "armor"),
    ("engineer",   "engineer"),
    ("howitzer",   "artillery"),
    ("hq_helo",    "helicopter"),   # command helicopter (e.g. UH60 CO)
    ("hq_inf",     "infantry"),     # company command squad
    ("hq_tank",    "armor"),        # M1A1 CMD etc.
    ("hq_veh",     "ifv"),          # command IFV
    ("ifv",        "ifv"),
    ("infantry",   "infantry"),
    ("mlrs",       "artillery"),
    ("mortar",     "artillery"),
    ("reco",       "recon"),
    ("sead",       "plane"),        # anti-radiation strike planes
    ("supply",     "supply"),
    ("transport",  "ifv"),
    ("transport1", "ifv"),
    ("transport2", "ifv"),
    ("transport3", "ifv"),
    ("transport5", "ifv"),
    ("uav",        "plane"),
]


@pytest.mark.parametrize("raw,bucket", RAW_TO_BUCKET)
def test_primary_bucket(raw, bucket):
    assert normalize_role(raw) == bucket, f"{raw!r} should normalise to {bucket!r}"


def test_unknown_role_yields_unknown_bucket():
    assert normalize_role("totally-not-a-real-role") == "unknown"
    assert normalize_role("") == "unknown"
    assert normalize_role(None) == "unknown"


def test_all_canonical_buckets_are_reachable():
    """Every bucket the UI dropdown offers must be the normalise target of at
    least one raw value we've actually seen. Catches a dropdown that promises
    a filter that can never match anything."""
    seen = {normalize_role(raw) for raw, _ in RAW_TO_BUCKET}
    # "command" is multi-bucket so doesn't show up via normalize_role; assert
    # it separately via bucket_matches.
    assert all(b in seen or b == "command" for b in CANONICAL_BUCKETS), \
        f"unreachable buckets: {set(CANONICAL_BUCKETS) - seen - {'command'}}"


def test_bucket_matches_all_passthrough():
    assert bucket_matches("hq_tank", "all") is True
    assert bucket_matches("hq_tank", "") is True


def test_bucket_matches_primary_bucket():
    # hq_tank's primary bucket is armor, NOT infantry
    assert bucket_matches("hq_tank", "armor") is True
    assert bucket_matches("hq_tank", "infantry") is False


def test_bucket_matches_command_overlay():
    """Command is a cross-cutting bucket: every hq_* raw role matches it."""
    for hq_role in ("hq_tank", "hq_inf", "hq_helo", "hq_veh"):
        assert bucket_matches(hq_role, "command") is True, hq_role
    # Non-HQ units never match command, even if they have leader specialties.
    for normal in ("armor", "infantry", "reco", "supply"):
        assert bucket_matches(normal, "command") is False, normal


def test_bucket_matches_empty_or_none_raw():
    assert bucket_matches(None, "armor") is False
    assert bucket_matches("", "armor") is False
    # But "all" still accepts empty raw — listing should not drop unitss
    # whose role didn't parse.
    assert bucket_matches(None, "all") is True
