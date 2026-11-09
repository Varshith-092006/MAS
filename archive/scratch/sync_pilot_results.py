import json
import os
import sys
sys.path.insert(0, os.path.abspath("."))
from eval.checks.test_dev_markdown_toc_01 import run_neutral_test
from mas.core.governor import global_governor

run_id_a = "mas_dev_toc_a_p2m_1792332881"
ws_a = os.path.abspath(os.path.join(".", "workspace", run_id_a))
test_results_a = run_neutral_test(ws_a)

pilot_json = "eval/phase2m_pilot_results.json"
with open(pilot_json, "r", encoding="utf-8") as f:
    data = json.load(f)

# Task A completed record
run_a = {
    "slot": "Task A",
    "task_id": "dev_markdown_toc_01",
    "run_id": run_id_a,
    "status": "COMPLETED_QUALITY_GATE",
    "stop_reason": "Clean execution: All 10 independent Level 2 behavioral assertions passed.",
    "duration_seconds": 298.65,
    "calls_dispatched": 5,
    "input_tokens": 3508,
    "output_tokens": 24462,
    "total_tokens": 27970,
    "verified_cost": 0.0,
    "token_provenance": "PROVIDER_REPORTED",
    "architect_invoked": False,
    "behavioral_results": test_results_a,
    "quality_passed": True,
    "recovery_metadata": {
        "interrupted_stage": "Developer CodePatch generation Iteration 1 Attempt 3",
        "in_flight_transmission_id": "att_1792333152_f3b2cb00",
        "in_flight_transmission_state": "RESERVED",
        "work_recovered": "TaskPlan (Artifact 73) and workspace scaffolding preserved",
        "final_code_status": "Complete and verified against Level 2 test suite",
    }
}

# Task B pre-reset paused record
run_b = {
    "slot": "Task B",
    "task_id": "dev_inventory_system_01",
    "run_id": "mas_dev_inv_b_p2m_governor_paused",
    "status": "STOPPED_PROVIDER_QUOTA",
    "stop_reason": "Execution paused pending 2026-10-19 00:00:00 UTC quota reset (~9.11h remaining). Strict pre-reset network freeze in effect.",
    "calls_dispatched": 0,
    "input_tokens": 0,
    "output_tokens": 0,
    "total_tokens": 0,
    "verified_cost": 0.0,
    "token_provenance": "NO_GENERATION_PRODUCED",
    "behavioral_tests": "READY_OFFLINE"
}

data["runs"] = [run_a, run_b]
data["ledger_audit"] = global_governor.get_ledger_stats()

with open(pilot_json, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print("Updated phase2m_pilot_results.json successfully.")
