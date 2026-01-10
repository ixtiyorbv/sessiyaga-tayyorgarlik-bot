import json
import sys
from collections import defaultdict

FILE_NAME = "test.json"

try:
    with open(FILE_NAME, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception as e:
    print(f"❌ test.json o‘qilmadi: {e}")
    sys.exit(1)

if not isinstance(data, list):
    print("❌ test.json ichida asosiy struktura list ([ ]) bo‘lishi kerak")
    sys.exit(1)

errors = []
fan_registry = defaultdict(set)

# dublikatlarni saqlash uchun
savol_map = defaultdict(list)

for q in data:
    savol = q.get("savol")
    fan = q.get("fan", "NOMA’LUM FAN")

    if isinstance(savol, str) and savol.strip():
        savol_map[savol.strip()].append(fan)

# DUBLIKATLARNI ANIQLASH
for savol_text, fans in savol_map.items():
    if len(fans) > 1:
        errors.append(
            f"🔁 DUBLIKAT SAVOL TOPILDI:\n"
            f"   Savol: \"{savol_text}\"\n"
            f"   Fanlar: {', '.join(fans)}\n"
            f"   Takrorlar soni: {len(fans)} ta"
        )

# Fan nomi registr tekshiruvi
for fan_lower, variants in fan_registry.items():
    if len(variants) > 1:
        errors.append(
            f"Fan nomi registr muammosi: {', '.join(variants)}"
        )

# NATIJA
if errors:
    print("\n⚠️ DUBLIKATLAR TOPILDI:\n")
    for e in errors:
        print(e)
        print("-" * 60)
    sys.exit(1)
else:
    print("✅ DUBLIKAT SAVOLLAR YO‘Q")
