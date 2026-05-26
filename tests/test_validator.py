"""Validator tests."""
from __future__ import annotations
import pytest

from wif_ag_tool.models import DeckState, WifUnit
from wif_ag_tool.validator.unit_validator import validate_unit_exists, UnitNotFoundError
from wif_ag_tool.validator.index_validator import validate_pack_index, IndexOutOfBoundsError
from wif_ag_tool.validator.token_validator import validate_token, TokenLengthError


def _dummy_unit() -> WifUnit:
    return WifUnit(
        name="WF_M1A2_SEPV2_Abrams_US",
        guid="g", nation="US", attack=1, defense=1, xp_bonus=1,
        role="armor", name_token="X",
    )


def test_valid_unit_exists():
    validate_unit_exists("WF_M1A2_SEPV2_Abrams_US", {"WF_M1A2_SEPV2_Abrams_US": _dummy_unit()})


def test_invalid_unit_raises():
    with pytest.raises(UnitNotFoundError):
        validate_unit_exists("WF_NONEXISTENT", {})


def test_valid_index_in_bounds():
    deck = DeckState("d", ["p"] * 5, [])
    validate_pack_index(5, deck)  # 5 == next_index, valid for new append


def test_invalid_index_out_of_bounds_raises():
    deck = DeckState("d", ["p"] * 5, [])
    with pytest.raises(IndexOutOfBoundsError):
        validate_pack_index(6, deck)


def test_token_valid_length():
    validate_token("ABCDEFGHIJ")


def test_token_invalid_length_raises():
    with pytest.raises(TokenLengthError):
        validate_token("TOOSHORT")
