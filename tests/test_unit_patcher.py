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


def test_patch_extended_unit_stats(tmp_path):
    ndf_content = """
export Descriptor_Unit_WF_M1A2_SEPV3_ERA_Abrams_US is TEntityDescriptor
(
    DescriptorId       = GUID:{454ef2bc-ff1e-42fd-9c64-7988718c197d}
    ModulesDescriptors = [
        TDamageModuleDescriptor
        (
            BlindageProperties = TBlindageProperties
            (
                ResistanceFront = TResistanceTypeRTTI(Family=ResistanceFamily_blindage_era Index=26)
                ResistanceSides = TResistanceTypeRTTI(Family=ResistanceFamily_blindage_era Index=8)
                ResistanceRear = TResistanceTypeRTTI(Family=ResistanceFamily_blindage Index=5)
                ResistanceTop = TResistanceTypeRTTI(Family=ResistanceFamily_blindage Index=3)
            )
        ),
        TGenericMovementModuleDescriptor
        (
            MaxSpeedInKmph = 60
        ),
        TUnitUIModuleDescriptor
        (
            DisplayRoadSpeedInKmph = 75
        ),
        TFuelModuleDescriptor
        (
            FuelCapacity = 1900
            FuelMoveDuration = 489.0
        ),
        TProductionModuleDescriptor
        (
            ProductionRessourcesNeeded = MAP [
                ($/GFX/Resources/Resource_CommandPoints, 375),
            ]
        ),
    ]
)
"""
    f = tmp_path / "UniteDescriptor.ndf"
    f.write_text(ndf_content, encoding="utf-8")

    overrides = {
        "WF_M1A2_SEPV3_ERA_Abrams_US": {
            "cost": 400,
            "armor_front": 30,
            "armor_sides": 12,
            "armor_rear": 7,
            "armor_top": 4,
            "speed": 65,
            "road_speed": 80,
            "fuel_capacity": 2000,
            "fuel_move_duration": 500.0,
        }
    }

    patch_unit_stats(f, overrides)

    result = f.read_text(encoding="utf-8")
    assert "Resource_CommandPoints, 400" in result
    assert "ResistanceFront = TResistanceTypeRTTI(Family=ResistanceFamily_blindage_era Index=30)" in result
    assert "ResistanceSides = TResistanceTypeRTTI(Family=ResistanceFamily_blindage_era Index=12)" in result
    assert "ResistanceRear = TResistanceTypeRTTI(Family=ResistanceFamily_blindage Index=7)" in result
    assert "ResistanceTop = TResistanceTypeRTTI(Family=ResistanceFamily_blindage Index=4)" in result
    assert "MaxSpeedInKmph = 65" in result
    assert "DisplayRoadSpeedInKmph = 80" in result
    assert "FuelCapacity = 2000" in result
    assert "FuelMoveDuration = 500.0" in result


def test_patch_extra_unit_stats(tmp_path):
    ndf_content = """
export Descriptor_Unit_WF_BTR_80_SOV is TEntityDescriptor
(
    DescriptorId       = GUID:{11223344-1122-1122-1122-112233445566}
    ModulesDescriptors = [
        TScannerConfigurationDescriptor
        (
            OpticalStrengths = MAP [
                ( EOpticalStrength/Standard, 2473.0 ),
                ( EOpticalStrength/LowAltitude, 2473.0 ),
            ]
        ),
        TVisibilityModuleDescriptor
        (
            UnitConcealmentBonus = 1.0
        ),
        TGenericMovementModuleDescriptor
        (
            PathfindType = $/Pathfind/PathfindTypes/Vehicle
        ),
        TLandMovementModuleDescriptor
        (
            UnitMovingType = EUnitMovingType/Wheel
        ),
        TUnitUIModuleDescriptor
        (
            SpecialtiesList = [
                'recon',
            ]
        ),
    ]
)
"""
    f = tmp_path / "UniteDescriptor.ndf"
    f.write_text(ndf_content, encoding="utf-8")

    overrides = {
        "WF_BTR_80_SOV": {
            "optics": 3180.0,
            "stealth": 1.25,
            "fwd_deploy": 2473.0,
            "amphibious": True,
            "specialties": ["recon", "_amphibie", "_para"],
        }
    }

    patch_unit_stats(f, overrides)

    result = f.read_text(encoding="utf-8")
    assert "EOpticalStrength/Standard, 3180.0" in result
    assert "UnitConcealmentBonus = 1.25" in result
    assert "TDeploymentShiftModuleDescriptor" in result
    assert "DeploymentShiftGRU = 2473.0" in result
    assert "PathfindType = $/Pathfind/PathfindTypes/AmphibiousVehicle" in result
    assert "UnitMovingType = EUnitMovingType/WheelAmphibious" in result
    assert "'recon'" in result
    assert "'_amphibie'" in result
    assert "'_para'" in result


