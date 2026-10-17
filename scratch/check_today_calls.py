import sqlite3

conn = sqlite3.connect("mas.db")
c = conn.cursor()
c.execute("""
    SELECT count(mc.call_id)
    FROM model_calls mc
    JOIN runs r ON mc.run_id = r.run_id
    WHERE r.started_at >= '2026-10-17 00:00:00'
""")
today_calls = c.fetchone()[0]
print(f"Total model calls on 2026-10-17 UTC: {today_calls}")
print(f"Daily cap: 45. Remaining transmissions allowed today: {45 - today_calls}")
