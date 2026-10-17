import asyncio
import json
import os
import sys
import sqlite3
sys.path.insert(0, os.path.abspath("."))
import httpx
from mas.api.main import app

def run():
    print("=" * 80)
    print("METRICS AND DATA RECONCILIATION SCRIPT")
    print("=" * 80)
    
    conn = sqlite3.connect("mas.db")
    cursor = conn.cursor()
    
    runs = cursor.execute("SELECT run_id, task_id, system, model, actual_model, execution_mode, token_provenance, total_tokens, estimated_cost, status, failure_reason FROM runs").fetchall()
    print("\n[DB: runs]")
    for r in runs:
        print(f"  Run ID: {r[0]}")
        print(f"    Task: {r[1]}, System: {r[2]}, Model: {r[3]}, Actual: {r[4]}")
        print(f"    Mode: {r[5]}, Provenance: {r[6]}, Tokens: {r[7]}, Cost: ${r[8]:.6f}")
        print(f"    Status: {r[9]}")
        print(f"    Failure Reason: {r[10]}")
        
        # Check metrics for this run
        metrics = cursor.execute("SELECT metric_name, metric_value, scope FROM metrics WHERE run_id = ?", (r[0],)).fetchall()
        metric_map = {m[0]: m[1] for m in metrics if m[2] == "neutral"}
        if metric_map:
            c = metric_map.get("completeness", 0.0)
            e = metric_map.get("executability", 0.0)
            s = metric_map.get("consistency", 0.0)
            q_db = metric_map.get("quality", 0.0)
            q_recomputed = round(c * e * s, 4)
            match = (abs(q_db - q_recomputed) < 1e-4)
            print(f"    Neutral Metrics: C={c}, E={e}, S={s}")
            print(f"    Quality in DB: {q_db} | Recomputed Q = C*E*S: {q_recomputed} | Match: {match}")
            if r[7] and r[7] > 0:
                q1k = round(q_recomputed / (r[7] / 1000.0), 4)
                print(f"    Q / 1k Tokens: {q1k}")
            else:
                print(f"    Q / 1k Tokens: UNAVAILABLE (tokens = {r[7]})")

    # API verification
    async def check_api():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            resp = await client.get("/analytics/summary?include_simulated=false")
            print("\n[API: /analytics/summary (include_simulated=false)]")
            print(f"  Status: {resp.status_code}")
            data = resp.json()
            print(f"  Total Runs Analyzed: {data.get('total_runs_analyzed')}")
            print(f"  Provenance Filter: {data.get('provenance_filter')}")
            print(f"  System Comparison: {json.dumps(data.get('system_comparison'), indent=4)}")
            print(f"  Model Breakdown: {json.dumps(data.get('model_breakdown'), indent=4)}")
    
    asyncio.run(check_api())

if __name__ == "__main__":
    run()
