import sqlite3
import json

conn = sqlite3.connect('mas.db')
conn.row_factory = sqlite3.Row
r = conn.cursor().execute("SELECT * FROM runs WHERE run_id='mas_dev_toc_a_p2m_1792332881'").fetchone()
if r:
    for k, v in dict(r).items():
        print(f"{k}: {v}")
else:
    print("Run not found!")
