import sqlite3
import json

conn = sqlite3.connect('mas.db')
c = conn.cursor()

row = c.execute('SELECT json_data FROM artifacts WHERE artifact_id = 50').fetchone()
data = json.loads(row[0])
content = data.get("file_contents", {}).get("main.py", "")

print("=== Artifact 50 main.py (Iteration 2) ===")
for idx, line in enumerate(content.splitlines(), 1):
    print(f"{idx:3}: {line}")
