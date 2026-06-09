from __future__ import annotations
from pathlib import Path
import pytest
from wif_ag_tool.generator.unit_patcher import patch_unit_stats, _set_field_in_module

def test_set_field_in_module():
    block = """
        TStrategicDataModuleDescriptor
        (
            UnitAttackValue          = 652
            UnitDefenseValue         = 497
            UnitBonusXpPerLevelValue = 1
        )
    """
    # Test setting existing field preserves spacing
    modified = _set_field_in_module(block, "UnitAttackValue", 999)
    assert "UnitAttackValue          = 999" in modified
    assert "UnitDefenseValue         = 497" in modified

    # Test setting missing field appends it before closing paren
    missing_block = """
        TStrategicDataModuleDescriptor
        (
            UnitBonusXpPerLevelValue = 1
        )
    """
    modified_missing = _set_field_in_module(missing_block, "UnitAttackValue", 123)
    assert "UnitAttackValue = 123" in modified_missing
    assert "UnitBonusXpPerLevelValue = 1" in modified_missing

def test_patch_unit_stats(tmp_path):
    ndf_content = """
export Descriptor_Unit_WF_M1A2_SEPV2_Abrams_US is TEntityDescriptor
(
    DescriptorId       = GUID:{454ef2bc-ff1e-42fd-9c64-7988718c197d}
    ModulesDescriptors = [
        TStrategicDataModuleDescriptor
        (
            UnitAttackValue          = 652
            UnitDefenseValue         = 497
            UnitBonusXpPerLevelValue = 1
        ),
    ]
)

export Descriptor_Unit_WF_T90M_RUS is TEntityDescriptor
(
    DescriptorId       = GUID:{12345678-1234-1234-1234-123456789012}
    ModulesDescriptors = [
        TStrategicDataModuleDescriptor
        (
            UnitAttackValue          = 580
            UnitDefenseValue         = 440
        ),
    ]
)
"""
    f = tmp_path / "UniteDescriptor.ndf"
    f.write_text(ndf_content, encoding="utf-8")

    overrides = {
        "WF_M1A2_SEPV2_Abrams_US": (999, 888),
        "WF_T90M_RUS": (None, 555), # only override defense
    }

    patch_unit_stats(f, overrides)

    result = f.read_text(encoding="utf-8")
    assert "UnitAttackValue          = 999" in result
    assert "UnitDefenseValue         = 888" in result
    assert "UnitAttackValue          = 580" in result  # unchanged
    assert "UnitDefenseValue         = 555" in result  # changed
