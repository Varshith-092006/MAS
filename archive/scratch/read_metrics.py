import sqlite3

conn = sqlite3.connect('mas.db')
cur = conn.cursor()
cur.execute('PRAGMA table_info(metrics)')
cols = [r[1] for r in cur.fetchall()]
print("Cols:", cols)
cur.execute('SELECT rowid, ' + ', '.join(cols) + ' FROM metrics WHERE run_id = ? AND scope = "neutral"', ('mas_srdd_educ_01_r1_attempt4',))
for r in cur.fetchall():
    print(r)
conn.close()

