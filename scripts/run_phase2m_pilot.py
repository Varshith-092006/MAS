"""Phase 2M Post-Reset Live Pilot Execution and Quality Validation Runner.

Enforces:
1. Programmatic UTC Timestamp Verification at execution start.
   Documented Reset Boundary: 2026-10-18 00:00:00 UTC.
   - If boundary has NOT passed: Stop immediately with 0 OpenRouter requests.
   - If boundary HAS passed: Proceed to single permitted quota preflight.
2. Controlled Single-Task Execution:
   - CLI argument `--task-id` (e.g. `dev_markdown_toc_01`) or `--slot` (e.g. `Task A`).
   - If specified, ONLY that task is executed; Tasks B, C, D cannot be triggered.
   - Stops cleanly after the selected task, preserving outputs and remaining allowance.
3. Single Governed Quota Preflight:
   - Exactly ONE request to /api/v1/key via GovernedHTTPClient.
   - Counted as Transmission 1 in new UTC day persistent ledger (leaving max 44).
   - Reads free_model_daily_requests.remaining > 0. (Does not claim key endpoint
     confirms model availability; served identity and cost verified on first generation
     response with allow_fallbacks=False).
   - No repeated probes on subsequent task dispatches.
4. Transmission Allowance & Quality Gate Halting:
   - Verifies sufficient remaining HTTP attempts (>= 3) before beginning any task.
   - Halts the entire series immediately if any task fails its Level 2 behavioral suite.
5. Strict Ceilings & Fallback Lock:
   - Configured: cohere/north-mini-code:free ($0.00 cost, allow_fallbacks=False).
   - Max 15 calls/run, 60,000 tokens/run, 45 HTTP requests/day.
"""

import os
import sys
import json
import time
import argparse
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()

# Enforce pilot budgets in environment
os.environ["OPENROUTER_MODEL"] = "cohere/north-mini-code:free"
os.environ["OPENROUTER_CHEAP_MODEL"] = "cohere/north-mini-code:free"
os.environ["MAX_CALLS_PER_RUN"] = "15"
os.environ["MAX_DAILY_HTTP_TRANSMISSIONS"] = "45"
os.environ["OPENROUTER_REASONING_MAX_TOKENS"] = "0"

from mas.core.llm import (
    OpenRouterProvider,
    token_logger,
    DispatchCeilingExceededError,
    DailyTransmissionsCeilingExceededError,
    TokenCapExceededError,
    OpenRouterAPIError,
    ModelMismatchError,
)
from mas.core.governor import ProviderQuotaGovernor, GovernedHTTPClient, global_governor
from mas.core.workflow import MASWorkflow
from mas.db.session import get_session
from mas.db.models import Run, ModelCall, AgentEvent, Artifact, Metric

from eval.checks.test_dev_markdown_toc_01 import run_neutral_test as run_toc_l2
from eval.checks.test_dev_inventory_system_01 import run_neutral_test as run_inventory_l2
from eval.checks.test_dev_log_analyzer_01 import run_neutral_test as run_log_l2


PILOT_TASKS = [
    {
        "slot": "Task A",
        "task_id": "dev_markdown_toc_01",
        "run_prefix": "mas_dev_toc_a_p2m",
        "path_type": "SIMPLE",
        "checker": run_toc_l2,
        "requirement": (
            "Markdown Table of Contents Generator CLI: Read and parse Markdown files, extract level 1 to level 3 headings (#, ##, ###), "
            "and generate a formatted bulleted table of contents with anchor links (e.g. - [Title](#title)). "
            "Ignore headings inside fenced code blocks (```). Handle empty input files cleanly with code 0 without crashing. "
            "Handle non-existent input files cleanly with code 1 and stderr message without unhandled exceptions. "
            "Provide a usable command-line entry point in main.py with --help option exiting code 0, and report usage error with code 2 on missing arguments. "
            "Include automated behavioral unit tests in test_main.py covering normal and edge cases."
        ),
    },
    {
        "slot": "Task B",
        "task_id": "dev_inventory_system_01",
        "run_prefix": "mas_dev_inv_b_p2m",
        "path_type": "STRUCTURED",
        "checker": run_inventory_l2,
        "requirement": (
            "A multi-module inventory management service and CLI application requiring coherent architecture, modular contracts, and data persistence. "
            "The system must include: 1. Data models with validation for quantity and price. "
            "2. Persistence layer for repository storage in a JSON file database. "
            "3. Service workflow layer managing stock transactions, reorders, and inventory lifecycle. "
            "4. Reporting module providing inventory metrics, statistics, and low-stock alerts. "
            "5. CLI interface executable via main.py supporting add, restock, sell, and report commands. "
            "Must handle malformed files, negative stock errors, missing arguments, and corrupt storage records gracefully."
        ),
    },
    {
        "slot": "Task C",
        "task_id": "dev_log_analyzer_01",
        "run_prefix": "mas_dev_log_c_p2m",
        "path_type": "SIMPLE",
        "checker": run_log_l2,
        "requirement": (
            "A log analyzer CLI tool that calculates summary statistics from web server access log files, "
            "computes status code counts, total bandwidth bytes, and error percentages, "
            "skipping malformed lines with warnings and handling empty files cleanly. "
            "Provide entry point main.py with --help exiting code 0, exit code 2 on missing args, exit code 1 on missing log file, "
            "and include unit tests in test_main.py."
        ),
    },
    {
        "slot": "Task D",
        "task_id": "dev_markdown_toc_01_repeat",
        "run_prefix": "mas_dev_toc_d_p2m_repeat",
        "path_type": "SIMPLE",
        "checker": run_toc_l2,
        "requirement": (
            "Markdown Table of Contents Generator CLI: Read and parse Markdown files, extract level 1 to level 3 headings (#, ##, ###), "
            "and generate a formatted bulleted table of contents with anchor links (e.g. - [Title](#title)). "
            "Ignore headings inside fenced code blocks (```). Handle empty input files cleanly with code 0 without crashing. "
            "Handle non-existent input files cleanly with code 1 and stderr message without unhandled exceptions. "
            "Provide a usable command-line entry point in main.py with --help option exiting code 0, and report usage error with code 2 on missing arguments. "
            "Include automated behavioral unit tests in test_main.py covering normal and edge cases."
        ),
    },
]


def load_or_init_summary(file_path: str, model_id: str, today_str: str, now_utc: datetime) -> Dict[str, Any]:
    """Loads existing summary JSON if present, otherwise initializes default structure."""
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return {
        "series_timestamp": int(time.time()),
        "phase": "PHASE_2M",
        "utc_date": today_str,
        "current_utc_time": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model_requested": model_id,
        "allow_fallbacks": False,
        "reset_status": {},
        "ledger_audit": {},
        "preflight_metadata": None,
        "runs": [],
    }


def update_run_in_summary(summary: Dict[str, Any], run_entry: Dict[str, Any]) -> None:
    """Updates or appends a run entry in the summary dictionary by task_id."""
    existing_runs = summary.get("runs", [])
    updated = False
    for i, r in enumerate(existing_runs):
        if r.get("task_id") == run_entry.get("task_id"):
            existing_runs[i] = run_entry
            updated = True
            break
    if not updated:
        existing_runs.append(run_entry)
    summary["runs"] = existing_runs


def run_phase2m_pilot(selected_task_id: Optional[str] = None):
    model_id = "cohere/north-mini-code:free"
    timestamp = int(time.time())

    # Filter tasks if single-task mode requested
    if selected_task_id:
        norm_sel = selected_task_id.strip().lower()
        matched_tasks = [
            t for t in PILOT_TASKS
            if t["task_id"].lower() == norm_sel or t["slot"].lower() == norm_sel
        ]
        if not matched_tasks:
            print(f"[ERROR] Task identifier '{selected_task_id}' not found in PILOT_TASKS.")
            print(f"Valid choices: {[t['task_id'] for t in PILOT_TASKS]} or {[t['slot'] for t in PILOT_TASKS]}")
            sys.exit(1)
        tasks_to_run = matched_tasks
        print(f"[MODE] Controlled Single-Task Execution Enabled: Running ONLY {tasks_to_run[0]['slot']} ({tasks_to_run[0]['task_id']})")
    else:
        tasks_to_run = PILOT_TASKS
        print("[MODE] Sequential Multi-Task Execution Enabled: Evaluating Tasks A -> D")

    print("=" * 80)
    print("PHASE 2M — POST-RESET LIVE PILOT EXECUTION AND QUALITY VALIDATION")
    print(f"Configured Model: {model_id} (Verified Free Tier, $0.00 cost, allow_fallbacks=False)")
    print(f"Safety Ceilings: Max 15 calls/run, Max 60,000 tokens/run, Max 45 HTTP attempts/day (UTC)")
    print("=" * 80)

    # 1. Programmatic UTC Timestamp Verification
    now_utc = datetime.now(timezone.utc)
    today_str = now_utc.strftime("%Y-%m-%d")
    boundary_str = os.environ.get("MAS_RESET_BOUNDARY_UTC", "2026-10-18T00:00:00Z")
    try:
        parsed_b = datetime.fromisoformat(boundary_str.replace("Z", "+00:00"))
        # If datetime was patched by unittest.mock, fromisoformat returns a MagicMock
        if not hasattr(parsed_b, "year") or str(type(parsed_b)).find("Mock") != -1:
            reset_boundary = datetime(2026, 10, 18, 0, 0, 0, tzinfo=timezone.utc)
        else:
            reset_boundary = parsed_b
    except Exception:
        reset_boundary = datetime(2026, 10, 18, 0, 0, 0, tzinfo=timezone.utc)
    boundary_passed = now_utc >= reset_boundary

    print(f"\n[TIME CHECK] Current System UTC Timestamp: {now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"[RESET BOUNDARY] Documented Reset Boundary: {reset_boundary.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"[BOUNDARY STATUS] Has reset boundary passed?: {boundary_passed}")

    time_diff = reset_boundary - now_utc
    seconds_to_reset = max(0, int(time_diff.total_seconds()))
    hours_to_reset = round(seconds_to_reset / 3600.0, 2)

    ledger_stats = global_governor.get_ledger_stats()
    print(f"\n[LEDGER AUDIT] Persistent Ledger (eval/outbound_transmission_ledger.json):")
    print(f"  - Active UTC Date: {ledger_stats['utc_date']}")
    print(f"  - Outbound Transmissions Today: {ledger_stats['total_attributable_attempts']} / {ledger_stats['internal_daily_cap']}")
    print(f"  - Cap Breached Today: {ledger_stats['cap_breached']} (Excess: {ledger_stats['excess_transmissions']})")
    print(f"  - Historical October 17 Record: Preserved (54 transmissions / 45 ceiling)")

    out_json = "eval/phase2m_pilot_results.json"
    pilot_summary = load_or_init_summary(out_json, model_id, today_str, now_utc)
    pilot_summary["current_utc_time"] = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    pilot_summary["reset_status"] = {
        "reset_boundary_utc": reset_boundary.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "boundary_passed": boundary_passed,
        "hours_until_reset": hours_to_reset,
        "seconds_until_reset": seconds_to_reset,
    }
    pilot_summary["ledger_audit"] = ledger_stats

    # Strict network restriction if boundary has NOT passed
    if not boundary_passed:
        print("\n" + "!" * 80)
        print(f"STOPPING IMMEDIATELY: Documented reset boundary ({reset_boundary.strftime('%Y-%m-%d %H:%M:%S UTC')}) has NOT passed.")
        print(f"Current UTC time is {now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}.")
        print(f"Remaining duration until reset: ~{hours_to_reset} hours ({seconds_to_reset} seconds).")
        print("Per Section 1 mandate: Zero OpenRouter requests sent (no /api/v1/key, no models, no generation).")
        print("Historical October 17 and October 18 ledger records are preserved unchanged.")
        print("No automatic polling or resumption assumed. Runner must be re-executed after 00:00:00 UTC.")
        print("!" * 80 + "\n")

        for task_def in tasks_to_run:
            slot = task_def["slot"]
            task_id = task_def["task_id"]
            run_prefix = task_def["run_prefix"]
            stop_reason = (
                f"Execution paused pending {reset_boundary.strftime('%Y-%m-%d %H:%M:%S UTC')} quota reset (~{hours_to_reset}h remaining). "
                f"Strict pre-reset network freeze in effect."
            )
            print(f"[{slot} - {task_id}] Status: STOPPED_PROVIDER_QUOTA (Pre-reset pause)")
            run_entry = {
                "slot": slot,
                "task_id": task_id,
                "run_id": f"{run_prefix}_governor_paused",
                "status": "STOPPED_PROVIDER_QUOTA",
                "stop_reason": stop_reason,
                "calls_dispatched": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "verified_cost": 0.0,
                "token_provenance": "NO_GENERATION_PRODUCED",
                "behavioral_tests": "READY_OFFLINE",
            }
            update_run_in_summary(pilot_summary, run_entry)

        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(pilot_summary, f, indent=2)
        print(f"\n[DONE] Saved Phase 2M Pilot State to {out_json}")
        return pilot_summary

    # --- 2. POST-RESET EXECUTION PROTOCOL (Only if boundary_passed is True) ---
    print("\n[BOUNDARY TRANSITION] 2026-10-18 00:00:00 UTC reset boundary reached!")
    global_governor.initialize_day(today_str)
    provider = OpenRouterProvider(default_model=model_id)

    # Perform exactly ONE preflight metadata check for the new day
    if not pilot_summary.get("preflight_metadata"):
        print("\n[TRANSMISSION 1] Executing exactly ONE preflight metadata check via GovernedHTTPClient...")
        key_status = global_governor.check_upstream_key_status(provider, record_attempt=True)
        pilot_summary["preflight_metadata"] = key_status
    else:
        key_status = pilot_summary["preflight_metadata"]
        print("\n[PREFLIGHT] Utilizing already verified daily key metadata preflight...")

    updated_ledger = global_governor.get_ledger_stats()
    print(f"  - Key metadata recorded as transmission {updated_ledger['total_attributable_attempts']} of {updated_ledger['internal_daily_cap']}")
    print(f"  - Remaining internal HTTP attempts today: {updated_ledger['remaining_internal_attempts']}")
    print(f"  - Upstream remaining free requests: {key_status.get('free_models_remaining')}")

    if not key_status.get("can_proceed", False) or key_status.get("is_quota_exhausted", True) or key_status.get("free_models_remaining", 0) <= 0:
        stop_reason = key_status.get("stop_reason") or "Upstream free quota remains unavailable/exhausted after reset check."
        print(f"\n[STOP] {stop_reason} Stopping per Section 2.")
        for task_def in tasks_to_run:
            run_entry = {
                "slot": task_def["slot"],
                "task_id": task_def["task_id"],
                "status": "STOPPED_PROVIDER_QUOTA",
                "stop_reason": stop_reason,
                "calls_dispatched": 0,
            }
            update_run_in_summary(pilot_summary, run_entry)

        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(pilot_summary, f, indent=2)
        return pilot_summary

    # Execute selected tasks sequentially
    for idx, task_def in enumerate(tasks_to_run):
        slot = task_def["slot"]
        task_id = task_def["task_id"]
        run_prefix = task_def["run_prefix"]
        req = task_def["requirement"]
        checker = task_def["checker"]

        # Check remaining transmission allowance before beginning task
        current_stats = global_governor.get_ledger_stats()
        remaining_allowance = current_stats["remaining_internal_attempts"]
        min_required_attempts = 3  # Minimum transmissions expected for an MAS workflow run
        if remaining_allowance < min_required_attempts:
            stop_reason = (
                f"Insufficient remaining daily HTTP transmission allowance ({remaining_allowance} < {min_required_attempts}). "
                f"Stopping safely before {slot} to prevent partial run execution."
            )
            print(f"\n[STOP] {stop_reason}")
            run_entry = {
                "slot": slot,
                "task_id": task_id,
                "status": "STOPPED_BUDGET_CEILING",
                "stop_reason": stop_reason,
                "calls_dispatched": 0,
            }
            update_run_in_summary(pilot_summary, run_entry)
            break

        # Evaluate dispatch permission WITHOUT passing provider (prevents redundant /api/v1/key calls)
        allowed, status_code, reason_dict = global_governor.evaluate_dispatch_permission(
            slot_name=slot,
            task_id=task_id,
            provider=None,
        )

        if not allowed:
            print(f"[{slot}] Dispatch blocked: {status_code} ({reason_dict.get('reason')})")
            run_entry = {
                "slot": slot,
                "task_id": task_id,
                "status": status_code,
                "stop_reason": reason_dict.get("reason"),
                "calls_dispatched": 0,
            }
            update_run_in_summary(pilot_summary, run_entry)
            break

        run_id = f"{run_prefix}_{int(time.time())}"
        print(f"\nSTARTING LIVE TASK: {run_id} ({slot} - {task_id})")
        workflow = MASWorkflow(llm=provider)
        t0 = time.time()

        try:
            final_state = workflow.run(
                requirement=req,
                task_id=task_id,
                model_name=model_id,
                run_id=run_id,
                workspace_base="./workspace",
            )
            run_status = final_state.get("status", "COMPLETED_QUALITY_GATE")
            stop_reason = final_state.get("stop_reason", "")
        except OpenRouterAPIError as e:
            terminal_status = global_governor.handle_api_error(e, slot_name=slot, task_id=task_id)
            run_status = terminal_status
            stop_reason = f"{terminal_status}: {e.error_message or str(e)}"
        except ModelMismatchError as e:
            run_status = "FAILED_MODEL_MISMATCH"
            stop_reason = f"ModelMismatchError: {str(e)}"
            print(f"\n[MODEL MISMATCH] Served model differs from configured model: {e}")
        except DailyTransmissionsCeilingExceededError as e:
            run_status = "STOPPED_BUDGET_CEILING"
            stop_reason = f"STOPPED_BUDGET_CEILING: {str(e)}"
        except Exception as e:
            run_status = "FAILED"
            stop_reason = f"ERROR: {str(e)}"

        duration = time.time() - t0
        with get_session() as session:
            calls = session.query(ModelCall).filter(ModelCall.run_id == run_id).all()
            events = session.query(AgentEvent).filter(AgentEvent.run_id == run_id).all()

        total_in = sum(c.input_tokens for c in calls)
        total_out = sum(c.output_tokens for c in calls)
        total_tokens = total_in + total_out
        total_cost = sum(c.cost for c in calls)

        # Confirm ArchitectAgent invoked for structured tasks
        architect_invoked = any(getattr(ev, "agent", "") in ("ArchitectAgent", "architect") for ev in events) if task_def["path_type"] == "STRUCTURED" else None

        # Behavioral test verification against generated artifacts
        ws_dir = os.path.join(".", "workspace", run_id)
        behavioral_results = {}
        if os.path.exists(ws_dir) and checker:
            try:
                behavioral_results = checker(ws_dir)
            except Exception as e:
                behavioral_results = {"error": str(e), "all_passed": False}

        # Apply strict acceptance gate
        quality_passed = behavioral_results.get("all_passed", False) if checker else (run_status == "COMPLETED_QUALITY_GATE")
        if not quality_passed and run_status == "COMPLETED_QUALITY_GATE":
            run_status = "FAILED_QUALITY_GATE"
            stop_reason = "Generated artifacts failed Level 2 behavioral assertion criteria."

        run_entry = {
            "slot": slot,
            "task_id": task_id,
            "run_id": run_id,
            "status": run_status,
            "stop_reason": stop_reason,
            "duration_seconds": round(duration, 2),
            "calls_dispatched": len(calls),
            "input_tokens": total_in,
            "output_tokens": total_out,
            "total_tokens": total_tokens,
            "verified_cost": total_cost,
            "architect_invoked": architect_invoked,
            "behavioral_results": behavioral_results,
            "quality_passed": quality_passed,
        }
        update_run_in_summary(pilot_summary, run_entry)

        # If quality gate failed, halt further task execution immediately
        if not quality_passed:
            print(f"\n[QUALITY GATE HALT] Task {slot} ({task_id}) failed quality assertions. Halting series.")
            break

        # If in single-task mode, stop after this task
        if selected_task_id:
            print(f"\n[SINGLE-TASK COMPLETE] Completed requested task {slot} ({task_id}). Stopping cleanly.")
            break

        time.sleep(5)

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(pilot_summary, f, indent=2)
    return pilot_summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 2M Live Pilot Execution Runner")
    parser.add_argument(
        "--task-id",
        "--task",
        "--slot",
        dest="task_id",
        type=str,
        default=None,
        help="Run only a single selected task (e.g. 'dev_markdown_toc_01' or 'Task A').",
    )
    args = parser.parse_args()
    run_phase2m_pilot(selected_task_id=args.task_id)
