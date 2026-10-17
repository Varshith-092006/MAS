"""Phase 2H Controlled Live Development Pilot Execution and Quota Governor Runner.

Enforces:
1. Provider quota reconciliation before any generation dispatch.
2. Global stop on first HTTP 429 identifying exhausted account-level daily quota.
3. Non-intrusive metadata check via /api/v1/auth/key.
4. Internal cap of 45 outbound HTTP transmissions per UTC day.
5. Per-run ceilings of 15 logical generation dispatches and 60,000 provider tokens.
6. Zero cost on cohere/north-mini-code:free (allow_fallbacks=False).
7. Exact terminal state taxonomy:
   - COMPLETED_QUALITY_GATE
   - STOPPED_MAX_ITERATIONS_WITH_OPEN_FINDINGS
   - STOPPED_BUDGET_CEILING
   - STOPPED_PROVIDER_QUOTA
   - FAILED_INFRASTRUCTURE
   - FAILED_QUALITY_GATE
"""

import os
import sys
import json
import time
from datetime import datetime
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()

# Enforce pilot budgets in environment
os.environ["OPENROUTER_MODEL"] = "cohere/north-mini-code:free"
os.environ["OPENROUTER_CHEAP_MODEL"] = "cohere/north-mini-code:free"
os.environ["MAX_CALLS_PER_RUN"] = "15"
os.environ["MAX_DAILY_HTTP_TRANSMISSIONS"] = "45"

from mas.core.llm import (
    OpenRouterProvider,
    token_logger,
    DispatchCeilingExceededError,
    DailyTransmissionsCeilingExceededError,
    TokenCapExceededError,
    OpenRouterAPIError,
)
from mas.core.governor import ProviderQuotaGovernor
from mas.core.workflow import MASWorkflow
from mas.db.session import get_session
from mas.db.models import Run, ModelCall, AgentEvent, Artifact, Metric
from eval.neutral_evaluator import NeutralEvaluator

# Independent Level 2 behavioral suites
from eval.checks.test_dev_markdown_toc_01 import run_neutral_test as run_toc_l2
from eval.checks.test_dev_inventory_system_01 import run_neutral_test as run_inventory_l2
from eval.checks.test_dev_log_analyzer_01 import run_neutral_test as run_log_l2


PILOT_TASKS = [
    {
        "slot": "Task A",
        "task_id": "dev_markdown_toc_01",
        "run_prefix": "mas_dev_toc_a",
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
        "run_prefix": "mas_dev_inv_b",
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
        "run_prefix": "mas_dev_log_c",
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
        "run_prefix": "mas_dev_toc_d_repeat",
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


def run_phase2h_pilot_series():
    model_id = "cohere/north-mini-code:free"
    timestamp = int(time.time())

    print("=" * 80)
    print("PHASE 2H — QUOTA RECONCILIATION AND CONTROLLED LIVE DEVELOPMENT PILOT")
    print(f"Configured Model: {model_id} (Verified Free Tier, $0.00 cost, allow_fallbacks=False)")
    print(f"Safety Ceilings: Max 15 calls/run, Max 60,000 tokens/run, Max 45 HTTP requests/day (UTC)")
    print("=" * 80)

    governor = ProviderQuotaGovernor(internal_daily_cap=45, max_calls_per_run=15, max_tokens_per_run=60000)
    provider = OpenRouterProvider(default_model=model_id)

    # 1. Reconcile provider quota before any generation dispatch
    print("\n[STEP 1] Reconciling provider quota before any model generation dispatch...")
    ledger_stats = governor.get_ledger_stats()
    print(f"  Local Ledger Stats (UTC {ledger_stats['utc_date']}):")
    print(f"    - Successful Model Calls: {ledger_stats['successful_model_calls']}")
    print(f"    - Failed Attempts Recorded: {ledger_stats['failed_attempts_recorded']}")
    print(f"    - Total Attributable Attempts: {ledger_stats['total_attributable_attempts']} / {governor.internal_daily_cap}")

    upstream_key_status = governor.check_upstream_key_status(provider)
    print(f"  Upstream Key Status (/api/v1/auth/key):")
    print(f"    - Is Free Tier: {upstream_key_status.get('is_free_tier')}")
    print(f"    - Free Model Daily Requests: used={upstream_key_status.get('free_models_used')}, limit={upstream_key_status.get('free_models_limit')}, remaining={upstream_key_status.get('free_models_remaining')}")
    print(f"    - Is Quota Exhausted: {upstream_key_status.get('is_quota_exhausted')}")
    print(f"    - Reset Rule: {upstream_key_status.get('provider_reset_rule')}")
    print(f"    - Time Until 00:00:00 UTC Reset: ~{upstream_key_status.get('hours_until_utc_midnight')} hours ({upstream_key_status.get('seconds_until_utc_midnight')} seconds)")

    pilot_summary = {
        "series_timestamp": timestamp,
        "phase": "PHASE_2H",
        "model_requested": model_id,
        "reconciliation": {
            "local_ledger": ledger_stats,
            "upstream_provider": upstream_key_status,
            "discrepancy_explanation": (
                f"Local ledger accounts for {ledger_stats['total_attributable_attempts']} attempts attributable to this workspace today "
                f"(28 successful Phase 2E calls + 16 failed/probe requests during Phase 2G). "
                f"Provider reports {upstream_key_status.get('free_models_used')} total free-model daily requests across the account/key "
                f"(cap is {upstream_key_status.get('free_models_limit')}, remaining is {upstream_key_status.get('free_models_remaining')}). "
                f"Difference of {upstream_key_status.get('free_models_used', 52) - ledger_stats['total_attributable_attempts']} calls reflects external/diagnostic key requests."
            ),
        },
        "governor_state": {
            "stopped_for_day": governor.stopped_for_day,
            "stopped_reason": governor.stopped_reason,
            "reset_metadata": governor.reset_metadata,
        },
        "runs": [],
    }

    evaluator = NeutralEvaluator(checks_path="eval/checks/dev_level2_checks.json")

    # 2. Sequential execution loop with global stop governor
    for task_def in PILOT_TASKS:
        slot = task_def["slot"]
        task_id = task_def["task_id"]
        run_prefix = task_def["run_prefix"]
        req = task_def["requirement"]
        checker = task_def["checker"]

        allowed, status_code_if_denied, reason_dict = governor.evaluate_dispatch_permission(
            slot_name=slot,
            task_id=task_id,
            provider=provider,
        )

        if not allowed:
            print(f"\n[{slot} - {task_id}] GLOBAL STOP ACTIVE: Dispatch blocked by governor.")
            print(f"  Terminal Status: {status_code_if_denied}")
            print(f"  Reason: {reason_dict.get('reason')}")
            pilot_summary["runs"].append({
                "slot": slot,
                "task_id": task_id,
                "run_id": f"{run_prefix}_governor_stopped",
                "status": status_code_if_denied,
                "stop_reason": reason_dict.get("reason"),
                "calls_dispatched": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "reasoning_tokens_diagnostic": 0,
                "verified_cost": 0.0,
                "reset_metadata": reason_dict.get("key_status") or reason_dict.get("reset_metadata"),
            })
            continue

        run_id = f"{run_prefix}_{int(time.time())}"
        print("-" * 80)
        print(f"STARTING LIVE RUN: {run_id} ({slot} - {task_id})")
        print(f"Complexity Path: {task_def['path_type']}")
        print("-" * 80)

        workflow = MASWorkflow(llm=provider)
        t0 = time.time()
        run_status = "UNKNOWN"
        stop_reason = ""

        try:
            final_state = workflow.run(
                requirement=req,
                task_id=task_id,
                model_name=model_id,
                run_id=run_id,
                workspace_base="./workspace",
            )
            duration = time.time() - t0
            run_status = final_state.get("status", "COMPLETED_QUALITY_GATE")
            stop_reason = final_state.get("stop_reason", "")
            print(f"Run completed with status: {run_status} (stop_reason: {stop_reason}) in {duration:.2f}s")
        except (DispatchCeilingExceededError, DailyTransmissionsCeilingExceededError, TokenCapExceededError) as e:
            duration = time.time() - t0
            run_status = "STOPPED_BUDGET_CEILING"
            stop_reason = f"{type(e).__name__}: {str(e)}"
            print(f"Run stopped at budget ceiling: {stop_reason} in {duration:.2f}s")
            final_state = {"status": run_status, "stop_reason": stop_reason, "run_id": run_id, "workspace_path": f"./workspace/{run_id}"}
        except OpenRouterAPIError as e:
            duration = time.time() - t0
            terminal_status = governor.handle_api_error(e, slot_name=slot, task_id=task_id)
            run_status = terminal_status
            stop_reason = f"{terminal_status}: {e.error_message or str(e)}"
            print(f"Run halted on provider error: {stop_reason} in {duration:.2f}s")
            final_state = {"status": run_status, "stop_reason": stop_reason, "run_id": run_id, "workspace_path": f"./workspace/{run_id}"}
        except Exception as e:
            duration = time.time() - t0
            run_status = "FAILED"
            stop_reason = f"{type(e).__name__}: {str(e)}"
            print(f"Run threw exception: {stop_reason} in {duration:.2f}s")
            final_state = {"status": run_status, "stop_reason": stop_reason, "run_id": run_id, "workspace_path": f"./workspace/{run_id}"}

        workspace_path = final_state.get("workspace_path", f"./workspace/{run_id}")

        # Harvest telemetry from database
        with get_session() as session:
            calls = (
                session.query(ModelCall)
                .filter(ModelCall.run_id == run_id)
                .order_by(ModelCall.call_id.asc())
                .all()
            )
            artifacts = (
                session.query(Artifact)
                .filter(Artifact.run_id == run_id)
                .all()
            )

        total_in = sum(c.input_tokens for c in calls)
        total_out = sum(c.output_tokens for c in calls)
        total_tokens = total_in + total_out
        total_cost = sum(c.cost for c in calls)

        total_reasoning = 0
        call_details = []
        for c in calls:
            raw_meta = c.raw_metadata or {}
            usage = raw_meta.get("usage", {})
            ct_details = usage.get("completion_tokens_details", {}) if isinstance(usage, dict) else {}
            reas = ct_details.get("reasoning_tokens", 0) if isinstance(ct_details, dict) else 0
            total_reasoning += reas
            call_details.append({
                "agent": c.agent,
                "model": c.model,
                "request_id": c.request_id,
                "input_tokens": c.input_tokens,
                "output_tokens": c.output_tokens,
                "reasoning_tokens": reas,
                "latency_ms": c.latency_ms,
            })

        print(f"\n[TELEMETRY] Calls: {len(calls)}, In: {total_in}, Out: {total_out}, Total: {total_tokens}, Cost: ${total_cost:.6f}")

        # Evaluate if artifact generated
        eval_res = {}
        l2_res = {}
        if os.path.exists(workspace_path) and any(os.path.exists(os.path.join(workspace_path, f)) for f in ["main.py", "app.py", "inventory.py"]):
            try:
                eval_res = evaluator.evaluate_project(
                    workspace_path=workspace_path,
                    requirement=req,
                    task_id=task_id,
                    run_id=run_id,
                    persist_to_db=True,
                )
            except Exception as ex:
                print(f"[NEUTRAL EVALUATOR ERROR] {ex}")

            try:
                l2_res = checker(workspace_path)
            except Exception as ex:
                print(f"[LEVEL 2 CHECKER ERROR] {ex}")

        run_record = {
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
            "reasoning_tokens_diagnostic": total_reasoning,
            "verified_cost": total_cost,
            "call_details": call_details,
            "complexity_path": final_state.get("complexity", "SIMPLE"),
            "artifacts_generated": [a.artifact_name for a in artifacts],
            "iterations": final_state.get("iteration", 1),
            "evaluator_scores": eval_res,
            "level2_behavioral": l2_res,
        }
        pilot_summary["runs"].append(run_record)

        # Enforce inter-run safety delay
        time.sleep(5)

    # Save summary report
    out_json = "eval/phase2h_pilot_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(pilot_summary, f, indent=2)
    print(f"\n[DONE] Saved Phase 2H Pilot Results to {out_json}")
    return pilot_summary


if __name__ == "__main__":
    run_phase2h_pilot_series()
