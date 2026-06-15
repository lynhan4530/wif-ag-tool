from __future__ import annotations
from pathlib import Path
import pytest
from wif_ag_tool.parser.ammo_parser import parse_ammo
from wif_ag_tool.generator.ammo_patcher import patch_ammo_stats

def test_parse_and_patch_ammo(tmp_path):
    content = """
Ammo_AutoCanon_AP_20mm_M621_GIAT_AMX30 is TAmmunitionDescriptor
(
    DescriptorId                      = GUID:{087bb6a9-1efc-4203-b89d-b78667e320bc}
    Name                              = 'QHXGSTXDTE'
    Arme                              = TDamageTypeRTTI(Family=DamageFamily_ap Index=11)
    TimeBetweenTwoShots               = 0.2
    MinimumRangeGRU                   = 50
    MaximumRangeGRU                   = 1500
    PhysicalDamages                   = 1.0
    SuppressDamages                   = 15.0
    TimeBetweenTwoSalvos              = 2.0
    ShotsCountPerSalvo                = 5
    SupplyCost                        = 5.0
)
"""
    f = tmp_path / "Ammunition.ndf"
    f.write_text(content, encoding="utf-8")
    
    parsed = parse_ammo(f)
    assert "Ammo_AutoCanon_AP_20mm_M621_GIAT_AMX30" in parsed
    ammo = parsed["Ammo_AutoCanon_AP_20mm_M621_GIAT_AMX30"]
    assert ammo["guid"] == "087bb6a9-1efc-4203-b89d-b78667e320bc"
    assert ammo["name_token"] == "QHXGSTXDTE"
    assert ammo["damage_family"] == "DamageFamily_ap"
    assert ammo["damage_index"] == 11
    assert ammo["max_range"] == 1500
    assert ammo["time_between_shots"] == 0.2
    
    overrides = {
        "Ammo_AutoCanon_AP_20mm_M621_GIAT_AMX30": {
            "damage_index": 20,
            "max_range": 2000,
            "time_between_shots": 0.1,
            "time_between_salvos": 1.0,
            "shots_per_salvo": 10,
            "supply_cost": 8.0,
            "physical_damages": 2.0,
            "suppress_damages": 30.0,
            "damage_family": "DamageFamily_ap_missile"
        }
    }
    
    patch_ammo_stats(f, overrides)
    
    patched_content = f.read_text(encoding="utf-8")
    import re
    assert re.search(r'Arme\s*=\s*TDamageTypeRTTI\s*\(\s*Family\s*=\s*DamageFamily_ap_missile\s*Index\s*=\s*20\s*\)', patched_content)
    assert re.search(r'MaximumRangeGRU\s*=\s*2000', patched_content)
    assert re.search(r'TimeBetweenTwoShots\s*=\s*0\.1', patched_content)
    assert re.search(r'TimeBetweenTwoSalvos\s*=\s*1\.0', patched_content)
    assert re.search(r'ShotsCountPerSalvo\s*=\s*10', patched_content)
    assert re.search(r'SupplyCost\s*=\s*8\.0', patched_content)
    assert re.search(r'PhysicalDamages\s*=\s*2\.0', patched_content)
    assert re.search(r'SuppressDamages\s*=\s*30\.0', patched_content)


def test_parse_and_patch_extended_ammo(tmp_path):
    content = """
Ammo_AutoCanon_AP_20mm_M621_GIAT_AMX30 is TAmmunitionDescriptor
(
    DescriptorId                      = GUID:{087bb6a9-1efc-4203-b89d-b78667e320bc}
    Name                              = 'QHXGSTXDTE'
    MinimumRangeHelicopterGRU         = 0
    MaximumRangeHelicopterGRU         = 1000
    MinimumRangeAirplaneGRU           = 0
    MaximumRangeAirplaneGRU           = 0
    AimingTime                        = 2.5
    HitRollRuleDescriptor = TDiceHitRollRuleDescriptor
    (
        BaseCriticModifier = 25
        BaseHitValueModifiers =
        [
            (EBaseHitValueModifier/Base, 0),
            (EBaseHitValueModifier/Idling, 20),
            (EBaseHitValueModifier/Moving, 10),
            (EBaseHitValueModifier/Targeted, 0),
        ]
        DistanceToTarget = True
    )
)
"""
    f = tmp_path / "Ammunition.ndf"
    f.write_text(content, encoding="utf-8")
    
    parsed = parse_ammo(f)
    assert "Ammo_AutoCanon_AP_20mm_M621_GIAT_AMX30" in parsed
    ammo = parsed["Ammo_AutoCanon_AP_20mm_M621_GIAT_AMX30"]
    assert ammo["max_range_heli"] == 1000
    assert ammo["min_range_heli"] == 0
    assert ammo["max_range_plane"] == 0
    assert ammo["min_range_plane"] == 0
    assert ammo["aiming_time"] == 2.5
    assert ammo["accuracy_static"] == 20
    assert ammo["accuracy_motion"] == 10
    assert ammo["traits"] == []
    
    overrides = {
        "Ammo_AutoCanon_AP_20mm_M621_GIAT_AMX30": {
            "max_range_heli": 1200,
            "min_range_heli": 100,
            "max_range_plane": 1500,
            "min_range_plane": 200,
            "aiming_time": 1.5,
            "accuracy_static": 35,
            "accuracy_motion": 25,
            "traits": ["MOTION", "HEAT"]
        }
    }
    
    patch_ammo_stats(f, overrides)
    
    patched_content = f.read_text(encoding="utf-8")
    import re
    assert re.search(r'MaximumRangeHelicopterGRU\s*=\s*1200', patched_content)
    assert re.search(r'MinimumRangeHelicopterGRU\s*=\s*100', patched_content)
    assert re.search(r'MaximumRangeAirplaneGRU\s*=\s*1500', patched_content)
    assert re.search(r'MinimumRangeAirplaneGRU\s*=\s*200', patched_content)
    assert re.search(r'AimingTime\s*=\s*1\.5', patched_content)
    assert re.search(r'\(EBaseHitValueModifier/Idling\s*,\s*35\)', patched_content)
    assert re.search(r'\(EBaseHitValueModifier/Moving\s*,\s*25\)', patched_content)
    assert "TraitsToken = [ 'MOTION', 'HEAT', ]" in patched_content


