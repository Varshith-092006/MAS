import sqlite3

conn = sqlite3.connect('mas.db')
c = conn.cursor()
pilot_id = "mas_dev_csv_sales_1792211689"

print("Agent events for pilot:")
for r in c.execute('SELECT seq, agent, event, status, redacted_summary FROM agent_events WHERE run_id = ? ORDER BY seq', (pilot_id,)):
    print(f"[{r[0]}] {r[1]} -> {r[2]} ({r[3]}): {r[4]}")
