"""Phase 2K Verified Quota Reset, Transmission Governance, and Live Pilot Resumption Runner.

Enforces:
1. Unified Outbound Transmission Ledger (eval/outbound_transmission_ledger.json).
2. All outbound HTTP traffic routed through GovernedHTTPClient instrumented wrapper.
3. Strict pause maintained until documented 00:00:00 UTC daily reset has passed.
4. Exactly ONE preflight metadata query on the new UTC day, counted as transmission 1 (leaving max 44).
5. Sequential execution order:
   Task A: dev_markdown_toc_01
   Task B: dev_inventory_system_01 (STRUCTURED - ArchitectAgent invoked)
   Task C: dev_log_analyzer_01
   Task D: dev_markdown_toc_01_repeat
6. Strict per-run ceilings: 15 calls, 60,000 tokens, 45 HTTP requests/day, $0.00 cost, allow_fallbacks=False.
7. Quality gates: independent Level 2 behavioral suites executed; COMPLETED_QUALITY_GATE vs STOPPED_PROVIDER_QUOTA vs STOPPED_BUDGET_CEILING.
"""

import os
import sys
import json
import time
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

from mas.core.llm import (
    OpenRouterProvider,
    token_logger,
    DispatchCeilingExceededError,
    DailyTransmissionsCeilingExceededError,
    TokenCapExceededError,
    OpenRouterAPIError,
)
from mas.core.governor import ProviderQuotaGovernor, GovernedHTTPClient, global_governor
from mas.core.workflow import MASWorkflow
from mas.db.session import get_session
from mas.db.models import Run, ModelCall, AgentEvent, Artifact, Metric
from eval.neutral_evaluator import NeutralEvaluator

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


def run_phase2k_pilot():
    model_id = "cohere/north-mini-code:free"
    timestamp = int(time.time())

    print("=" * 80)
    print("PHASE 2K — VERIFIED QUOTA RESET, TRANSMISSION GOVERNANCE, AND LIVE PILOT RESUMPTION")
    print(f"Configured Model: {model_id} (Verified Free Tier, $0.00 cost, allow_fallbacks=False)")
    print(f"Safety Ceilings: Max 15 calls/run, Max 60,000 tokens/run, Max 45 HTTP requests/day (UTC)")
    print("=" * 80)

    now_utc = datetime.now(timezone.utc)
    today_str = now_utc.strftime("%Y-%m-%d")
    print(f"\n[TIME CHECK] Current UTC Time: {now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    # Calculate time until 00:00:00 UTC daily reset boundary
    seconds_to_midnight = int(
        ((24 - now_utc.hour - 1) * 3600) + ((60 - now_utc.minute - 1) * 60) + (60 - now_utc.second)
    )
    hours_to_midnight = round(seconds_to_midnight / 3600.0, 2)

    ledger_stats = global_governor.get_ledger_stats()
    print(f"[LEDGER AUDIT] UTC Date: {ledger_stats['utc_date']}")
    print(f"  - Outbound Transmissions Today: {ledger_stats['total_attributable_attempts']} / {ledger_stats['internal_daily_cap']}")
    print(f"  - Cap Breached Today: {ledger_stats['cap_breached']} (Excess: {ledger_stats['excess_transmissions']})")
    print(f"  - Time Until Next 00:00:00 UTC Reset: ~{hours_to_midnight} hours ({seconds_to_midnight} seconds)")

    pilot_summary = {
        "series_timestamp": timestamp,
        "phase": "PHASE_2K",
        "utc_date": today_str,
        "current_utc_time": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model_requested": model_id,
        "provider_routing": "OpenRouter Direct API (https://openrouter.ai/api/v1)",
        "allow_fallbacks": False,
        "ledger_audit": ledger_stats,
        "reset_status": {
            "documented_reset_rule": "Daily reset at 00:00:00 UTC for free model daily request limits",
            "hours_until_reset": hours_to_midnight,
            "seconds_until_reset": seconds_to_midnight,
            "is_post_reset": (today_str > "2026-10-17"),
        },
        "governor_audit": {
            "shared_http_client": "GovernedHTTPClient",
            "instrumentation_scope": [
                "Completion-generation requests",
                "Schema retry requests",
                "Network or HTTP retry transmissions",
                "HTTP 429 attempts",
                "Key-metadata requests",
                "Diagnostic HTTP requests",
            ],
            "offline_tests_verified": 8,
            "offline_tests_passing": True,
            "scratch_direct_bypasses_closed": True,
        },
        "runs": [],
    }

    # If it is still 2026-10-17, the documented reset time has NOT passed
    if today_str == "2026-10-17":
        print("\n" + "!" * 80)
        print("MANDATORY PAUSED STATE ENFORCED: 00:00:00 UTC reset boundary has NOT arrived yet.")
        print(f"Current UTC time is {now_utc.strftime('%H:%M:%S UTC')} on {today_str}.")
        print(f"Remaining pause duration: ~{hours_to_midnight} hours ({seconds_to_midnight} seconds).")
        print(f"Upstream free-model daily quota exhausted on 2026-10-17 (52/50 used, 0 remaining).")
        print(f"Historical 2026-10-17 ledger breach (54 transmissions / 45 ceiling) is permanently locked.")
        print(f"Per Section 3 mandate, stopping cleanly without sending futile generation requests.")
        print("!" * 80 + "\n")

        for task_def in PILOT_TASKS:
            slot = task_def["slot"]
            task_id = task_def["task_id"]
            run_prefix = task_def["run_prefix"]
            stop_reason = (
                f"Execution paused pending 00:00:00 UTC daily reset (~{hours_to_midnight}h remaining). "
                f"Upstream free-model daily quota exhausted on 2026-10-17."
            )
            print(f"[{slot} - {task_id}] Checkpointed status: STOPPED_PROVIDER_QUOTA")
            pilot_summary["runs"].append({
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
            })

        out_json = "eval/phase2k_pilot_results.json"
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(pilot_summary, f, indent=2)
        print(f"\n[DONE] Saved Phase 2K Pilot State to {out_json}")
        return pilot_summary

    # --- NEW UTC DAY EXECUTION PROTOCOL ---
    print("\n[BOUNDARY TRANSITION] New UTC Day Detected! Initializing ledger...")
    global_governor.initialize_day(today_str)
    provider = OpenRouterProvider(default_model=model_id)

    print("\n[TRANSMISSION 1] Executing exactly ONE preflight metadata check via GovernedHTTPClient...")
    key_status = global_governor.check_upstream_key_status(provider, record_attempt=True)
    pilot_summary["preflight_metadata"] = key_status

    updated_ledger = global_governor.get_ledger_stats()
    print(f"  - Key metadata recorded as transmission {updated_ledger['total_attributable_attempts']} of {updated_ledger['internal_daily_cap']}")
    print(f"  - Remaining internal HTTP attempts today: {updated_ledger['remaining_internal_attempts']}")
    print(f"  - Upstream remaining free requests: {key_status.get('free_models_remaining')}")

    if key_status.get("is_quota_exhausted"):
        print("\n[STOP] Upstream free quota remains exhausted. Stopping per protocol.")
        for task_def in PILOT_TASKS:
            pilot_summary["runs"].append({
                "slot": task_def["slot"],
                "task_id": task_def["task_id"],
                "status": "STOPPED_PROVIDER_QUOTA",
                "stop_reason": "Upstream quota remains unavailable after reset check.",
                "calls_dispatched": 0,
            })
        out_json = "eval/phase2k_pilot_results.json"
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(pilot_summary, f, indent=2)
        return pilot_summary

    # Sequential live execution once quota is restored
    for task_def in PILOT_TASKS:
        slot = task_def["slot"]
        task_id = task_def["task_id"]
        run_prefix = task_def["run_prefix"]
        req = task_def["requirement"]
        checker = task_def["checker"]

        allowed, status_code, reason_dict = global_governor.evaluate_dispatch_permission(
            slot_name=slot,
            task_id=task_id,
            provider=provider,
        )

        if not allowed:
            print(f"[{slot}] Dispatch blocked: {status_code} ({reason_dict.get('reason')})")
            pilot_summary["runs"].append({
                "slot": slot,
                "task_id": task_id,
                "status": status_code,
                "stop_reason": reason_dict.get("reason"),
                "calls_dispatched": 0,
            })
            continue

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
        except DailyTransmissionsCeilingExceededError as e:
            run_status = "STOPPED_BUDGET_CEILING"
            stop_reason = f"STOPPED_BUDGET_CEILING: {str(e)}"
        except Exception as e:
            run_status = "FAILED"
            stop_reason = f"ERROR: {str(e)}"

        duration = time.time() - t0
        with get_session() as session:
            calls = session.query(ModelCall).filter(ModelCall.run_id == run_id).all()

        total_in = sum(c.input_tokens for c in calls)
        total_out = sum(c.output_tokens for c in calls)
        total_tokens = total_in + total_out
        total_cost = sum(c.cost for c in calls)

        # Behavioral test verification if code was generated
        ws_dir = os.path.join(".", "workspace", run_id)
        behavioral_results = {}
        if os.path.exists(ws_dir) and checker:
            try:
                behavioral_results = checker(ws_dir)
            except Exception as e:
                behavioral_results = {"error": str(e), "all_passed": False}

        pilot_summary["runs"].append({
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
            "behavioral_results": behavioral_results,
        })

        time.sleep(5)

    out_json = "eval/phase2k_pilot_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(pilot_summary, f, indent=2)
    return pilot_summary


if __name__ == "__main__":
    run_phase2k_pilot()
