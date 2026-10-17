"""Phase 2G Multi-Task Development Pilot Series and Generalization Validation Runner.

Executes a 4-run pilot series on the verified free model cohere/north-mini-code:free:
  - Task A (SIMPLE path): dev_markdown_toc_01
  - Task B (STRUCTURED path, invoking real ArchitectAgent): dev_inventory_system_01
  - Task C (Data-Processing path): dev_log_analyzer_01
  - Task D (Repeat of Task A for consistency assessment): dev_markdown_toc_01_repeat

Strictly enforces:
  - Max 15 logical calls per run
  - Max 45 outbound HTTP transmissions per UTC day (including all previous runs)
  - Max 60,000 provider-reported tokens per run
  - Zero cost on cohere/north-mini-code:free (allow_fallbacks=False)
  - Safe checkpointing on quota ceiling without tight retry loops
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
        "slot": "Task D (Repeat of Task A)",
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


def count_today_http_transmissions() -> int:
    """Queries total model calls recorded for the current UTC day."""
    with get_session() as session:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return (
            session.query(ModelCall)
            .join(Run, ModelCall.run_id == Run.run_id)
            .filter(Run.started_at >= today_start)
            .count()
        )


def run_phase2g_pilot_series():
    model_id = "cohere/north-mini-code:free"
    timestamp = int(time.time())

    print("=" * 80)
    print("PHASE 2G — MULTI-TASK DEVELOPMENT PILOT SERIES STARTING")
    print(f"Model: {model_id} (Verified Free Tier, $0 cost, allow_fallbacks=False)")
    print(f"Ceilings: Max 15 calls/run, Max 60,000 tokens/run, Max 45 HTTP requests/day (UTC)")
    print("=" * 80)

    pilot_summary = {
        "series_timestamp": timestamp,
        "model_requested": model_id,
        "runs": [],
        "budget_limits": {
            "max_calls_per_run": 15,
            "max_tokens_per_run": 60000,
            "max_daily_transmissions": 45,
            "max_pilot_runs": 4,
        },
    }

    evaluator = NeutralEvaluator(checks_path="eval/checks/dev_level2_checks.json")

    for task_def in PILOT_TASKS:
        slot = task_def["slot"]
        task_id = task_def["task_id"]
        run_prefix = task_def["run_prefix"]
        req = task_def["requirement"]
        checker = task_def["checker"]

        current_http = count_today_http_transmissions()
        print(f"\n[{slot}] Checking daily budget before launch: {current_http} / 45 transmissions used today (UTC).")

        if current_http >= 45:
            print(f"[{slot}] ABORTING RUN: Daily transmission cap of 45 reached ({current_http} used). Preserving quota.")
            pilot_summary["runs"].append({
                "slot": slot,
                "task_id": task_id,
                "status": "STOPPED_DAILY_QUOTA_CEILING",
                "failure_reason": f"Daily transmission ceiling of 45 reached ({current_http} / 45 used).",
                "calls_dispatched": 0,
            })
            continue

        run_id = f"{run_prefix}_{int(time.time())}"
        print("-" * 80)
        print(f"STARTING RUN: {run_id} ({slot} - {task_id})")
        print(f"Path Expectation: {task_def['path_type']}")
        print("-" * 80)

        provider = OpenRouterProvider(default_model=model_id)
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
            run_status = final_state.get("status", "COMPLETED")
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
            err_type = "RATE_LIMIT_429" if e.status_code == 429 else f"OPENROUTER_ERROR_{e.status_code}"
            run_status = "STOPPED_BUDGET_CEILING" if e.status_code == 429 else "FAILED"
            stop_reason = f"{err_type}: {e.error_message or str(e)}"
            print(f"Run halted on provider error ({err_type}): {stop_reason} in {duration:.2f}s")
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
            events = (
                session.query(AgentEvent)
                .filter(AgentEvent.run_id == run_id)
                .order_by(AgentEvent.seq.asc())
                .all()
            )
            artifacts = (
                session.query(Artifact)
                .filter(Artifact.run_id == run_id)
                .all()
            )
            db_run = session.query(Run).filter(Run.run_id == run_id).first()

        total_in = sum(c.input_tokens for c in calls)
        total_out = sum(c.output_tokens for c in calls)
        total_tokens = total_in + total_out
        total_cost = sum(c.cost for c in calls)

        # Separate reasoning tokens from raw metadata
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

        print(f"\n[TELEMETRY] Calls: {len(calls)}, In: {total_in}, Out: {total_out}, Total: {total_tokens}, Reasoning: {total_reasoning}, Cost: ${total_cost:.6f}")

        # Run Neutral Evaluator v1.3
        eval_res = {}
        if os.path.exists(workspace_path):
            try:
                eval_res = evaluator.evaluate_project(
                    workspace_path=workspace_path,
                    requirement=req,
                    task_id=task_id,
                    run_id=run_id,
                    persist_to_db=True,
                )
                print(f"[NEUTRAL EVALUATOR] Completeness: {eval_res.get('completeness')}, Executability: {eval_res.get('executability')}, Consistency: {eval_res.get('consistency')}, Quality: {eval_res.get('quality')}")
            except Exception as ex:
                print(f"[NEUTRAL EVALUATOR ERROR] {ex}")

        # Run independent Level 2 behavioral checks
        l2_res = {}
        if os.path.exists(workspace_path):
            try:
                l2_res = checker(workspace_path)
                print(f"[LEVEL 2 BEHAVIORAL] Pass Rate: {l2_res.get('pass_rate')} ({l2_res.get('passed_assertions')}/{l2_res.get('total_assertions')} assertions passed)")
            except Exception as ex:
                print(f"[LEVEL 2 CHECKER ERROR] {ex}")

        # Inspect Reviewer report from state or artifacts
        rev_findings = final_state.get("review_report", {}).get("findings", [])
        rev_crit = final_state.get("review_report", {}).get("critical_issues", 0)
        rev_maj = final_state.get("review_report", {}).get("major_issues", 0)
        rev_min = final_state.get("review_report", {}).get("minor_issues", 0)
        rev_status = final_state.get("review_report", {}).get("status", "UNKNOWN")

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
            "reviewer_status": rev_status,
            "reviewer_critical": rev_crit,
            "reviewer_major": rev_maj,
            "reviewer_minor": rev_min,
            "reviewer_findings": rev_findings,
            "evaluator_scores": {
                "completeness": eval_res.get("completeness", 0.0),
                "executability": eval_res.get("executability", 0.0),
                "consistency": eval_res.get("consistency", 0.0),
                "quality": eval_res.get("quality", 0.0),
                "version": eval_res.get("evaluator_version", "v1.3"),
            },
            "level2_behavioral": {
                "all_passed": l2_res.get("all_passed", False),
                "pass_rate": l2_res.get("pass_rate", 0.0),
                "passed_assertions": l2_res.get("passed_assertions", 0),
                "total_assertions": l2_res.get("total_assertions", 0),
                "assertions": l2_res.get("assertions", {}),
            },
        }

        pilot_summary["runs"].append(run_record)

        # Inter-run safety delay (5s) to prevent bursting and honor rate limits
        print("\nWaiting 5 seconds before next task...")
        time.sleep(5)

    # Save summary report
    out_json = "eval/phase2g_pilot_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(pilot_summary, f, indent=2)
    print(f"\n[DONE] Saved Phase 2G Pilot Results to {out_json}")
    return pilot_summary


if __name__ == "__main__":
    run_phase2g_pilot_series()
