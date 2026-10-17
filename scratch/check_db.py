import sqlite3

conn = sqlite3.connect("mas.db")
c = conn.cursor()
c.execute("SELECT run_id, count(call_id) FROM model_calls WHERE run_id LIKE 'mas_dev_csv_sales%' GROUP BY run_id")
print("Phase 2E runs and call counts:")
for r in c.fetchall():
    print(r)

c.execute("SELECT count(call_id) FROM model_calls WHERE run_id LIKE 'mas_dev_csv_sales%'")
print("Total calls across Phase 2E runs:", c.fetchone()[0])
