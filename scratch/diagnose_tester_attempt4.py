import sqlite3, json

conn = sqlite3.connect('mas.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

run_id = 'mas_srdd_educ_01_r2_attempt4'

cur.execute('SELECT * FROM model_calls WHERE run_id = ? AND agent = "tester"', (run_id,))
calls = [dict(r) for r in cur.fetchall()]
print(f"Total Tester calls: {len(calls)}")
for i, c in enumerate(calls):
    print(f"\n--- Tester Call {i+1} (call_id: {c['call_id']}) ---")
    print(f"Tokens: in={c['input_tokens']} out={c['output_tokens']} tot={c['total_tokens']}")
    print(f"Request ID: {c['request_id']}")
    print(f"Metadata: {c['raw_metadata']}")

print("\n--- Agent Events for Tester ---")
cur.execute('SELECT * FROM agent_events WHERE run_id = ? AND agent = "tester" ORDER BY seq', (run_id,))
events = [dict(r) for r in cur.fetchall()]
for e in events:
    print(f"Seq {e['seq']}: event={e['event']} status={e['status']} summary={e['redacted_summary']}")

conn.close()

