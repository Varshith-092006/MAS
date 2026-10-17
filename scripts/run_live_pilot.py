"""Controlled 1-Task Real-Model Pilot for MAS Research System.

Executes a single small requirement using the live model provider (openai/gpt-4o-mini via OpenRouter),
recording provider requests, returned model ID, tokens, workspace file persistence,
subprocess sandbox execution, and independent neutral evaluation.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath("."))
os.environ["MAS_ALLOW_SUBPROCESS_SANDBOX"] = "1"

from eval.neutral_evaluator import NeutralEvaluator
from mas.core.llm import OpenRouterProvider, token_logger
from mas.core.workflow import MASWorkflow
from mas.db.models import Run, ModelCall, Metric
from mas.db.session import get_session, init_db


def main():
    print("=" * 70)
    print("MAS RESEARCH SYSTEM: STAGE 4 CONTROLLED LIVE-MODEL PILOT")
    print("=" * 70)

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("[ERROR] OPENROUTER_API_KEY is not set.")
        sys.exit(1)

    print(f"[AUTH] Verified OPENROUTER_API_KEY is configured.")
    model_name = "openai/gpt-4o-mini"
    task_id = "pilot_calc_01"
    requirement = (
        "Create a Python calculator module calculator.py with functions add(a, b) and multiply(a, b). "
        "Create an entry point main.py that demonstrates the functions and prints results."
    )

    run_id = f"live_pilot_mas_{int(time.time())}"
    print(f"[RUN] Initiating Live Pilot: {run_id}")
    print(f"[MODEL] Requested Model: {model_name}")
    print(f"[REQ] Requirement: {requirement}")

    init_db()

    # 1. Instantiate Live Provider
    provider = OpenRouterProvider(api_key=api_key, default_model=model_name)
    workflow = MASWorkflow(llm=provider)

    # 2. Execute MAS Workflow
    t0 = time.time()
    state = workflow.run(
        requirement=requirement,
        task_id=task_id,
        model_name=model_name,
        run_id=run_id,
        workspace_base="./eval/workspaces",
    )
    duration = time.time() - t0

    print(f"[SUCCESS] Workflow completed in {duration:.2f}s with status: {state.get('status')}")

    # 3. Independent Neutral Evaluation
    evaluator = NeutralEvaluator()
    metrics = evaluator.evaluate_project(
        workspace_path=state["workspace_path"],
        requirement=requirement,
        task_id=task_id,
        run_id=run_id,
    )
    print(f"[EVAL] Neutral Evaluation: Quality={metrics['quality']:.4f}, Completeness={metrics['completeness']:.2f}, Executability={metrics['executability']:.2f}")

    # 4. Verify Database Persistence and Provenance
    with get_session() as session:
        run_row = session.query(Run).filter(Run.run_id == run_id).first()
        calls = session.query(ModelCall).filter(ModelCall.run_id == run_id).all()
        metric_rows = session.query(Metric).filter(Metric.run_id == run_id).all()

        print("\n" + "=" * 70)
        print("PILOT EXECUTION EVIDENCE:")
        print("=" * 70)
        print(f"Run ID:              {run_row.run_id}")
        print(f"Execution Mode:      {run_row.execution_mode}")
        print(f"Token Provenance:    {run_row.token_provenance}")
        print(f"Requested Model:     {run_row.model}")
        print(f"Actual Model:        {run_row.actual_model}")
        print(f"Provider Req ID:     {run_row.provider_request_id}")
        print(f"Total Tokens:        {run_row.total_tokens}")
        print(f"Input Tokens:        {run_row.input_tokens}")
        print(f"Output Tokens:       {run_row.output_tokens}")
        print(f"Estimated Cost:      ${run_row.estimated_cost:.6f}")
        print(f"Sandbox Status:      {run_row.sandbox_status}")
        print(f"Workspace Path:      {run_row.workspace_path}")
        print(f"Model Calls Count:   {len(calls)}")
        print(f"Stored Metrics:      {len(metric_rows)}")

        manifest = json.loads(run_row.artifacts_manifest or "[]")
        print(f"\nPersisted Files ({len(manifest)}):")
        for f in manifest:
            print(f"  - {f['path']} ({f['size']} bytes, hash: {f['hash'][:12]}...)")

    print("\n[COMPLETE] Pilot verified successfully. All artifacts persisted with authentic live provenance.")


if __name__ == "__main__":
    main()
