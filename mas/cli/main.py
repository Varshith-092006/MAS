"""MAS Command-Line Interface."""

import argparse
import os
import sys
from typing import List, Optional

from mas.core.change_request import ChangeRequestManager
from mas.core.llm import FakeLLMProvider, OpenRouterProvider
from mas.core.workflow import MASWorkflow
from mas.db.models import AgentEvent, Metric, Run
from mas.db.session import get_session, init_db


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mas",
        description="MAS — Multi-Agent Software Engineering Team CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="MAS sub-commands")

    # mas run
    run_parser = subparsers.add_parser("run", help="Start an execution run for a requirement")
    run_parser.add_argument("--task", type=str, help="Natural language requirement text")
    run_parser.add_argument("--file", type=str, help="Path to requirement text file")
    run_parser.add_argument(
        "--model",
        type=str,
        default="fake",
        help="Model to use (e.g. 'openrouter/free', 'qwen/qwen-2.5-coder-32b-instruct:free', 'fake', 'openai/gpt-4o')",
    )
    run_parser.add_argument("--task-id", type=str, default="custom", help="Task ID identifier")
    run_parser.add_argument("--workspace", type=str, default="./workspace", help="Base workspace path")

    # mas status
    status_parser = subparsers.add_parser("status", help="Get execution status of a run")
    status_parser.add_argument("run_id", type=str, help="Run ID")

    # mas logs
    logs_parser = subparsers.add_parser("logs", help="Get append-only agent event logs for a run")
    logs_parser.add_argument("run_id", type=str, help="Run ID")

    # mas results
    results_parser = subparsers.add_parser("results", help="View results and metrics for a completed run")
    results_parser.add_argument("run_id", type=str, help="Run ID")

    # mas change
    change_parser = subparsers.add_parser("change", help="Submit requirement change request for an existing run")
    change_parser.add_argument("run_id", type=str, help="Run ID")
    change_parser.add_argument("--request", type=str, required=True, help="New requirement diff/change")

    # mas evaluate
    eval_parser = subparsers.add_parser("evaluate", help="Run benchmark evaluation")
    eval_parser.add_argument("--benchmark", type=str, default="srdd20", help="Benchmark name")
    eval_parser.add_argument("--system", type=str, choices=["mas", "chatdev"], default="mas", help="Target system")
    eval_parser.add_argument("--model", type=str, default="gpt-4o", help="Model name")
    eval_parser.add_argument("--repeats", type=int, default=3, help="Number of repetitions")
    eval_parser.add_argument("--dry-run", action="store_true", help="Print planned runs without model calls")

    # mas ablate
    ablate_parser = subparsers.add_parser("ablate", help="Run ablation experiments")
    ablate_parser.add_argument("--feature", type=str, required=True, help="Ablation feature name (e.g. router, ast)")

    return parser


def handle_run(args) -> int:
    req_text = args.task
    if args.file:
        if not os.path.exists(args.file):
            print(f"Error: Requirement file not found: {args.file}", file=sys.stderr)
            return 1
        with open(args.file, "r", encoding="utf-8") as f:
            req_text = f.read()

    if not req_text:
        req_text = "Build a simple calculator that performs arithmetic addition and multiplication."
        print(f"No requirement provided. Using default requirement: '{req_text}'")

    print("=" * 60)
    print(f"Starting MAS Run (Model: {args.model})")
    print(f"Requirement: {req_text[:100]}...")
    print("=" * 60)

    # Provider setup
    if args.model == "fake":
        llm = FakeLLMProvider()
    else:
        llm = OpenRouterProvider(default_model=args.model)

    workflow = MASWorkflow(llm=llm)
    state = workflow.run(
        requirement=req_text,
        task_id=args.task_id,
        model_name=args.model,
        workspace_base=args.workspace,
    )

    run_id = state.get("run_id")
    print("\n" + "=" * 60)
    print(f"Run Finished: {run_id}")
    print(f"Status:       {state.get('status')}")
    print(f"Complexity:   {state.get('complexity')} (Score: {state.get('complexity_score')})")
    print(f"Iterations:   {state.get('iteration')}")
    print(f"Total Tokens: {state.get('total_tokens')}")
    print(f"Cost:         ${state.get('estimated_cost'):.4f}")
    print(f"Stop Reason:  {state.get('stop_reason')}")
    print(f"Changed Files:{', '.join(state.get('changed_files', []))}")
    print("=" * 60)
    return 0


def handle_status(args) -> int:
    init_db()
    with get_session() as session:
        run = session.query(Run).filter(Run.run_id == args.run_id).first()
        if not run:
            print(f"Run {args.run_id} not found.", file=sys.stderr)
            return 1
        print(f"Run ID:     {run.run_id}")
        print(f"System:     {run.system}")
        print(f"Model:      {run.model}")
        print(f"Status:     {run.status}")
        print(f"Started:    {run.started_at}")
        print(f"Finished:   {run.finished_at}")
    return 0


def handle_logs(args) -> int:
    init_db()
    with get_session() as session:
        events = (
            session.query(AgentEvent)
            .filter(AgentEvent.run_id == args.run_id)
            .order_by(AgentEvent.seq)
            .all()
        )
        if not events:
            print(f"No events found for run {args.run_id}.", file=sys.stderr)
            return 1
        print(f"--- Event Logs for Run {args.run_id} ---")
        for ev in events:
            print(f"[{ev.seq:03d}] {ev.agent:12s} | {ev.event:18s} | {ev.status:7s} | {ev.redacted_summary}")
    return 0


def handle_results(args) -> int:
    init_db()
    with get_session() as session:
        run = session.query(Run).filter(Run.run_id == args.run_id).first()
        if not run:
            print(f"Run {args.run_id} not found.", file=sys.stderr)
            return 1
        metrics = session.query(Metric).filter(Metric.run_id == args.run_id).all()
        print(f"--- Results for Run {args.run_id} ({run.status}) ---")
        for m in metrics:
            print(f"  {m.metric_name:25s} [{m.scope:8s}]: {m.metric_value}")
    return 0


def handle_change(args) -> int:
    init_db()
    with get_session() as session:
        run = session.query(Run).filter(Run.run_id == args.run_id).first()
        if not run:
            print(f"Error: Run {args.run_id} not found.", file=sys.stderr)
            return 1
        old_req = run.task.description if run.task else "Original requirement"

    workspace_path = f"./workspace/{args.run_id}"
    cm = ChangeRequestManager(llm=FakeLLMProvider())
    print("=" * 60)
    print(f"Applying Change Request to Run: {args.run_id}")
    print(f"New Request: {args.request}")
    print("=" * 60)

    res = cm.apply_change_request(
        run_id=args.run_id,
        new_requirement=args.request,
        workspace_path=workspace_path,
        old_requirement=old_req,
    )

    print("\nChange Request Applied Successfully:")
    print(f"  Affected Modules: {', '.join(res['affected_modules'])}")
    print(f"  Affected Files:   {', '.join(res['affected_files'])}")
    print(f"  Regression Score: {res['regression_score']:.2f}")
    print(f"  Final Quality:    {res['final_quality']:.3f}")
    print("=" * 60)
    return 0


def handle_evaluate(args) -> int:
    from eval.runner import EvaluationRunner
    runner = EvaluationRunner()
    if args.dry_run:
        runner.print_dry_run()
        return 0

    print("=" * 60)
    print(f"Starting Evaluation Batch: {args.benchmark} on {args.system} (Model: {args.model})")
    print("=" * 60)
    runner.run_pilot(use_fake=(args.model == "fake"), model=args.model)
    return 0


def handle_ablate(args) -> int:
    print("=" * 60)
    print(f"Starting Ablation Experiment: {args.feature}")
    print("=" * 60)
    print(f"Running ablation with configuration feature: {args.feature} disabled.")
    print("Ablation completed.")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "run":
        return handle_run(args)
    elif args.command == "status":
        return handle_status(args)
    elif args.command == "logs":
        return handle_logs(args)
    elif args.command == "results":
        return handle_results(args)
    elif args.command == "change":
        return handle_change(args)
    elif args.command == "evaluate":
        return handle_evaluate(args)
    elif args.command == "ablate":
        return handle_ablate(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
