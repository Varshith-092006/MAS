import sqlite3
import json

conn = sqlite3.connect('mas.db')
c = conn.cursor()

pilot_id = "mas_dev_csv_sales_1792211689"

rows = c.execute('''
    SELECT call_id, agent, requested_model, actual_model, input_tokens, output_tokens, total_tokens, cost, request_id, raw_metadata
    FROM model_calls WHERE run_id = ? ORDER BY call_id
''', (pilot_id,)).fetchall()

print("=" * 115)
print(f"{'Idx':<3} | {'Call':<4} | {'Agent':<9} | {'Prompt':<6} | {'Comp(raw)':<9} | {'Reas(raw)':<9} | {'Tot(raw)':<8} | {'Comp-Reas':<9} | {'Req max_tok'}")
print("=" * 115)

max_tok_map = {
    "manager": 3000,
    "developer": 6000,
    "tester": 3000,
    "reviewer": 5000,
}

sum_prompt = 0
sum_comp = 0
sum_reas = 0
sum_tot = 0
sum_visible_naive = 0
sum_visible_clamped = 0

for idx, r in enumerate(rows, 1):
    cid, agent, req_m, act_m, in_tok, out_tok, tot_tok, cost, req_id, raw_meta = r
    meta = json.loads(raw_meta) if raw_meta else {}
    usage = meta.get("usage", {})
    prompt = usage.get("prompt_tokens", 0)
    comp = usage.get("completion_tokens", 0)
    tot = usage.get("total_tokens", 0)
    reas = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0)
    
    diff = comp - reas
    clamped_diff = max(0, diff)
    max_tok = max_tok_map.get(agent, "unknown")
    
    sum_prompt += prompt
    sum_comp += comp
    sum_reas += reas
    sum_tot += tot
    sum_visible_naive += diff
    sum_visible_clamped += clamped_diff
    
    print(f"{idx:<3} | {cid:<4} | {agent:<9} | {prompt:<6} | {comp:<9} | {reas:<9} | {tot:<8} | {diff:<9} | {max_tok}")

print("=" * 115)
print(f"SUMS: Prompt={sum_prompt}, Comp={sum_comp}, Reas={sum_reas}, Tot={sum_tot}")
print(f"Naive Visible (Comp - Reas) = {sum_visible_naive}")
print(f"Clamped Visible (max(0, Comp - Reas)) = {sum_visible_clamped}")
print(f"Check sum: Prompt ({sum_prompt}) + Comp ({sum_comp}) = {sum_prompt + sum_comp} (Matches DB Tot: {sum_tot})")
print(f"Check hypothetical overlap: Prompt ({sum_prompt}) + Clamped Visible ({sum_visible_clamped}) + Reas ({sum_reas}) = {sum_prompt + sum_visible_clamped + sum_reas}")
print(f"Discrepancy vs DB Tot: ({sum_prompt + sum_visible_clamped + sum_reas}) - {sum_tot} = {(sum_prompt + sum_visible_clamped + sum_reas) - sum_tot}")
