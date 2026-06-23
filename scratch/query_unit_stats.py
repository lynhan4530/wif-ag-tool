import json
from pathlib import Path

cache_path = Path(r"g:\Project\wif-ag-tool\data\wif_units_cache.json")
data = json.loads(cache_path.read_text(encoding="utf-8"))

print("Soviet transport units in WIF cache:")
for name, u in data.items():
    if u.get("is_transport") and u.get("nation") == "SOV":
        print(f"  Name: {name}")
        print(f"    Display: {u.get('display_name')}")
