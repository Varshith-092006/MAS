import sqlite3, json, os

conn = sqlite3.connect('mas.db')
cur = conn.cursor()

print("--- Latest Runs ---")
cur.execute('SELECT run_id, system, task_id, status, started_at, total_tokens FROM runs ORDER BY rowid DESC LIMIT 5')
for r in cur.fetchall():
    print(r)

print("\n--- Latest Model Calls ---")
cur.execute('SELECT call_id, run_id, model, input_tokens, output_tokens, total_tokens, created_at FROM model_calls ORDER BY rowid DESC LIMIT 5')
for r in cur.fetchall():
    print(r)

conn.close()

print("\n--- Workspaces with r2 ---")
ws_dir = "eval/workspaces"
if os.path.exists(ws_dir):
    for d in sorted(os.listdir(ws_dir)):
        if "_r2" in d:
            print(d)

