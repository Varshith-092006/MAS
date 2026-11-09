import sqlite3
import json
import os
import glob

def main():
    conn = sqlite3.connect('mas.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print('Tables in mas.db:', tables)

    print('\n=== RECENT RUNS in runs table ===')
    for row in c.execute("SELECT * FROM runs ORDER BY rowid DESC LIMIT 10").fetchall():
        print(dict(row))

    print('\n=== RECENT MODEL CALLS ===')
    try:
        for row in c.execute("SELECT * FROM model_calls ORDER BY rowid DESC LIMIT 15").fetchall():
            print(dict(row))
    except Exception as e:
        print('Error querying model_calls:', e)

    print('\n=== CHECKPOINTS / AGENT EVENTS / ARTIFACTS ===')
    for tbl in ['checkpoints', 'agent_events', 'artifacts']:
        if tbl in tables:
            print(f'--- Table: {tbl} ---')
            rows = c.execute(f"SELECT * FROM {tbl} ORDER BY rowid DESC LIMIT 5").fetchall()
            for r in rows:
                print(dict(r))

    print('\n=== WORKSPACE FILES IN LATEST RUNS ===')
    p2m_dirs = sorted(glob.glob('workspace/mas_dev_toc_a_p2m_*'))
    for d in p2m_dirs:
        print(f"\nDirectory: {d}")
        for root, dirs, files in os.walk(d):
            for f in files:
                fpath = os.path.join(root, f)
                size = os.path.getsize(fpath)
                print(f"  {fpath} ({size} bytes)")

if __name__ == '__main__':
    main()
