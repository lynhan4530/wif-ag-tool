import re

_RE_WEAPON_OLD = re.compile(r'\$/GFX/Weapon/WeaponDescriptor_(\S+)')
_RE_WEAPON_NEW = re.compile(r'\$/GFX/Weapon/WeaponDescriptor_([\w_]+)')

line = "        $/GFX/Weapon/WeaponDescriptor_WF_Sprut_RUS,"

m_old = _RE_WEAPON_OLD.search(line)
m_new = _RE_WEAPON_NEW.search(line)

print("Old regex group(1):", repr(m_old.group(1)) if m_old else None)
print("New regex group(1):", repr(m_new.group(1)) if m_new else None)
