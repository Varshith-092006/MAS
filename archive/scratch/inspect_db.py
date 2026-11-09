import sqlite3

conn = sqlite3.connect("mas.db")
cursor = conn.cursor()
tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
for t in tables:
    name = t[0]
    cols = cursor.execute(f"PRAGMA table_info({name})").fetchall()
    print(f"Table: {name}")
    for col in cols:
        print(f"  {col[1]} ({col[2]})")
    rows = cursor.execute(f"SELECT * FROM {name} LIMIT 5").fetchall()
    print(f"  Count: {len(cursor.execute(f'SELECT * FROM {name}').fetchall())}")
    for r in rows:
        print(f"  Row: {r}")
