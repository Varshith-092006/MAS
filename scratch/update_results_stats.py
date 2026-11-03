import json
from mas.core.governor import global_governor

res_file = "eval/phase2m_pilot_results.json"
with open(res_file, "r", encoding="utf-8") as f:
    data = json.load(f)

data["ledger_audit"] = global_governor.get_ledger_stats()

with open(res_file, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print("Updated phase2m_pilot_results.json with reconciled ledger stats.")
