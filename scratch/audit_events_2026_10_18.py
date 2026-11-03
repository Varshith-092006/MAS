import json

with open("eval/outbound_transmission_ledger.json", "r", encoding="utf-8") as f:
    ledger = json.load(f)

day = ledger.get("2026-10-18", {})
print("=== DAY SUMMARY METRICS ===")
for k, v in day.items():
    if k != "events":
        print(f"  {k}: {v}")

events = day.get("events", [])
print(f"\nTotal events list length: {len(events)}")

print("\n=== LIST OF ALL EVENTS ===")
for i, ev in enumerate(events, 1):
    att_id = ev.get("attempt_id")
    ev_type = ev.get("type")
    state = ev.get("state")
    status = ev.get("status")
    source = ev.get("source")
    t = ev.get("time_utc")
    target = ev.get("target")
    print(f"{i:2d}. [{t}] type={ev_type:<15} state={state:<10} status={str(status):<5} target={target:<30} source={source}")
