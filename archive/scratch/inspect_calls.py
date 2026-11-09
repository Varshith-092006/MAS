import sqlite3
import json

conn = sqlite3.connect('mas.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("=== CALL 138 (Developer in 1792332881) ===")
r = c.execute("SELECT raw_metadata FROM model_calls WHERE call_id=138").fetchone()
if r:
    meta = json.loads(r['raw_metadata'])
    print("Metadata keys:", meta.keys())
    print("Usage:", meta.get("usage"))

print("\n=== CALL 139 (Developer in 1792332881) ===")
r = c.execute("SELECT raw_metadata FROM model_calls WHERE call_id=139").fetchone()
if r:
    meta = json.loads(r['raw_metadata'])
    print("Metadata keys:", meta.keys())
    print("Usage:", meta.get("usage"))

print("\n=== CALLS IN 1792329507 Developer ===")
for r in c.execute("SELECT call_id, agent, total_tokens, raw_metadata FROM model_calls WHERE run_id='mas_dev_toc_a_p2m_1792329507' AND agent='developer'").fetchall():
    print(r['call_id'], r['agent'], r['total_tokens'])
