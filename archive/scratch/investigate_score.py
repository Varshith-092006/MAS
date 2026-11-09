import os, sys, glob, json, re

ws_file = 'eval/workspaces/mas_srdd_educ_01_r1_attempt4/main.py'
with open(ws_file, 'r', encoding='utf-8') as f:
    code = f.read().lower()
clean_code_words = set(re.findall(r'[a-zA-Z0-9_]{3,}', code))

print("Total code words:", len(clean_code_words))

# Check transcripts or files that contain 0.3636
for root, _, files in os.walk('.'):
    if any(skip in root for skip in ['.git', 'venv', '__pycache__', '.pytest_cache']):
        continue
    for file in files:
        if file.endswith(('.py', '.json', '.md', '.csv', '.txt')):
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if '0.3636' in content:
                        print(f"Found '0.3636' in: {path}")
            except Exception:
                pass

