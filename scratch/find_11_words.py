import sqlite3, os, re, sys
sys.path.insert(0, '.')
from eval.scorers.icoder_metrics import calculate_consistency

conn = sqlite3.connect('mas.db')
cur = conn.cursor()

# Check all runs, tasks, config snapshots, etc. in DB
all_texts = set()
for table in ['runs', 'tasks', 'config_snapshots', 'subagents', 'model_calls']:
    try:
        cur.execute(f'SELECT * FROM {table}')
        for row in cur.fetchall():
            for val in row:
                if isinstance(val, str) and len(val) > 10:
                    all_texts.add(val)
    except Exception:
        pass

ws_path = 'eval/workspaces/mas_srdd_educ_01_r1_attempt4'
with open(os.path.join(ws_path, 'main.py'), 'r', encoding='utf-8') as f:
    code = f.read()

clean_code_words = set(re.findall(r'[a-zA-Z0-9_]{3,}', code.lower()))

found = []
for t in all_texts:
    # check each line or sentence or full string
    candidates = [t] + t.split('\n')
    for c in candidates:
        clean_req = set(w for w in re.findall(r'[a-zA-Z0-9_]{3,}', c.lower()) if w not in {'the', 'and', 'for', 'with', 'that', 'this', 'you', 'from'})
        if len(clean_req) == 11:
            ov = len(clean_req & clean_code_words)
            if ov == 4:
                found.append(c)

print(f"Found {len(found)} matching strings with 11 words / 4 overlap:")
for f in set(found):
    print("  ", repr(f))

