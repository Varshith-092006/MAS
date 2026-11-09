"""Audit script to recompute Completeness, Executability, Consistency, and Quality

for every run in results.csv from its workspace (when present) and report discrepancies > 0.01.
Does NOT modify or rewrite results.csv or database tables.
"""

import csv
import json
import os
import sys

# Ensure repository root is on path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

os.environ["MAS_ALLOW_SUBPROCESS_SANDBOX"] = "1"

from eval.neutral_evaluator import NeutralEvaluator


def load_task_descriptions() -> dict:
    tasks_file = os.path.join(REPO_ROOT, "eval", "tasks.json")
    task_map = {}
    if os.path.exists(tasks_file):
        try:
            with open(tasks_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for t in data:
                    tid = t.get("task_id")
                    if tid:
                        task_map[tid] = t.get("description", "")
        except Exception as e:
            print(f"[WARN] Error loading tasks.json: {e}")
    return task_map


def safe_float(val):
    if val is None or val == "" or str(val).strip().lower() in ("none", "null", "nan"):
        return None
    try:
        return float(val)
    except ValueError:
        return None


def find_workspace(run_id: str) -> str | None:
    candidates = [
        os.path.join(REPO_ROOT, "eval", "workspaces", run_id),
        os.path.join(REPO_ROOT, "workspace", run_id),
    ]
    for c in candidates:
        if os.path.exists(c) and os.path.isdir(c):
            return c
    return None


def audit_scores(csv_path: str = "results.csv"):
    csv_file = os.path.join(REPO_ROOT, csv_path)
    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} does not exist.")
        return

    task_map = load_task_descriptions()
    evaluator = NeutralEvaluator()

    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Loaded {len(rows)} rows from {csv_path}\n" + "=" * 80)

    total_checked = 0
    workspaces_found = 0
    workspaces_missing = 0
    discrepancies = []

    for r in rows:
        total_checked += 1
        run_id = r.get("run_id", "").strip()
        task_id = r.get("task_id", "").strip()
        system = r.get("system", "").strip()
        status = r.get("status", "").strip()

        ws = find_workspace(run_id)
        if not ws:
            workspaces_missing += 1
            continue

        workspaces_found += 1
        req = task_map.get(task_id, "")

        try:
            metrics = evaluator.evaluate_project(ws, req, task_id=task_id, persist_to_db=False)
        except Exception as exc:
            print(f"[{run_id}] Evaluation error: {exc}")
            continue

        c_stored = safe_float(r.get("completeness"))
        e_stored = safe_float(r.get("executability"))
        s_stored = safe_float(r.get("consistency"))
        q_stored = safe_float(r.get("quality"))

        c_calc = metrics.get("completeness")
        e_calc = metrics.get("executability")
        s_calc = metrics.get("consistency")
        q_calc = metrics.get("quality")

        diffs = {}
        for m_name, stored_val, calc_val in [
            ("completeness", c_stored, c_calc),
            ("executability", e_stored, e_calc),
            ("consistency", s_stored, s_calc),
            ("quality", q_stored, q_calc),
        ]:
            if stored_val is not None and calc_val is not None:
                diff = abs(stored_val - calc_val)
                if diff > 0.01:
                    diffs[m_name] = {
                        "stored": stored_val,
                        "recomputed": calc_val,
                        "delta": round(diff, 4),
                    }
            elif stored_val is not None and calc_val is None:
                diffs[m_name] = {"stored": stored_val, "recomputed": None, "delta": "None"}
            elif stored_val is None and calc_val is not None:
                # If stored was None (e.g. run failed/stopped), calculate whether quality was zeroed
                if status not in ("FAILED", "STOPPED_BUDGET_CEILING", "INCOMPLETE") and calc_val > 0:
                    diffs[m_name] = {"stored": None, "recomputed": calc_val, "delta": "Missing"}

        if diffs:
            discrepancies.append({
                "run_id": run_id,
                "system": system,
                "status": status,
                "diffs": diffs,
            })
            print(f"[DISCREPANCY] Run: {run_id} ({system}, status: {status})")
            for m_name, d in diffs.items():
                print(f"   - {m_name}: stored={d['stored']} vs recomputed={d['recomputed']} (delta: {d['delta']})")

    print("=" * 80)
    print("AUDIT SUMMARY:")
    print(f"Total rows inspected:      {total_checked}")
    print(f"Workspaces present:        {workspaces_found}")
    print(f"Workspaces absent/cleaned: {workspaces_missing}")
    print(f"Runs with discrepancies:   {len(discrepancies)}")
    if discrepancies:
        print("\nSummary of discrepant runs:")
        for d in discrepancies:
            print(f"  * {d['run_id']} ({d['system']}): {list(d['diffs'].keys())}")
    else:
        print("\nNo score discrepancies > 0.01 detected among available workspaces.")


if __name__ == "__main__":
    audit_scores()
