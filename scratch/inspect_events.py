import sqlite3

conn = sqlite3.connect('mas.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("=== RECENT RUNS IN runs ===")
for r in c.execute("SELECT run_id, task_id, status, started_at, finished_at, failure_reason FROM runs WHERE run_id LIKE 'mas_dev_toc%' ORDER BY rowid DESC LIMIT 10").fetchall():
    print(dict(r))

print("\n=== EVENTS FOR mas_dev_toc_a_p2m_1792332881 ===")
for r in c.execute("SELECT seq, run_id, agent, event, status, redacted_summary, created_at FROM agent_events WHERE run_id='mas_dev_toc_a_p2m_1792332881' ORDER BY seq ASC").fetchall():
    print(dict(r))

print("\n=== EVENTS FOR mas_dev_toc_a_p2m_1792331989 ===")
for r in c.execute("SELECT seq, run_id, agent, event, status, redacted_summary, created_at FROM agent_events WHERE run_id='mas_dev_toc_a_p2m_1792331989' ORDER BY seq ASC").fetchall():
    print(dict(r))

print("\n=== EVENTS FOR mas_dev_toc_a_p2m_1792331622 ===")
for r in c.execute("SELECT seq, run_id, agent, event, status, redacted_summary, created_at FROM agent_events WHERE run_id='mas_dev_toc_a_p2m_1792331622' ORDER BY seq ASC").fetchall():
    print(dict(r))

print("\n=== EVENTS FOR mas_dev_toc_a_p2m_1792330468 ===")
for r in c.execute("SELECT seq, run_id, agent, event, status, redacted_summary, created_at FROM agent_events WHERE run_id='mas_dev_toc_a_p2m_1792330468' ORDER BY seq ASC").fetchall():
    print(dict(r))
