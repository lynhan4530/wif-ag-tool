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
