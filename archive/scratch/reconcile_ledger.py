import json

ledger_file = "eval/outbound_transmission_ledger.json"
with open(ledger_file, "r", encoding="utf-8") as f:
    data = json.load(f)

# Reconcile 2026-10-18 header
d18 = data["2026-10-18"]
events = d18["events"]

gen_success = sum(1 for ev in events if ev.get("type") in ("LIVE_GENERATION", "GENERATION") and ev.get("status") == 200)
meta_queries = sum(1 for ev in events if ev.get("type") in ("KEY_METADATA", "METADATA"))
active_res = sum(1 for ev in events if ev.get("state") == "RESERVED")
total_trans = len(events)

print(f"Events breakdown: gen_success={gen_success}, meta_queries={meta_queries}, active_res={active_res}, total={total_trans}")

d18["generation_calls_successful"] = gen_success
d18["metadata_queries"] = meta_queries
d18["total_outbound_http_transmissions"] = total_trans

with open(ledger_file, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print("Updated ledger successfully.")

from mas.core.governor import global_governor
stats = global_governor.get_ledger_stats()
print("Reconciled global governor stats:")
print(json.dumps(stats, indent=2))
