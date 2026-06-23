import sys
from pathlib import Path
import re

sys.path.insert(0, str(Path(r"g:\Project\wif-ag-tool\src")))

from wif_ag_tool.web.app import create_app
from wif_ag_tool.web.api import _state

app = create_app()
with app.app_context():
    # Find all Apache units
    apaches = []
    for name, unit in _state["units"].items():
        if "Apache" in name or "APACHE" in name:
            apaches.append(unit)
            print(f"Unit: {unit.name}")
            print(f"  weapon_descriptor_ref: {unit.weapon_descriptor_ref}")
            
    # Let's inspect the actual content of WeaponDescriptor.ndf for the first Apache
    if apaches:
        weapon_ref = apaches[0].weapon_descriptor_ref
        if weapon_ref:
            if not weapon_ref.startswith("WeaponDescriptor_"):
                weapon_ref = f"WeaponDescriptor_{weapon_ref}"
            
            # Read G:\Project\A-World-In-Flames\Generated\Gameplay\Gfx\WeaponDescriptor.ndf
            wd_path = Path(r"G:\Project\A-World-In-Flames\Generated\Gameplay\Gfx\WeaponDescriptor.ndf")
            if wd_path.exists():
                text = wd_path.read_text(encoding="utf-8")
                # Search for the weapon descriptor export
                pattern = rf"export {re.escape(weapon_ref)}\s+is\s+TWeaponManagerModuleDescriptor"
                m = re.search(pattern, text)
                if m:
                    print(f"Found weapon descriptor in NDF: {weapon_ref}")
                    # Find end of block
                    start = m.start()
                    open_p = text.find("(", start)
                    depth = 0
                    end_idx = None
                    for idx in range(open_p, len(text)):
                        if text[idx] == "(":
                            depth += 1
                        elif text[idx] == ")":
                            depth -= 1
                            if depth == 0:
                                end_idx = idx + 1
                                break
                    if end_idx:
                        block = text[start:end_idx]
                        print("NDF Block:")
                        print(block)
                else:
                    print(f"Could not find weapon descriptor in NDF: {weapon_ref}")
