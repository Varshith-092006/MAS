"""Phase 2E MAS End-to-End Development Pilot Execution Script.

Executes the real MAS multi-agent orchestration workflow against verified free model
cohere/north-mini-code:free on the non-confirmatory task dev_csv_sales_01.
"""

import os
import sys
import json
import time
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()

from mas.core.llm import OpenRouterProvider, token_logger
from mas.core.workflow import MASWorkflow
from mas.db.session import get_session
from mas.db.models import Run, ModelCall, AgentEvent, Artifact, Metric
from eval.checks.test_dev_csv_sales_01 import run_neutral_test
from eval.neutral_evaluator import NeutralEvaluator


def execute_phase2e_pilot():
    model_id = "cohere/north-mini-code:free"
    run_id = f"mas_dev_csv_sales_{int(time.time())}"
    task_id = "dev_csv_sales_01"

    requirement = (
        "CSV Sales Summary CLI: Read a CSV file containing product name, quantity, and unit price. "
        "Validate required columns and numeric inputs. "
        "Compute per-product revenue (quantity * unit_price) and total revenue correctly. "
        "Handle an empty CSV cleanly without crashing. "
        "Handle malformed rows without silently inventing data. "
        "Provide a usable command-line entry point in main.py. "
        "Include automated behavioral tests in test_main.py for normal and failure cases. "
        "Use the Python standard library."
    )

    print("=" * 80)
    print(f"STARTING PHASE 2E DEVELOPMENT PILOT RUN: {run_id}")
    print(f"Task ID: {task_id}")
    print(f"Model ID: {model_id}")
    print("=" * 80)

    # 1. Initialize real OpenRouterProvider with strict zero-cost model
    provider = OpenRouterProvider(default_model=model_id)

    # 2. Initialize real MASWorkflow
    workflow = MASWorkflow(llm=provider)

    t0 = time.time()
    try:
        final_state = workflow.run(
            requirement=requirement,
            task_id=task_id,
            model_name=model_id,
            run_id=run_id,
            workspace_base="./workspace",
        )
        duration_total = time.time() - t0
        print(f"\n[WORKFLOW RUN FINISHED] Status: {final_state.get('status')} in {duration_total:.2f}s")
    except Exception as e:
        duration_total = time.time() - t0
        print(f"\n[WORKFLOW RUN EXCEPTION] {type(e).__name__}: {e}")
        final_state = {"status": "FAILED", "run_id": run_id, "workspace_path": f"./workspace/{run_id}"}

    workspace_path = final_state.get("workspace_path", f"./workspace/{run_id}")

    # 3. Harvest Model Calls Telemetry
    print("\n" + "=" * 80)
    print("HARVESTING DETAILED MODEL CALL TELEMETRY FROM DATABASE")
    print("=" * 80)

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
            .order_by(Artifact.artifact_id.asc())
            .all()
        )
        metrics = (
            session.query(Metric)
            .filter(Metric.run_id == run_id)
            .all()
        )

    total_in = sum(c.input_tokens for c in calls)
    total_out = sum(c.output_tokens for c in calls)
    total_cost = sum(c.cost for c in calls)

    print(f"Total Dispatched LLM Calls: {len(calls)}")
    print(f"Total Input Tokens: {total_in}")
    print(f"Total Output Tokens: {total_out}")
    print(f"Total Tokens: {total_in + total_out}")
    print(f"Total Verified Cost: ${total_cost:.6f}")

    call_records = []
    for idx, c in enumerate(calls, 1):
        raw_meta = c.raw_metadata or {}
        usage = raw_meta.get("usage", {})
        ct_details = usage.get("completion_tokens_details", {}) if isinstance(usage, dict) else {}
        reasoning_tokens = ct_details.get("reasoning_tokens", 0)
        visible_tokens = max(0, c.output_tokens - reasoning_tokens)

        rec = {
            "index": idx,
            "agent": c.agent,
            "requested_model": c.requested_model,
            "actual_model": c.actual_model,
            "request_id": c.request_id,
            "cost": c.cost,
            "prompt_tokens": c.input_tokens,
            "completion_tokens": c.output_tokens,
            "reasoning_tokens": reasoning_tokens,
            "visible_tokens": visible_tokens,
            "total_tokens": c.total_tokens,
        }
        call_records.append(rec)
        print(
            f"Call #{idx} [{c.agent.upper():9}]: {c.actual_model} | "
            f"Prompt: {c.input_tokens:4} | Visible: {visible_tokens:4} | "
            f"Reasoning: {reasoning_tokens:4} | Cost: ${c.cost:.6f} | "
            f"ReqID: {c.request_id}"
        )

    # 4. Agent Event Audit
    print("\n" + "=" * 80)
    print("AGENT EVENT SEQUENCE")
    print("=" * 80)
    for ev in events:
        print(f"[{ev.seq:2}] {ev.agent:9} -> {ev.event:20} | Status: {ev.status} | {ev.redacted_summary or ''}")

    # 5. Generated Workspace Files Audit
    print("\n" + "=" * 80)
    print("GENERATED WORKSPACE ARTIFACTS")
    print("=" * 80)
    workspace_files = {}
    if os.path.exists(workspace_path):
        for root, _, files in os.walk(workspace_path):
            if any(x in root for x in [".git", "__pycache__", ".mas_snapshots"]):
                continue
            for fn in files:
                fpath = os.path.join(root, fn)
                rel_p = os.path.relpath(fpath, workspace_path).replace("\\", "/")
                try:
                    with open(fpath, "r", encoding="utf-8") as fh:
                        content = fh.read()
                        workspace_files[rel_p] = content
                        print(f"- {rel_p} ({len(content)} chars)")
                except Exception as e:
                    print(f"- {rel_p} (read error: {e})")

    # 6. Independent Level 2 Behavioral Testing
    print("\n" + "=" * 80)
    print("INDEPENDENT LEVEL 2 BEHAVIORAL VERIFICATION")
    print("=" * 80)
    behavioral_results = run_neutral_test(workspace_path)
    print(f"Pass Rate: {behavioral_results.get('pass_rate')}")
    print(f"All Assertions Passed: {behavioral_results.get('all_passed')}")
    print("Assertion Details:")
    for k, v in behavioral_results.get("assertions", {}).items():
        print(f"  - {k}: {'PASS' if v else 'FAIL'}")
    print("Execution Logs:")
    for l in behavioral_results.get("logs", []):
        print(f"  {l}")

    # 7. Neutral Evaluator v1.2 Scoring
    print("\n" + "=" * 80)
    print("NEUTRAL EVALUATOR AUDIT")
    print("=" * 80)
    evaluator = NeutralEvaluator()
    eval_metrics = evaluator.evaluate_project(
        workspace_path=workspace_path,
        requirement=requirement,
        persist_to_db=False,
    )
    print(f"Evaluator Version: {eval_metrics.get('evaluator_version')}")
    print(f"Completeness (C): {eval_metrics.get('completeness')}")
    print(f"Executability (E): {eval_metrics.get('executability')}")
    print(f"Consistency (S): {eval_metrics.get('consistency')}")
    print(f"Quality Score (Q = C*E*S): {eval_metrics.get('quality')}")
    print(f"Shared Smoke: {eval_metrics.get('shared_test')}")

    # 8. Save Detailed Audit Package
    summary_report = {
        "run_id": run_id,
        "task_id": task_id,
        "model_id": model_id,
        "duration_seconds": round(duration_total, 2),
        "status": final_state.get("status"),
        "complexity": final_state.get("complexity"),
        "complexity_score": final_state.get("complexity_score"),
        "total_calls": len(calls),
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "total_cost": total_cost,
        "calls": call_records,
        "workspace_files": list(workspace_files.keys()),
        "behavioral_results": behavioral_results,
        "neutral_evaluation": eval_metrics,
    }

    audit_out_path = f"scratch/phase2e_pilot_audit_{run_id}.json"
    os.makedirs("scratch", exist_ok=True)
    with open(audit_out_path, "w", encoding="utf-8") as fh:
        json.dump(summary_report, fh, indent=2)

    print(f"\n[PILOT AUDIT SAVED] Audit data written to: {audit_out_path}")
    return summary_report


if __name__ == "__main__":
    execute_phase2e_pilot()
