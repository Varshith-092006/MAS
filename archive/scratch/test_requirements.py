import os, sys, re
sys.path.insert(0, '.')
from eval.scorers.icoder_metrics import calculate_consistency

ws_path = 'eval/workspaces/mas_srdd_educ_01_r1_attempt4'
with open(os.path.join(ws_path, 'main.py'), 'r', encoding='utf-8') as f:
    code = f.read()

# Let's test various requirement strings from across the project
strings_to_test = [
    # 1. Short task description
    "Step-by-step science question solver providing explanations and solutions.",
    # 2. Detailed requirement in task dict or tests
    "Science Question Solver",
    "A science question solver that takes questions in physics, chemistry, and biology and provides step-by-step solutions.",
    "A step-by-step science question solver application that provides explanations and solutions for scientific questions.",
    "Develop a step-by-step science question solver capable of providing explanations and solutions.",
]

# Also check eval/checks/level2_checks.json or dev_level2_checks.json
import json
if os.path.exists('eval/checks/level2_checks.json'):
    with open('eval/checks/level2_checks.json') as f:
        cdata = json.load(f)
        for check in cdata.get('srdd_educ_01', []):
            if 'description' in check:
                strings_to_test.append(check['description'])

if os.path.exists('eval/tasks.json'):
    with open('eval/tasks.json') as f:
        tdata = json.load(f)
        for t in tdata:
            if t.get('task_id') == 'srdd_educ_01':
                strings_to_test.append(t.get('description', ''))
                strings_to_test.append(t.get('prompt', ''))
                strings_to_test.append(t.get('requirement', ''))

for s in set(strings_to_test):
    if not s: continue
    # Force lexical recall by testing lexical
    clean_req_words = set(w for w in re.findall(r'[a-zA-Z0-9_]{3,}', s.lower()) if w not in {'the', 'and', 'for', 'with', 'that', 'this', 'you', 'from'})
    clean_code_words = set(w for w in re.findall(r'[a-zA-Z0-9_]{3,}', code.lower()))
    if clean_req_words:
        recall = len(clean_req_words & clean_code_words) / len(clean_req_words)
        res = round(float(recall), 4)
        if res in (0.7143, 0.3636, 0.8571):
            print(f"MATCH! score={res} | req len={len(clean_req_words)} overlap={len(clean_req_words & clean_code_words)}")
            print(f"  String: {repr(s)}")

