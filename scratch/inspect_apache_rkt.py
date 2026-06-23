from pathlib import Path
import re

wd_path = Path(r"G:\Project\A-World-In-Flames\Generated\Gameplay\Gfx\WeaponDescriptor.ndf")
text = wd_path.read_text(encoding="utf-8")

pattern = r"export WeaponDescriptor_WF_AH64_Apache_RKT_US\s+is\s+TWeaponManagerModuleDescriptor"
m = re.search(pattern, text)
if m:
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
        print("NDF Block for WF_AH64_Apache_RKT_US:")
        print(block)
else:
    print("Could not find WF_AH64_Apache_RKT_US weapon descriptor")
