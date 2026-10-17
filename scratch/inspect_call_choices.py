import sqlite3
import json

conn = sqlite3.connect('mas.db')
c = conn.cursor()

pilot_id = "mas_dev_csv_sales_1792211689"

print("Detailed choices and usage for calls:")
for row in c.execute('SELECT call_id, agent, requested_model, input_tokens, output_tokens, total_tokens, raw_metadata FROM model_calls WHERE run_id = ? ORDER BY call_id', (pilot_id,)):
    cid, agent, req_m, in_tok, out_tok, tot_tok, raw_meta = row
    meta = json.loads(raw_meta) if raw_meta else {}
    usage = meta.get("usage", {})
    choices = meta.get("choices", [])
    finish_reason = choices[0].get("finish_reason") if choices else None
    content_len = len(choices[0].get("message", {}).get("content") or "") if choices else 0
    print(f"Call {cid} [{agent}]: finish_reason={finish_reason}, content_chars={content_len}, out_tok={out_tok}, usage={usage}")
