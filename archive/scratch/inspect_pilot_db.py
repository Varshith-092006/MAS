import sqlite3
import json

conn = sqlite3.connect('mas.db')
c = conn.cursor()

print('=== ALL RUNS IN MAS.DB ===')
for row in c.execute('SELECT run_id, task_id, system, model, status, started_at, total_tokens, estimated_cost FROM runs'):
    print(row)

pilot_id = "mas_dev_csv_sales_1792211689"

print(f'\n=== ARTIFACTS FOR {pilot_id} ===')
for row in c.execute('SELECT artifact_id, type, version, schema_valid, json_data FROM artifacts WHERE run_id = ? ORDER BY artifact_id', (pilot_id,)):
    aid, atype, aver, avalid, adata_raw = row
    adata = json.loads(adata_raw) if adata_raw else {}
    print(f"Artifact {aid}: type={atype}, ver={aver}, valid={avalid}")
    if atype == "review_report":
        print(f"  ReviewReport ver {aver}: status={adata.get('status')}, summary={adata.get('summary')}")
        for finding in adata.get("findings", []):
            print(f"    - Severity: {finding.get('severity')}")
            print(f"      Category: {finding.get('category')}")
            print(f"      File/Line: {finding.get('file_path')}:{finding.get('line_number')}")
            print(f"      Desc: {finding.get('description')}")
            print(f"      Suggestion: {finding.get('suggestion')}")
    elif atype == "reflection_decision":
        print(f"  ReflectionDecision ver {aver}: action={adata.get('action')}, score={adata.get('score')}, delta={adata.get('score_delta')}, rationale={adata.get('rationale')}")
    elif atype == "test_report":
        print(f"  TestReport ver {aver}: passed={adata.get('passed')}, total={adata.get('total_tests')}, failed={adata.get('failed_tests')}, summary={adata.get('summary')}")

print(f'\n=== MODEL CALLS FOR {pilot_id} ===')
total_in = 0
total_out = 0
total_tot = 0
for row in c.execute('SELECT call_id, agent, requested_model, actual_model, input_tokens, output_tokens, total_tokens, cost, request_id, raw_metadata FROM model_calls WHERE run_id = ? ORDER BY call_id', (pilot_id,)):
    cid, agent, req_m, act_m, in_tok, out_tok, tot_tok, cost, req_id, raw_meta = row
    total_in += (in_tok or 0)
    total_out += (out_tok or 0)
    total_tot += (tot_tok or 0)
    print(f"Call {cid}: Agent={agent}, In={in_tok}, Out={out_tok}, Tot={tot_tok}, Cost={cost}, ReqId={req_id}")
    meta = json.loads(raw_meta) if raw_meta else {}
    print(f"    raw_metadata: {meta}")

print(f"SUM OF COLUMNS: input={total_in}, output={total_out}, total={total_tot}")

print(f'\n=== METRICS FOR {pilot_id} ===')
for row in c.execute('SELECT metric_name, metric_value, scope FROM metrics WHERE run_id = ?', (pilot_id,)):
    print(row)
