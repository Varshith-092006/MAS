import sqlite3
import json

conn = sqlite3.connect('mas.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("=== ALL RUNS (recent 10) ===")
for r in c.execute("SELECT run_id, task_id, status, started_at, finished_at, failure_reason FROM runs ORDER BY rowid DESC LIMIT 10").fetchall():
    print(dict(r))

print("\n=== MODEL CALLS FOR P2M RUNS ===")
for r in c.execute("SELECT call_id, run_id, agent, model, actual_model, input_tokens, output_tokens, total_tokens, cost, request_id FROM model_calls WHERE run_id LIKE 'mas_dev_toc_a_p2m%' ORDER BY rowid ASC").fetchall():
    print(dict(r))

print("\n=== AGENT EVENTS FOR LAST RUN mas_dev_toc_a_p2m_1792332881 ===")
for r in c.execute("SELECT seq, run_id, agent, event, status, redacted_summary, created_at FROM agent_events WHERE run_id='mas_dev_toc_a_p2m_1792332881' ORDER BY seq ASC").fetchall():
    print(dict(r))

print("\n=== AGENT EVENTS FOR RUN mas_dev_toc_a_p2m_1792331989 ===")
for r in c.execute("SELECT seq, run_id, agent, event, status, redacted_summary, created_at FROM agent_events WHERE run_id='mas_dev_toc_a_p2m_1792331989' ORDER BY seq ASC").fetchall():
    print(dict(r))

print("\n=== AGENT EVENTS FOR RUN mas_dev_toc_a_p2m_1792329507 ===")
for r in c.execute("SELECT seq, run_id, agent, event, status, redacted_summary, created_at FROM agent_events WHERE run_id='mas_dev_toc_a_p2m_1792329507' ORDER BY seq ASC").fetchall():
    print(dict(r))

print("\n=== CHECKPOINTS FOR ALL P2M RUNS ===")
for r in c.execute("SELECT * FROM checkpoints WHERE run_id LIKE 'mas_dev_toc_a_p2m%' ORDER BY checkpoint_id ASC").fetchall():
    print(dict(r))
