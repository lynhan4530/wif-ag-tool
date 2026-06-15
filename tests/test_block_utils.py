"""Unit tests for wif_ag_tool.parser.block_utils."""
from __future__ import annotations

import pytest
from wif_ag_tool.parser.block_utils import find_matching_bracket, find_block_span


def test_find_matching_bracket_simple():
    text = "abc (def) ghi"
    # start_index is the opening bracket at index 4
    open_idx = text.find("(")
    assert open_idx == 4
    close_idx = find_matching_bracket(text, open_idx)
    assert close_idx == 8
    assert text[close_idx] == ")"


def test_find_matching_bracket_nested():
    text = "(a (b) c (d (e)))"
    # Match outer block
    assert find_matching_bracket(text, 0) == len(text) - 1
    # Match nested block 'e' inside (d (e))
    inner_open = text.find("(e)")
    assert find_matching_bracket(text, inner_open) == inner_open + 2


def test_find_matching_bracket_not_found():
    text = "(abc"
    assert find_matching_bracket(text, 0) is None


def test_find_matching_bracket_custom_chars():
    text = "[a, b, [c, d]]"
    assert find_matching_bracket(text, 0, "[", "]") == len(text) - 1
    inner_open = text.find("[c")
    assert find_matching_bracket(text, inner_open, "[", "]") == len(text) - 2


def test_find_block_span_simple():
    text = "header (content)"
    span = find_block_span(text, "header")
    assert span == (0, len(text))
    
    # Sub-string span check
    assert text[span[0]:span[1]] == "header (content)"


def test_find_block_span_missing_header():
    text = "header (content)"
    assert find_block_span(text, "different_header") is None


def test_find_block_span_missing_open_char():
    text = "header no brackets here"
    assert find_block_span(text, "header") is None


def test_find_block_span_unmatched_brackets():
    text = "header (content without closing"
    assert find_block_span(text, "header") is None


def test_find_block_span_nested():
    text = """
    some leading text
    export Descriptor_Unit_Abrams is TEntityDescriptor
    (
        DescriptorId = GUID:{xyz}
        Modules = [
            TStrategicData(UnitAttack = 10)
        ]
    )
    trailing text
    """
    header = "export Descriptor_Unit_Abrams"
    span = find_block_span(text, header)
    assert span is not None
    start, end = span
    block_content = text[start:end]
    assert block_content.startswith(header)
    assert block_content.endswith(")")
