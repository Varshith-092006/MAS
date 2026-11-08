import json

with open('eval/benchmark_manifest.json') as f:
    m = json.load(f)

print("Summary:", json.dumps(m.get('summary', {}), indent=2))
print("\n--- Runs for srdd_educ_01 ---")
for r in m.get('runs', []):
    if r.get('task_id') == 'srdd_educ_01':
        rid = r.get('run_id')
        sys_name = r.get('system')
        rep = r.get('repeat_no')
        status = r.get('status')
        mode = r.get('execution_mode')
        tok = r.get('tokens')
        paired = r.get('is_paired_complete')
        counter = r.get('paired_counterpart_run_id')
        print(f"{rid:<30} | {sys_name:<8} | r{rep} | {status:<24} | {mode:<10} | tok={tok} | paired={paired} | counter={counter}")

