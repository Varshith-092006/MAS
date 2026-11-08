import sqlite3, json

conn = sqlite3.connect('mas.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

run_id = 'mas_srdd_educ_01_r2_attempt3'

print("=== RUN INFO ===")
cur.execute('SELECT * FROM runs WHERE run_id = ?', (run_id,))
run_row = cur.fetchone()
if run_row:
    for k in run_row.keys():
        print(f"  {k}: {run_row[k]}")

print("\n=== MODEL CALLS ===")
cur.execute('SELECT * FROM model_calls WHERE run_id = ?', (run_id,))
calls = [dict(r) for r in cur.fetchall()]
print(f"Total model calls: {len(calls)}")
for i, c in enumerate(calls):
    print(f"\n--- Call {i+1} ---")
    for k in ['call_id', 'agent', 'model', 'input_tokens', 'output_tokens', 'total_tokens', 'request_id']:
        print(f"  {k}: {c.get(k)}")
    raw_meta = c.get('raw_metadata')
    if raw_meta:
        try:
            meta = json.loads(raw_meta)
            print("  raw_metadata keys:", list(meta.keys()))
            if 'response' in meta:
                print("  response preview:", str(meta['response'])[:500])
        except Exception:
            print("  raw_meta length:", len(raw_meta))

print("\n=== AGENT EVENTS ===")
cur.execute('SELECT * FROM agent_events WHERE run_id = ? ORDER BY event_id', (run_id,))
events = [dict(r) for r in cur.fetchall()]
print(f"Total agent events: {len(events)}")
for e in events:
    print(f"\nEvent {e.get('event_id')}: type={e.get('event_type')} agent={e.get('agent_name')} phase={e.get('phase')}")
    payload = e.get('payload')
    if payload:
        print("  payload:", payload[:500])

conn.close()

