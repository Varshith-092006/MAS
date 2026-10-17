"""Execute fair matched research benchmark on canonical SRDD Task 1 (srdd_educ_01) for MAS and ChatDev.

This script enforces:
1. Canonical task identity from eval/tasks.json (Science Question Solver)
2. Byte-for-byte identical requirement string to both MAS and ChatDev
3. Unified software generation contract (Python 3.11+, main.py entry point)
4. Symmetric evaluator protocol (NeutralEvaluator with fixed assertions)
5. Zero simulation / zero mock fallback (LIVE_API with provider-reported usage)
6. Preserves historical pilot runs as diagnostic evidence.
"""

import hashlib
import json
import os
import sys
import threading
import time
from datetime import datetime

sys.path.insert(0, os.path.abspath("."))
from dotenv import load_dotenv
load_dotenv()
os.environ["MAS_ALLOW_SUBPROCESS_SANDBOX"] = "1"
os.environ["MAS_STAGE_MAX_SPEND"] = "1.00"

import uvicorn
from eval.chatdev_adapter import ChatDevAdapter
from eval.neutral_evaluator import NeutralEvaluator
from eval.checks.test_srdd_educ_01 import run_neutral_test
from mas.core.llm import OpenRouterProvider, token_logger
from mas.core.proxy import proxy_app
from mas.core.workflow import MASWorkflow, generate_artifacts_manifest
from mas.db.models import Evaluation, Metric, ModelCall, Run
from mas.db.session import get_session, init_db


def start_proxy_daemon(port: int = 8089):
    """Starts local logging proxy in a daemon thread if not already running."""
    import requests
    try:
        r = requests.get(f"http://127.0.0.1:{port}/health", timeout=1)
        if r.status_code == 200:
            print(f"[Proxy] Using active logging proxy on port {port}")
            return
    except Exception:
        pass

    def _serve():
        uvicorn.run(proxy_app, host="127.0.0.1", port=port, log_level="warning")

    t = threading.Thread(target=_serve, daemon=True)
    t.start()
    time.sleep(1.5)
    print(f"[Proxy] Started logging proxy daemon on http://127.0.0.1:{port}/v1")


def main():
    print("=" * 80)
    print("FAIR MATCHED BENCHMARK RERUN: CANONICAL TASK srdd_educ_01")
    print("=" * 80)

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("[ERROR] OPENROUTER_API_KEY not configured.")
        sys.exit(1)

    # 1. Load canonical task from verified dataset
    tasks_file = "eval/tasks.json"
    with open(tasks_file, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    task = tasks[0]
    task_id = task["task_id"]
    task_name = task["name"]
    category = task["category"]
    subcategory = task.get("subcategory", "Science")
    req = task["description"]

    # Verify task identity and requirement checksum
    expected_req_sha = "15b83bd79330fcf4a79de4ad9cbc725ffeba2a695f1b76bf4d1ca567c4740012"
    actual_req_sha = hashlib.sha256(req.encode("utf-8")).hexdigest()

    assert task_id == "srdd_educ_01", f"Task ID mismatch: {task_id}"
    assert task_name == "Science Question Solver", f"Task name mismatch: {task_name}"
    assert actual_req_sha == expected_req_sha, f"Requirement checksum mismatch: {actual_req_sha}"

    model = "openai/gpt-4o"
    eval_id = f"eval_canonical_{int(time.time())}"

    print(f"Task ID:          {task_id}")
    print(f"Task Name:        {task_name}")
    print(f"Category:         {category} ({subcategory})")
    print(f"Requirement:      {req}")
    print(f"Req Checksum:     SHA-256:{actual_req_sha}")
    print(f"Model Condition:  {model}")
    print(f"Evaluation ID:    {eval_id}")
    print("=" * 80)

    init_db()

    # 2. Mark old pilot runs as diagnostic in database without deleting them
    with get_session() as session:
        for old_run_id in ["mas_srdd_educ_01_live", "cd_srdd_educ_01_live"]:
            old_run = session.query(Run).filter(Run.run_id == old_run_id).first()
            if old_run:
                old_run.failure_reason = (
                    "DIAGNOSTIC_RUN: Dataset integrity limitation (used unaligned QuickStudy prompt "
                    "instead of canonical Science Question Solver); retained for historical audit."
                )
        session.commit()

    # Create new evaluation record
    with get_session() as session:
        session.add(Evaluation(
            evaluation_id=eval_id,
            benchmark="srdd20_canonical",
            repeat_no=1,
            ablation="A0",
        ))
        session.commit()

    # Spending limit configuration for Stage 1
    MAX_STAGE_BUDGET = 1.00  # Hard authorization limit: US$1.00 total across both runs
    cumulative_spend = 0.0

    # Start logging proxy for ChatDev
    proxy_port = 8089
    start_proxy_daemon(port=proxy_port)

    llm = OpenRouterProvider(api_key=api_key, default_model=model)
    evaluator = NeutralEvaluator()

    # -------------------------------------------------------------------------
    # 3. RUN MAS (Canonical Task)
    # -------------------------------------------------------------------------
    mas_run_id = f"mas_{task_id}_canonical"
    mas_ws = os.path.abspath(f"./eval/workspaces/{mas_run_id}")
    print(f"\n[MAS] Starting execution: {mas_run_id} -> {mas_ws}")

    t0 = time.time()
    mas_workflow = MASWorkflow(llm=llm)
    try:
        mas_state = mas_workflow.run(
            requirement=req,
            task_id=task_id,
            model_name=model,
            run_id=mas_run_id,
            workspace_base="./eval/workspaces",
        )
        mas_dur = time.time() - t0
        mas_status = mas_state.get('status', 'FAILED')
        print(f"[MAS] Generation completed in {mas_dur:.2f}s (Status: {mas_status})")

        # Evaluate MAS with neutral evaluator
        mas_metrics = evaluator.evaluate_project(
            workspace_path=mas_state["workspace_path"],
            requirement=req,
            task_id=task_id,
            run_id=mas_run_id,
            persist_to_db=True,
        )
        mas_totals = token_logger.get_run_totals(mas_run_id)
        mas_cost = mas_totals.get("estimated_cost") or 0.0
        cumulative_spend += mas_cost

        print(f"[MAS] Total Tokens: {mas_totals['total_tokens']}, Incurred Cost: ${mas_cost:.6f}")
        print(f"[Stage 1 Budget] Cumulative Spend: ${cumulative_spend:.6f} / Limit: ${MAX_STAGE_BUDGET:.2f}")

        # Run Level 2 Fixed Neutral Test Suite
        mas_neutral_results = run_neutral_test(mas_state["workspace_path"])
    except Exception as e:
        mas_dur = time.time() - t0
        mas_status = "FAILED"
        print(f"\n[MAS ERROR] Generation halted with error: {e}")
        mas_state = {
            "status": "FAILED",
            "stop_reason": str(e),
            "workspace_path": mas_ws,
        }
        mas_metrics = {
            "completeness": None,
            "executability": None,
            "consistency": None,
            "quality": None,
            "shared_test": None,
        }
        mas_totals = token_logger.get_run_totals(mas_run_id)
        if mas_totals.get("call_count", 0) == 0:
            mas_totals["total_tokens"] = None
            mas_totals["input_tokens"] = None
            mas_totals["output_tokens"] = None
            mas_totals["token_provenance"] = "UNAVAILABLE"
        mas_cost = mas_totals.get("estimated_cost") or 0.0
        cumulative_spend += mas_cost
        mas_neutral_results = {
            "all_passed": False,
            "passed": 0,
            "total": 0,
            "details": [f"MAS execution halted with error: {str(e)}"],
        }

    with get_session() as session:
        r = session.query(Run).filter(Run.run_id == mas_run_id).first()
        if r:
            r.evaluation_id = eval_id
            session.commit()

    # Mandatory Check: Stop if MAS encountered a provider or model-integrity failure
    if mas_status != "COMPLETED":
        print(f"\n[HALT] MAS Run A failed (status: {mas_status}, stop_reason: {mas_state.get('stop_reason')}).")
        print("[HALT] Per Stage 1 protocol, stopping immediately before ChatDev execution.")
        cd_out = {"workspace_dir": ""}
        cd_metrics = {
            "completeness": None,
            "executability": None,
            "consistency": None,
            "quality": None,
            "shared_test": None,
        }
        cd_totals = {
            "total_tokens": None,
            "input_tokens": None,
            "output_tokens": None,
            "estimated_cost": 0.0,
            "call_count": 0,
            "token_provenance": "UNAVAILABLE",
        }
        cd_skip_reason = "Skipped: Stage 1 stopped after MAS Run A failure"
        cd_neutral_results = {"all_passed": False, "passed": 0, "total": 0, "details": [cd_skip_reason]}
        cd_run_id = "SKIPPED_DUE_TO_MAS_FAILURE"
        cd_status = "SKIPPED"
        cd_dur = 0.0

        with get_session() as session:
            cd_row = session.query(Run).filter(Run.run_id == cd_run_id).first()
            if not cd_row:
                session.add(Run(
                    run_id=cd_run_id,
                    task_id=task_id,
                    evaluation_id=eval_id,
                    system="chatdev",
                    model=model,
                    actual_model=model,
                    execution_mode="SKIPPED",
                    status="SKIPPED",
                    failure_reason=None,
                    skip_reason=cd_skip_reason,
                    token_provenance="UNAVAILABLE",
                    total_tokens=0,
                    input_tokens=0,
                    output_tokens=0,
                    estimated_cost=0.0,
                    artifacts_manifest="[]",
                    started_at=datetime.utcnow(),
                    finished_at=datetime.utcnow(),
                ))
            else:
                cd_row.status = "SKIPPED"
                cd_row.execution_mode = "SKIPPED"
                cd_row.failure_reason = None
                cd_row.skip_reason = cd_skip_reason
            session.commit()
    else:
        # Check budget before executing ChatDev
        projected_cd_cost = 0.20
        if cumulative_spend + projected_cd_cost > MAX_STAGE_BUDGET:
            print(f"\n[HALT] Projected ChatDev cost (${projected_cd_cost:.2f}) would exceed Stage 1 spending limit (${MAX_STAGE_BUDGET:.2f}). Current spend: ${cumulative_spend:.4f}.")
            print("[HALT] Stopping before ChatDev execution to enforce US$1.00 budget cap.")
            cd_out = {"workspace_dir": ""}
            cd_metrics = {"completeness": 0.0, "executability": 0.0, "consistency": 0.0, "quality": 0.0, "shared_test": 0.0}
            cd_totals = {"total_tokens": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost": 0.0}
            cd_neutral_results = {"all_passed": False, "passed": 0, "total": 0, "details": ["Skipped due to budget limit"]}
            cd_run_id = "SKIPPED_DUE_TO_BUDGET_LIMIT"
            cd_dur = 0.0
        else:
            # -------------------------------------------------------------------------
            # 4. RUN CHATDEV (Canonical Task)
            # -------------------------------------------------------------------------
            cd_run_id = f"cd_{task_id}_canonical"
            cd_ws = os.path.abspath(f"./eval/workspaces/{cd_run_id}")
            print(f"\n[ChatDev] Starting execution: {cd_run_id} -> {cd_ws}")

            t0 = time.time()
            cd_adapter = ChatDevAdapter(
                proxy_url=f"http://127.0.0.1:{proxy_port}/v1",
                llm=llm,
            )
            cd_out = cd_adapter.run_task(
                task=task,
                output_base_dir="./eval/workspaces",
                model=model,
                run_id=cd_run_id,
                use_fake=False,
            )
            cd_dur = time.time() - t0
            print(f"[ChatDev] Generation completed in {cd_dur:.2f}s")

            # Evaluate ChatDev with neutral evaluator
            cd_metrics = evaluator.evaluate_project(
                workspace_path=cd_out["workspace_dir"],
                requirement=req,
                task_id=task_id,
                run_id=cd_run_id,
                persist_to_db=True,
            )
            cd_totals = token_logger.get_run_totals(cd_run_id)
            cd_cost = cd_totals.get("estimated_cost") or 0.0
            cumulative_spend += cd_cost

            # Run Level 2 Fixed Neutral Test Suite
            cd_neutral_results = run_neutral_test(cd_out["workspace_dir"])

            # Persist ChatDev run record
            cd_manifest = generate_artifacts_manifest(cd_out["workspace_dir"])
            with get_session() as session:
                cd_row = session.query(Run).filter(Run.run_id == cd_run_id).first()
                if not cd_row:
                    session.add(Run(
                        run_id=cd_run_id,
                        task_id=task_id,
                        evaluation_id=eval_id,
                        system="chatdev",
                        model=model,
                        actual_model=model,
                        execution_mode="LIVE_API",
                        token_provenance="PROVIDER_REPORTED" if cd_totals["total_tokens"] > 0 else "UNAVAILABLE",
                        workspace_path=cd_out["workspace_dir"],
                        artifacts_manifest=json.dumps(cd_manifest),
                        total_tokens=cd_totals["total_tokens"],
                        input_tokens=cd_totals["input_tokens"],
                        output_tokens=cd_totals["output_tokens"],
                        estimated_cost=cd_totals["estimated_cost"],
                        sandbox_status="SUCCESS" if cd_metrics["executability"] > 0 else "FAILED",
                        status="COMPLETED" if (cd_totals["total_tokens"] > 0 and len(cd_manifest) > 0) else "FAILED",
                        started_at=datetime.utcnow(),
                        finished_at=datetime.utcnow(),
                    ))
                else:
                    cd_row.evaluation_id = eval_id
                    cd_row.status = "COMPLETED" if (cd_totals["total_tokens"] > 0 and len(cd_manifest) > 0) else "FAILED"
                    cd_row.execution_mode = "LIVE_API"
                    cd_row.total_tokens = cd_totals["total_tokens"]
                    cd_row.estimated_cost = cd_totals["estimated_cost"]
                session.commit()

    # -------------------------------------------------------------------------
    # 5. RECONCILIATION & REPORTING
    # -------------------------------------------------------------------------
    mas_q1k = round(mas_metrics["quality"] / (mas_totals["total_tokens"] / 1000), 4) if (mas_metrics.get("quality") is not None and mas_totals.get("total_tokens")) else None
    cd_q1k = round(cd_metrics["quality"] / (cd_totals["total_tokens"] / 1000), 4) if (cd_metrics.get("quality") is not None and cd_totals.get("total_tokens")) else None

    fmt_metric = lambda v: f"{v:<22.4f}" if v is not None else f"{'N/A':<22}"
    fmt_tok = lambda v: f"{v:<22}" if v is not None else f"{'UNAVAILABLE':<22}"
    fmt_q1k = lambda v: f"{v:<22}" if v is not None else f"{'N/A':<22}"

    print("\n" + "=" * 80)
    print("CANONICAL MATCHED LIVE COMPARISON RESULTS")
    print("=" * 80)
    print(f"{'Metric / Parameter':<30} | {'MAS Architecture':<22} | {'ChatDev Baseline':<22}")
    print("-" * 80)
    print(f"{'Run ID':<30} | {mas_run_id:<22} | {cd_run_id:<22}")
    print(f"{'Task ID':<30} | {task_id:<22} | {task_id:<22}")
    print(f"{'Requirement SHA-256':<30} | {actual_req_sha[:16]}... | {actual_req_sha[:16]}...")
    print(f"{'Requested Model':<30} | {model:<22} | {model:<22}")
    cd_exec_mode = "LIVE_API" if cd_status == "COMPLETED" else "SKIPPED"
    print(f"{'Run Status':<30} | {mas_status:<22} | {cd_status:<22}")
    print(f"{'Execution Mode':<30} | {'LIVE_API':<22} | {cd_exec_mode:<22}")
    print(f"{'Total Provider Tokens':<30} | {fmt_tok(mas_totals['total_tokens'])} | {fmt_tok(cd_totals['total_tokens'])}")
    print(f"{'Input Tokens':<30} | {fmt_tok(mas_totals['input_tokens'])} | {fmt_tok(cd_totals['input_tokens'])}")
    print(f"{'Output Tokens':<30} | {fmt_tok(mas_totals['output_tokens'])} | {fmt_tok(cd_totals['output_tokens'])}")
    mas_c_disp = f"${mas_totals['estimated_cost']:.6f}" if mas_totals.get('estimated_cost') is not None else "$0.000000"
    cd_c_disp = f"${cd_totals['estimated_cost']:.6f}" if cd_totals.get('estimated_cost') is not None else "$0.000000"
    print(f"{'Estimated Cost ($)':<30} | {mas_c_disp:<22} | {cd_c_disp:<22}")
    print(f"{'Elapsed Duration (s)':<30} | {mas_dur:<22.2f} | {cd_dur:<22.2f}")
    print(f"{'Completeness (C)':<30} | {fmt_metric(mas_metrics['completeness'])} | {fmt_metric(cd_metrics['completeness'])}")
    print(f"{'Executability (E)':<30} | {fmt_metric(mas_metrics['executability'])} | {fmt_metric(cd_metrics['executability'])}")
    print(f"{'Consistency (S)':<30} | {fmt_metric(mas_metrics['consistency'])} | {fmt_metric(cd_metrics['consistency'])}")
    print(f"{'Quality (Q = C*E*S)':<30} | {fmt_metric(mas_metrics['quality'])} | {fmt_metric(cd_metrics['quality'])}")
    print(f"{'Quality / 1k Tokens':<30} | {fmt_q1k(mas_q1k)} | {fmt_q1k(cd_q1k)}")
    print(f"{'Shared Test Score':<30} | {fmt_metric(mas_metrics['shared_test'])} | {fmt_metric(cd_metrics['shared_test'])}")
    print(f"{'Neutral Battery All Passed':<30} | {str(mas_neutral_results['all_passed']):<22} | {str(cd_neutral_results['all_passed']):<22}")
    print("=" * 80)

    # Gather per-call model provenance from DB
    with get_session() as session:
        mas_calls = [
            {
                "call_id": c.call_id,
                "agent": c.agent,
                "requested_model": c.requested_model,
                "actual_model": c.actual_model,
                "request_id": c.request_id,
                "input_tokens": c.input_tokens,
                "output_tokens": c.output_tokens,
                "total_tokens": c.total_tokens,
                "cost": c.cost,
                "latency_ms": c.latency_ms,
                "raw_metadata": c.raw_metadata,
            }
            for c in session.query(ModelCall).filter(ModelCall.run_id == mas_run_id).all()
        ]
        cd_calls = [
            {
                "call_id": c.call_id,
                "agent": c.agent,
                "requested_model": c.requested_model,
                "actual_model": c.actual_model,
                "request_id": c.request_id,
                "input_tokens": c.input_tokens,
                "output_tokens": c.output_tokens,
                "total_tokens": c.total_tokens,
                "cost": c.cost,
                "latency_ms": c.latency_ms,
                "raw_metadata": c.raw_metadata,
            }
            for c in session.query(ModelCall).filter(ModelCall.run_id == cd_run_id).all()
        ]

    mas_manifest = generate_artifacts_manifest(mas_state["workspace_path"]) if mas_state.get("workspace_path") else []
    cd_manifest = generate_artifacts_manifest(cd_out["workspace_dir"]) if cd_out.get("workspace_dir") else []

    # Save detailed JSON summary for report reconciliation
    summary_path = "eval/canonical_pilot_reconciliation.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "stage": "STAGE_1_CANONICAL_MATCHED_PAIR",
            "task_id": task_id,
            "task_name": task_name,
            "requirement": req,
            "requirement_sha256": actual_req_sha,
            "eval_id": eval_id,
            "max_budget_usd": MAX_STAGE_BUDGET,
            "stage_cumulative_spend_usd": cumulative_spend,
            "mas": {
                "run_id": mas_run_id,
                "status": mas_status,
                "workspace": mas_state.get("workspace_path", ""),
                "duration": mas_dur,
                "totals": mas_totals,
                "metrics": mas_metrics,
                "q1k": mas_q1k,
                "neutral_test": mas_neutral_results,
                "manifest": mas_manifest,
                "model_calls": mas_calls,
            },
            "chatdev": {
                "run_id": cd_run_id,
                "status": cd_status,
                "execution_mode": "SKIPPED" if cd_status == "SKIPPED" else "LIVE_API",
                "skip_reason": "Skipped: Stage 1 stopped after MAS Run A failure" if cd_status == "SKIPPED" else None,
                "failure_reason": None if cd_status == "SKIPPED" else (cd_out.get("failure_reason")),
                "research_statistics_eligible": False,
                "workspace": cd_out.get("workspace_dir", ""),
                "duration": cd_dur,
                "totals": cd_totals,
                "metrics": cd_metrics,
                "q1k": cd_q1k,
                "neutral_test": cd_neutral_results,
                "manifest": cd_manifest,
                "model_calls": cd_calls,
            },
        }, f, indent=2)

    print(f"[Summary] Saved reconciliation JSON to: {summary_path}")
    print(f"[Stage 1 Summary] Total Additional Spend: ${cumulative_spend:.6f} / Budget: ${MAX_STAGE_BUDGET:.2f}")


if __name__ == "__main__":
    main()
