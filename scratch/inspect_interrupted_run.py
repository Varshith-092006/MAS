import sqlite3
import json

conn = sqlite3.connect('mas.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("--- RUN RECORD ---")
for r in c.execute("SELECT * FROM runs WHERE run_id='mas_dev_toc_a_p2m_1792332881'").fetchall():
    print(dict(r))

print("\n--- AGENT EVENTS ---")
for r in c.execute("SELECT * FROM agent_events WHERE run_id='mas_dev_toc_a_p2m_1792332881' ORDER BY seq ASC").fetchall():
    print(dict(r))

print("\n--- MODEL CALLS ---")
for r in c.execute("SELECT * FROM model_calls WHERE run_id='mas_dev_toc_a_p2m_1792332881' ORDER BY rowid ASC").fetchall():
    print(dict(r))

print("\n--- CHECKPOINTS ---")
for r in c.execute("SELECT * FROM checkpoints WHERE run_id='mas_dev_toc_a_p2m_1792332881'").fetchall():
    print(dict(r))

print("\n--- ARTIFACTS ---")
for r in c.execute("SELECT * FROM artifacts WHERE run_id='mas_dev_toc_a_p2m_1792332881'").fetchall():
    print(dict(r))
