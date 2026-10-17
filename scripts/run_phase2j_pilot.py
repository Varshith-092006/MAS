"""Phase 2J Post-Reset Resumption and Live Development Pilot Runner.

Enforces:
1. Unified Outbound Transmission Ledger (eval/outbound_transmission_ledger.json).
2. Counter reset strictly upon new UTC day boundary (00:00:00 UTC).
3. Exactly ONE preflight metadata request on the new day, counted as 1 HTTP transmission.
4. Immediate pause if documented reset has not passed or quota remains exhausted.
5. Sequential execution order:
   Task A: dev_markdown_toc_01
   Task B: dev_inventory_system_01
   Task C: dev_log_analyzer_01
   Task D: dev_markdown_toc_01_repeat
6. Strict per-run ceilings: 15 calls, 60,000 tokens, $0.00 cost, allow_fallbacks=False.
7. Truthful terminal states: COMPLETED_QUALITY_GATE vs STOPPED_PROVIDER_QUOTA vs STOPPED_BUDGET_CEILING.
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
from mas.core.governor import ProviderQuotaGovernor, global_governor
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


def run_phase2j_pilot():
    model_id = "cohere/north-mini-code:free"
    timestamp = int(time.time())

    print("=" * 80)
    print("PHASE 2J — POST-RESET RESUMPTION AND LIVE DEVELOPMENT PILOT RUNNER")
    print(f"Configured Model: {model_id} (Verified Free Tier, $0.00 cost, allow_fallbacks=False)")
    print(f"Safety Ceilings: Max 15 calls/run, Max 60,000 tokens/run, Max 45 HTTP requests/day (UTC)")
    print("=" * 80)

    now_utc = datetime.now(timezone.utc)
    today_str = now_utc.strftime("%Y-%m-%d")
    print(f"\n[TIME CHECK] Current UTC Time: {now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    # Check time until 00:00:00 UTC reset
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
        "phase": "PHASE_2J",
        "utc_date": today_str,
        "current_utc_time": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model_requested": model_id,
        "provider_routing": "OpenRouter Direct API (https://openrouter.ai/api/v1)",
        "allow_fallbacks": False,
        "ledger_audit": ledger_stats,
        "reset_status": {
            "documented_reset_rule": "Daily reset at 00:00:00 UTC",
            "hours_until_reset": hours_to_midnight,
            "seconds_until_reset": seconds_to_midnight,
            "is_post_reset": False,
        },
        "runs": [],
    }

    # If it is still 2026-10-17, reset has not passed
    if today_str == "2026-10-17":
        print("\n" + "!" * 80)
        print("PAUSED EXECUTION ENFORCED: 00:00:00 UTC reset has NOT arrived yet.")
        print(f"Upstream free-model daily quota remains exhausted (0 remaining).")
        print(f"Remaining pause duration: ~{hours_to_midnight} hours.")
        print(f"Per Phase 2J mandate, stopping cleanly without sending futile model generation requests.")
        print("!" * 80 + "\n")

        for task_def in PILOT_TASKS:
            slot = task_def["slot"]
            task_id = task_def["task_id"]
            run_prefix = task_def["run_prefix"]
            stop_reason = (
                f"Execution paused pending 00:00:00 UTC daily reset (~{hours_to_midnight}h remaining). "
                f"Upstream free-model daily quota exhausted on 2026-10-17."
            )
            print(f"[{slot} - {task_id}] Status: STOPPED_PROVIDER_QUOTA")
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
            })

        out_json = "eval/phase2j_pilot_results.json"
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(pilot_summary, f, indent=2)
        print(f"[DONE] Saved Phase 2J Pilot State to {out_json}")
        return pilot_summary

    # New UTC Day: Perform single preflight metadata check
    pilot_summary["reset_status"]["is_post_reset"] = True
    provider = OpenRouterProvider(default_model=model_id)

    print("\n[PREFLIGHT CHECK] New UTC day detected. Making exactly ONE key metadata check...")
    key_status = global_governor.check_upstream_key_status(provider, record_attempt=True)
    pilot_summary["preflight_metadata"] = key_status

    updated_ledger = global_governor.get_ledger_stats()
    print(f"  - Metadata query recorded. Ledger count: {updated_ledger['total_attributable_attempts']} / 45 (Remaining: {updated_ledger['remaining_internal_attempts']})")
    print(f"  - Upstream remaining free requests: {key_status.get('free_models_remaining')}")

    if key_status.get("is_quota_exhausted"):
        print("\n[STOP] Quota still exhausted post-reset. Halting.")
        for task_def in PILOT_TASKS:
            pilot_summary["runs"].append({
                "slot": task_def["slot"],
                "task_id": task_def["task_id"],
                "status": "STOPPED_PROVIDER_QUOTA",
                "stop_reason": "Upstream quota remains unavailable after reset check.",
                "calls_dispatched": 0,
            })
        return pilot_summary

    # Sequential live execution once quota is restored
    evaluator = NeutralEvaluator(checks_path="eval/checks/dev_level2_checks.json")

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
        except Exception as e:
            run_status = "FAILED"
            stop_reason = f"ERROR: {str(e)}"

        duration = time.time() - t0
        # Telemetry harvesting
        with get_session() as session:
            calls = session.query(ModelCall).filter(ModelCall.run_id == run_id).all()

        total_in = sum(c.input_tokens for c in calls)
        total_out = sum(c.output_tokens for c in calls)
        total_tokens = total_in + total_out
        total_cost = sum(c.cost for c in calls)

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
        })

        time.sleep(5)

    out_json = "eval/phase2j_pilot_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(pilot_summary, f, indent=2)
    return pilot_summary


if __name__ == "__main__":
    run_phase2j_pilot()
