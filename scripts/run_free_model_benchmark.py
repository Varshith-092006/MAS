"""Execute free-model exploratory benchmark for MAS vs ChatDev using cohere/north-mini-code:free.

Experiment Label: FREE_MODEL_EXPLORATORY
Requested Model: cohere/north-mini-code:free
Preserves:
1. Canonical task identity from eval/tasks.json (Science Question Solver)
2. Byte-for-byte identical requirement string to both MAS and ChatDev
3. Unified software generation contract (Python 3.11+, main.py entry point)
4. Symmetric evaluator protocol (NeutralEvaluator with fixed assertions)
5. Strict provider routing (allow_fallbacks: False) and provider-reported usage
6. Preserves historical GPT-4o records as separate experimental conditions.
"""

import hashlib
import json
import os
import sys
import threading
import time
from datetime import datetime

sys.path.insert(0, os.path.abspath("."))
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass
from dotenv import load_dotenv

load_dotenv("c:/Users/The Mighty King/Desktop/Final Year Project/.env")
os.environ["MAS_ALLOW_SUBPROCESS_SANDBOX"] = "1"

import uvicorn
from eval.chatdev_adapter import ChatDevAdapter
from eval.neutral_evaluator import NeutralEvaluator
from eval.checks.test_srdd_educ_01 import run_neutral_test
from mas.core.llm import OpenRouterProvider, token_logger, OpenRouterAPIError, ModelMismatchError
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


def run_canonical_pair(tasks, api_key: str, model: str = "cohere/north-mini-code:free"):
    print("=" * 80)
    print("FREE MODEL EXPLORATORY BENCHMARK: CANONICAL TASK srdd_educ_01")
    print("=" * 80)

    task = tasks[0]
    task_id = task["task_id"]
    task_name = task["name"]
    category = task["category"]
    subcategory = task.get("subcategory", "Science")
    req = task["description"]

    expected_req_sha = "15b83bd79330fcf4a79de4ad9cbc725ffeba2a695f1b76bf4d1ca567c4740012"
    actual_req_sha = hashlib.sha256(req.encode("utf-8")).hexdigest()

    assert task_id == "srdd_educ_01", f"Task ID mismatch: {task_id}"
    assert task_name == "Science Question Solver", f"Task name mismatch: {task_name}"
    assert actual_req_sha == expected_req_sha, f"Requirement checksum mismatch: {actual_req_sha}"

    eval_id = f"eval_free_model_exploratory_{int(time.time())}"

    print(f"Task ID:          {task_id}")
    print(f"Task Name:        {task_name}")
    print(f"Category:         {category} ({subcategory})")
    print(f"Requirement:      {req}")
    print(f"Req Checksum:     SHA-256:{actual_req_sha}")
    print(f"Model Condition:  {model}")
    print(f"Evaluation ID:    {eval_id}")
    print("=" * 80)

    init_db()

    with get_session() as session:
        session.add(Evaluation(
            evaluation_id=eval_id,
            benchmark="FREE_MODEL_EXPLORATORY",
            repeat_no=1,
            ablation="A0",
        ))
        session.commit()

    proxy_port = 8089
    start_proxy_daemon(port=proxy_port)

    llm = OpenRouterProvider(api_key=api_key, default_model=model)
    evaluator = NeutralEvaluator()

    # -------------------------------------------------------------------------
    # 1. RUN MAS (Canonical Task)
    # -------------------------------------------------------------------------
    mas_run_id = f"mas_{task_id}_free_exp"
    mas_ws = os.path.abspath(f"./eval/workspaces/{mas_run_id}")
    print(f"\n[MAS] Starting execution: {mas_run_id} -> {mas_ws}")

    t0 = time.time()
    mas_workflow = MASWorkflow(llm=llm)
    mas_is_provider_failure = False

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

        mas_metrics = evaluator.evaluate_project(
            workspace_path=mas_state["workspace_path"],
            requirement=req,
            task_id=task_id,
            run_id=mas_run_id,
            persist_to_db=True,
        )
        mas_totals = token_logger.get_run_totals(mas_run_id)
        mas_cost = mas_totals.get("estimated_cost") or 0.0

        print(f"[MAS] Total Tokens: {mas_totals['total_tokens']}, Incurred Cost: ${mas_cost:.6f}")
        mas_neutral_results = run_neutral_test(mas_state["workspace_path"])

    except (OpenRouterAPIError, ModelMismatchError) as e:
        mas_dur = time.time() - t0
        mas_status = "FAILED"
        mas_is_provider_failure = True
        print(f"\n[MAS PROVIDER ERROR] Execution halted due to provider/model failure: {e}")
        mas_state = {"status": "FAILED", "stop_reason": str(e), "workspace_path": mas_ws}
        mas_metrics = {"completeness": None, "executability": None, "consistency": None, "quality": None, "shared_test": None}
        mas_totals = token_logger.get_run_totals(mas_run_id)
        mas_neutral_results = {"all_passed": False, "passed": 0, "total": 0, "details": [f"Provider failure: {str(e)}"]}

    except Exception as e:
        mas_dur = time.time() - t0
        mas_status = "FAILED"
        print(f"\n[MAS APPLICATION ERROR] Generation failed: {e}")
        mas_state = {"status": "FAILED", "stop_reason": str(e), "workspace_path": mas_ws}
        mas_metrics = {"completeness": None, "executability": None, "consistency": None, "quality": None, "shared_test": None}
        mas_totals = token_logger.get_run_totals(mas_run_id)
        mas_neutral_results = {"all_passed": False, "passed": 0, "total": 0, "details": [f"Application error: {str(e)}"]}

    # Update evaluation_id on MAS run record
    with get_session() as session:
        r = session.query(Run).filter(Run.run_id == mas_run_id).first()
        if r:
            r.evaluation_id = eval_id
            session.commit()

    # -------------------------------------------------------------------------
    # 2. RUN CHATDEV (Canonical Task)
    # Only stop ChatDev if provider itself failed; do NOT stop on application errors
    # -------------------------------------------------------------------------
    cd_run_id = f"cd_{task_id}_free_exp"
    cd_ws = os.path.abspath(f"./eval/workspaces/{cd_run_id}")

    if mas_is_provider_failure:
        print(f"\n[HALT] Model provider unavailable for MAS. Marking ChatDev incomplete/skipped per provider-failure protocol.")
        cd_status = "SKIPPED"
        cd_dur = 0.0
        cd_metrics = {"completeness": None, "executability": None, "consistency": None, "quality": None, "shared_test": None}
        cd_totals = {"total_tokens": None, "input_tokens": None, "output_tokens": None, "estimated_cost": 0.0, "call_count": 0, "token_provenance": "UNAVAILABLE"}
        cd_neutral_results = {"all_passed": False, "passed": 0, "total": 0, "details": ["Skipped due to upstream provider failure on MAS run"]}
        cd_skip_reason = "Skipped: Upstream model provider unavailable"

        with get_session() as session:
            session.add(Run(
                run_id=cd_run_id,
                task_id=task_id,
                evaluation_id=eval_id,
                system="chatdev",
                model=model,
                actual_model=model,
                execution_mode="SKIPPED",
                status="SKIPPED",
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
            session.commit()

    else:
        print(f"\n[ChatDev] Starting execution: {cd_run_id} -> {cd_ws}")
        t0 = time.time()
        cd_adapter = ChatDevAdapter(
            proxy_url=f"http://127.0.0.1:{proxy_port}/v1",
            llm=llm,
        )
        try:
            cd_out = cd_adapter.run_task(
                task=task,
                output_base_dir="./eval/workspaces",
                model=model,
                run_id=cd_run_id,
                use_fake=False,
            )
            cd_dur = time.time() - t0
            print(f"[ChatDev] Generation completed in {cd_dur:.2f}s")

            cd_metrics = evaluator.evaluate_project(
                workspace_path=cd_out["workspace_dir"],
                requirement=req,
                task_id=task_id,
                run_id=cd_run_id,
                persist_to_db=True,
            )
            cd_totals = token_logger.get_run_totals(cd_run_id)
            cd_cost = cd_totals.get("estimated_cost") or 0.0
            cd_neutral_results = run_neutral_test(cd_out["workspace_dir"])

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
            cd_status = "COMPLETED" if (cd_totals["total_tokens"] > 0 and len(cd_manifest) > 0) else "FAILED"

        except Exception as e:
            cd_dur = time.time() - t0
            cd_status = "FAILED"
            print(f"[ChatDev ERROR] Execution failed: {e}")
            cd_metrics = {"completeness": None, "executability": None, "consistency": None, "quality": None, "shared_test": None}
            cd_totals = token_logger.get_run_totals(cd_run_id)
            cd_neutral_results = {"all_passed": False, "passed": 0, "total": 0, "details": [f"ChatDev error: {str(e)}"]}
            with get_session() as session:
                cd_row = session.query(Run).filter(Run.run_id == cd_run_id).first()
                if cd_row:
                    cd_row.status = "FAILED"
                    cd_row.failure_reason = str(e)[:255]
                    session.commit()

    # -------------------------------------------------------------------------
    # 3. RECONCILIATION SUMMARY
    # -------------------------------------------------------------------------
    pair_status = "COMPLETED" if (mas_status == "COMPLETED" and cd_status == "COMPLETED") else "INCOMPLETE"

    mas_q1k = round(mas_metrics["quality"] / (mas_totals["total_tokens"] / 1000), 4) if (mas_metrics.get("quality") is not None and mas_totals.get("total_tokens")) else None
    cd_q1k = round(cd_metrics["quality"] / (cd_totals["total_tokens"] / 1000), 4) if (cd_metrics.get("quality") is not None and cd_totals.get("total_tokens")) else None

    reconciliation = {
        "benchmark": "FREE_MODEL_EXPLORATORY",
        "task_id": task_id,
        "task_name": task_name,
        "requirement_sha256": actual_req_sha,
        "requested_model": model,
        "evaluation_id": eval_id,
        "timestamp": datetime.utcnow().isoformat(),
        "pair_status": pair_status,
        "mas": {
            "run_id": mas_run_id,
            "status": mas_status,
            "duration_s": round(mas_dur, 2),
            "tokens": mas_totals.get("total_tokens"),
            "token_provenance": mas_totals.get("token_provenance", "PROVIDER_REPORTED"),
            "cost_usd": mas_totals.get("estimated_cost", 0.0),
            "completeness": mas_metrics.get("completeness"),
            "executability": mas_metrics.get("executability"),
            "consistency": mas_metrics.get("consistency"),
            "quality_q": mas_metrics.get("quality"),
            "quality_per_1k": mas_q1k,
            "neutral_test_passed": mas_neutral_results.get("all_passed", False),
            "neutral_test_details": mas_neutral_results.get("details", []),
        },
        "chatdev": {
            "run_id": cd_run_id,
            "status": cd_status,
            "duration_s": round(cd_dur, 2),
            "tokens": cd_totals.get("total_tokens"),
            "token_provenance": cd_totals.get("token_provenance", "PROVIDER_REPORTED"),
            "cost_usd": cd_totals.get("estimated_cost", 0.0),
            "completeness": cd_metrics.get("completeness"),
            "executability": cd_metrics.get("executability"),
            "consistency": cd_metrics.get("consistency"),
            "quality_q": cd_metrics.get("quality"),
            "quality_per_1k": cd_q1k,
            "neutral_test_passed": cd_neutral_results.get("all_passed", False),
            "neutral_test_details": cd_neutral_results.get("details", []),
        }
    }

    recon_file = "eval/free_model_exploratory_reconciliation.json"
    with open(recon_file, "w", encoding="utf-8") as f:
        json.dump(reconciliation, f, indent=2)

    fmt_metric = lambda v: f"{v:<22.4f}" if v is not None else f"{'N/A':<22}"
    fmt_tok = lambda v: f"{v:<22}" if v is not None else f"{'UNAVAILABLE':<22}"
    fmt_q1k = lambda v: f"{v:<22}" if v is not None else f"{'N/A':<22}"

    print("\n" + "=" * 80)
    print("FREE MODEL EXPLORATORY COMPARISON RESULTS")
    print("=" * 80)
    print(f"{'Metric / Parameter':<30} | {'MAS Architecture':<22} | {'ChatDev Baseline':<22}")
    print("-" * 80)
    print(f"{'System Status':<30} | {mas_status:<22} | {cd_status:<22}")
    print(f"{'Model Condition':<30} | {model:<22} | {model:<22}")
    print(f"{'Completeness (C)':<30} | {fmt_metric(mas_metrics.get('completeness'))} | {fmt_metric(cd_metrics.get('completeness'))}")
    print(f"{'Executability (E)':<30} | {fmt_metric(mas_metrics.get('executability'))} | {fmt_metric(cd_metrics.get('executability'))}")
    print(f"{'Consistency (S / Security)':<30} | {fmt_metric(mas_metrics.get('consistency'))} | {fmt_metric(cd_metrics.get('consistency'))}")
    print(f"{'Composite Quality (Q=C*E*S)':<30} | {fmt_metric(mas_metrics.get('quality'))} | {fmt_metric(cd_metrics.get('quality'))}")
    print(f"{'Neutral Suite Passed':<30} | {str(mas_neutral_results.get('all_passed')):<22} | {str(cd_neutral_results.get('all_passed')):<22}")
    print(f"{'Total Tokens':<30} | {fmt_tok(mas_totals.get('total_tokens'))} | {fmt_tok(cd_totals.get('total_tokens'))}")
    print(f"{'Estimated Cost (USD)':<30} | ${mas_totals.get('estimated_cost', 0.0):<21.6f} | ${cd_totals.get('estimated_cost', 0.0):<21.6f}")
    print(f"{'Quality / 1K Tokens':<30} | {fmt_q1k(mas_q1k)} | {fmt_q1k(cd_q1k)}")
    print(f"{'Execution Runtime (s)':<30} | {mas_dur:<22.2f} | {cd_dur:<22.2f}")
    print("=" * 80)
    print(f"Reconciliation JSON saved to: {recon_file}")

    return reconciliation


if __name__ == "__main__":
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("[ERROR] OPENROUTER_API_KEY not configured.")
        sys.exit(1)

    tasks_file = "eval/tasks.json"
    with open(tasks_file, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    res = run_canonical_pair(tasks, api_key)
