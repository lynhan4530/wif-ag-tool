"""Shared pytest fixtures. All tests use the on-disk NDF fixtures in tests/fixtures/.

Tests must NEVER touch real game paths (G:\\Warno_mod\\... or G:\\Project\\...).
CI runs on Ubuntu where those paths don't exist.
"""
from __future__ import annotations
from pathlib import Path
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _isolate_vanilla_combat_groups(monkeypatch):
    """run_export/build_export_blocks parse config.VANILLA_COMBAT_GROUPS by default (to
    reuse vanilla combat-group names+tokens). Point it at the fixture so tests never read
    real game paths — CI-safe and deterministic."""
    from wif_ag_tool import config
    monkeypatch.setattr(config, "VANILLA_COMBAT_GROUPS", FIXTURES / "sample_combatgroups.ndf")


@pytest.fixture(scope="session")
def fixture_units_path() -> Path:
    return FIXTURES / "sample_units.ndf"


@pytest.fixture(scope="session")
def fixture_deck_path() -> Path:
    return FIXTURES / "sample_deck.ndf"


@pytest.fixture(scope="session")
def fixture_packs_path() -> Path:
    return FIXTURES / "sample_packs.ndf"


@pytest.fixture(scope="session")
def fixture_combatgroups_path() -> Path:
    return FIXTURES / "sample_combatgroups.ndf"
