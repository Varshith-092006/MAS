import sqlite3
import json

conn = sqlite3.connect('mas.db')
c = conn.cursor()

for aid in [47, 50, 53]:
    row = c.execute('SELECT artifact_id, type, version, json_data FROM artifacts WHERE artifact_id = ?', (aid,)).fetchone()
    data = json.loads(row[3])
    print(f"\n==========================================")
    print(f"CODEPATCH ARTIFACT {aid} (VERSION {row[2]})")
    print(f"==========================================")
    fc = data.get("file_contents", {})
    for fn, content in fc.items():
        print(f"--- File: {fn} (len={len(content)}) ---")
        lines = content.splitlines()
        print("FIRST 10 LINES:")
        for l in lines[:10]:
            print("  ", l)
        print("LAST 10 LINES:")
        for l in lines[-10:]:
            print("  ", l)
