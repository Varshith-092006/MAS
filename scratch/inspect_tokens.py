import sqlite3
import json

conn = sqlite3.connect('mas.db')
c = conn.cursor()

pilot_id = "mas_dev_csv_sales_1792211689"

print("Call Details for Pilot Run:")
rows = c.execute('''
    SELECT call_id, agent, requested_model, actual_model, input_tokens, output_tokens, total_tokens, cost, request_id, raw_metadata
    FROM model_calls WHERE run_id = ? ORDER BY call_id
''', (pilot_id,)).fetchall()

print(f"{'Call':<5} | {'Agent':<10} | {'Input':<6} | {'Out(DB)':<7} | {'Tot(DB)':<7} | {'Prompt(raw)':<11} | {'Comp(raw)':<9} | {'Tot(raw)':<8} | {'Reasoning(raw)':<14}")
print("-" * 90)

sum_in = 0
sum_out = 0
sum_tot = 0
sum_raw_prompt = 0
sum_raw_comp = 0
sum_raw_tot = 0
sum_raw_reas = 0

for r in rows:
    cid, agent, req_m, act_m, in_tok, out_tok, tot_tok, cost, req_id, raw_meta = r
    meta = json.loads(raw_meta) if raw_meta else {}
    usage = meta.get("usage", {})
    raw_prompt = usage.get("prompt_tokens", 0)
    raw_comp = usage.get("completion_tokens", 0)
    raw_tot = usage.get("total_tokens", 0)
    comp_details = usage.get("completion_tokens_details", {}) or {}
    raw_reas = comp_details.get("reasoning_tokens", 0)
    
    sum_in += in_tok or 0
    sum_out += out_tok or 0
    sum_tot += tot_tok or 0
    sum_raw_prompt += raw_prompt
    sum_raw_comp += raw_comp
    sum_raw_tot += raw_tot
    sum_raw_reas += raw_reas
    
    print(f"{cid:<5} | {agent:<10} | {in_tok:<6} | {out_tok:<7} | {tot_tok:<7} | {raw_prompt:<11} | {raw_comp:<9} | {raw_tot:<8} | {raw_reas:<14}")

print("-" * 90)
print(f"{'SUM':<5} | {'ALL':<10} | {sum_in:<6} | {sum_out:<7} | {sum_tot:<7} | {sum_raw_prompt:<11} | {sum_raw_comp:<9} | {sum_raw_tot:<8} | {sum_raw_reas:<14}")
