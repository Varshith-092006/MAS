"""Evaluation runner for benchmark experiments, dry runs, pilots, and ablations."""

import argparse
import json
import os
import sys
from datetime import datetime
import time
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.abspath("."))
os.environ["MAS_ALLOW_SUBPROCESS_SANDBOX"] = "1"

from eval.chatdev_adapter import ChatDevAdapter
from eval.neutral_evaluator import NeutralEvaluator
from eval.reports import export_results_csv, generate_stats_markdown_report
from eval.srdd_loader import load_srdd_benchmark_tasks, save_and_persist_tasks
from mas.core.llm import FakeLLMProvider, OpenRouterProvider, token_logger
from mas.core.workflow import MASWorkflow, generate_artifacts_manifest
from mas.db.models import Evaluation, Run
from mas.db.session import get_session, init_db


class EvaluationRunner:
    """Manages execution of benchmark matrices, ablations, and dry runs."""

    def __init__(
        self,
        tasks_path: str = "eval/tasks.json",
        results_path: str = "results.csv",
        llm=None,
    ):
        self.tasks_path = tasks_path
        self.results_path = results_path
        self.llm = llm or FakeLLMProvider()
        self.evaluator = NeutralEvaluator()

    def load_tasks(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.tasks_path):
            save_and_persist_tasks(self.tasks_path)
        with open(self.tasks_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def print_dry_run(self):
        """Displays planned 300 core runs and planning token envelope with ZERO model calls."""
        tasks = self.load_tasks()
        print("\n" + "=" * 70)
        print("MAS EMPIRICAL EVALUATION — DRY RUN SUMMARY (ZERO MODEL CALLS)")
        print("=" * 70)

        # 1. Main comparison
        main_tasks = tasks[:20]
        print(f"\n[1] MAIN BENCHMARK (GPT-4o)")
        print(f"    Tasks:   20 (Education: 4, Work: 4, Life: 4, Games: 4, Creation: 4)")
        print(f"    Systems: MAS (Reviewer: GPT-4o-mini), ChatDev")
        print(f"    Repeats: 3")
        print(f"    Runs:    20 tasks x 3 repeats x 2 systems = 120 model runs")

        # 2. Cheaper MAS
        print(f"\n[2] CHEAPER MAS ARM (GPT-4o-mini)")
        print(f"    Tasks:   20")
        print(f"    System:  MAS only")
        print(f"    Repeats: 3")
        print(f"    Runs:    20 tasks x 3 repeats = 60 model runs")

        # 3. Ablations
        ablation_tasks = tasks[:10]
        ablation_configs = [
            ("A1", "Router OFF (Always STRUCTURED)"),
            ("A2", "AST OFF (No dependency cycle/impact pruning)"),
            ("A3", "Context Slicing OFF (Resend full project each iteration)"),
            ("A4", "Cheap Reviewer OFF (Use GPT-4o for review)"),
            ("A5", "Adaptive Stop OFF (Always run MAX_ITERATIONS=3)"),
            ("A6", "UML/Sprint Always ON"),
        ]
        print(f"\n[3] ABLATION EXPERIMENTS (GPT-4o-mini)")
        print(f"    Tasks:   10 tasks (first 10 SRDD tasks)")
        print(f"    Configs: 6 configurations (A1 to A6)")
        print(f"    Repeats: 2")
        print(f"    Runs:    10 tasks x 2 repeats x 6 configs = 120 model runs")
        print(f"    * Note: A0 is reference row from existing first 2 MAS repeats (0 extra runs)")

        # Total runs
        total_runs = 120 + 60 + 120
        print("\n" + "-" * 70)
        print(f"TOTAL CORE EXPERIMENTAL RUNS = {total_runs}")
        print("-" * 70)

        # Planning token envelope
        gpt4o_envelope = 120 * 40_000
        gpt4o_mini_mas_envelope = 60 * 20_000
        gpt4o_mini_ablate_envelope = 120 * 20_000
        total_envelope = gpt4o_envelope + gpt4o_mini_mas_envelope + gpt4o_mini_ablate_envelope

        print("\nENGINEERING PLANNING TOKEN ENVELOPE (Engineering budget cap, not measured benchmark data):")
        print(f"  - GPT-4o Main (120 runs @ 40,000 cap):        {gpt4o_envelope:,} tokens ({gpt4o_envelope/1e6:.1f}M)")
        print(f"  - GPT-4o-mini MAS (60 runs @ 20,000 cap):      {gpt4o_mini_mas_envelope:,} tokens ({gpt4o_mini_mas_envelope/1e6:.1f}M)")
        print(f"  - GPT-4o-mini Ablate (120 runs @ 20,000 cap):  {gpt4o_mini_ablate_envelope:,} tokens ({gpt4o_mini_ablate_envelope/1e6:.1f}M)")
        print(f"  -------------------------------------------------------------")
        print(f"  TOTAL PLANNING ENVELOPE:                      {total_envelope:,} tokens ({total_envelope/1e6:.1f}M)")
        print("=" * 70 + "\n")

    def dry_run(
        self,
        tasks: Optional[List[Dict[str, Any]]] = None,
        repeats: int = 3,
        systems: Optional[List[str]] = None,
        models: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Calculates planned benchmark matrix and reports ZERO model calls."""
        task_list = tasks if tasks is not None else self.load_tasks()
        systems = systems or ["mas", "chatdev"]
        models = models or ["gpt-4o"]
        total_runs = len(task_list) * repeats * len(systems) * len(models)
        self.print_dry_run()
        return {
            "planned_runs": total_runs,
            "model_calls": 0,
            "systems": systems,
            "models": models,
            "repeats": repeats,
            "tasks_count": len(task_list),
        }

    def run_pilot(self, task_index: int = 0, model: str = "gpt-4o", use_fake: bool = True) -> Dict[str, Any]:
        """Runs the 1-task real or fake pilot for both MAS and ChatDev."""
        tasks = self.load_tasks()
        selected_task = tasks[task_index]
        print(f"\nRunning 1-Task Pilot on Task: {selected_task['name']} (ID: {selected_task['task_id']})")

        # 1. Run MAS
        timestamp = int(time.time())
        mas_run_id = f"pilot_mas_{selected_task['task_id']}_{timestamp}"
        llm = FakeLLMProvider() if use_fake else OpenRouterProvider(default_model=model)
        mas_workflow = MASWorkflow(llm=llm)
        mas_state = mas_workflow.run(
            requirement=selected_task["description"],
            task_id=selected_task["task_id"],
            model_name=model,
            run_id=mas_run_id,
            workspace_base="./eval/workspaces",
        )

        # Neutral evaluation of MAS output
        mas_metrics = self.evaluator.evaluate_project(
            workspace_path=mas_state["workspace_path"],
            requirement=selected_task["description"],
            task_id=selected_task["task_id"],
            run_id=mas_run_id,
        )

        # 2. Run ChatDev
        cd_adapter = ChatDevAdapter(llm=llm)
        cd_output = cd_adapter.run_task(
            task=selected_task,
            output_base_dir="./eval/workspaces",
            model=model,
            run_id=f"pilot_chatdev_{selected_task['task_id']}_{timestamp}",
            use_fake=use_fake,
        )

        cd_metrics = self.evaluator.evaluate_project(
            workspace_path=cd_output["workspace_dir"],
            requirement=selected_task["description"],
            task_id=selected_task["task_id"],
            run_id=cd_output["run_id"],
        )

        mas_totals = token_logger.get_run_totals(mas_run_id)
        cd_totals = token_logger.get_run_totals(cd_output["run_id"])
        mas_tokens = mas_totals["total_tokens"]
        cd_tokens = cd_totals["total_tokens"]

        mas_q1k = round(mas_metrics["quality"] / (mas_tokens / 1000), 4) if (mas_tokens and mas_tokens > 0) else None
        cd_q1k = round(cd_metrics["quality"] / (cd_tokens / 1000), 4) if (cd_tokens and cd_tokens > 0) else None

        pilot_results = {
            "task_id": selected_task["task_id"],
            "task_name": selected_task["name"],
            "mas": {
                "run_id": mas_run_id,
                "tokens": mas_tokens,
                "quality": mas_metrics["quality"],
                "quality_per_1k_tokens": mas_q1k,
                "completeness": mas_metrics["completeness"],
                "executability": mas_metrics["executability"],
                "consistency": mas_metrics["consistency"],
            },
            "chatdev": {
                "run_id": cd_output["run_id"],
                "tokens": cd_tokens,
                "quality": cd_metrics["quality"],
                "quality_per_1k_tokens": cd_q1k,
                "completeness": cd_metrics["completeness"],
                "executability": cd_metrics["executability"],
                "consistency": cd_metrics["consistency"],
            },
        }

        print("\n" + "=" * 60)
        print("PILOT EXECUTION RESULTS:")
        mas_q1k_str = f"{mas_q1k:.4f}" if mas_q1k is not None else "N/A"
        cd_q1k_str = f"{cd_q1k:.4f}" if cd_q1k is not None else "N/A"
        print(f"MAS:     Tokens={mas_tokens}, Quality={mas_metrics['quality']:.3f}, Quality/1k={mas_q1k_str}")
        print(f"ChatDev: Tokens={cd_tokens}, Quality={cd_metrics['quality']:.3f}, Quality/1k={cd_q1k_str}")
        print("=" * 60 + "\n")

    def run_benchmark(
        self,
        task_count: int = 20,
        repeats: int = 1,
        model: str = "fake",
        use_fake: bool = True,
        systems: Optional[List[str]] = None,
        benchmark_name: str = "srdd20",
    ) -> Dict[str, Any]:
        """Executes full benchmark evaluation across sampled SRDD tasks under identical conditions."""
        systems = systems or ["mas", "chatdev"]
        tasks = self.load_tasks()[:task_count]

        print("\n" + "=" * 70)
        print(f"STARTING EMPIRICAL BENCHMARK: {benchmark_name.upper()}")
        print(f"Tasks: {len(tasks)} | Systems: {systems} | Repeats: {repeats} | Model: {model}")
        print("=" * 70)

        eval_id = f"eval_{int(time.time())}_{benchmark_name}"
        init_db()

        # Persist Evaluation record
        with get_session() as session:
            ev = Evaluation(
                evaluation_id=eval_id,
                benchmark=benchmark_name,
                repeat_no=repeats,
                ablation="A0",
            )
            session.add(ev)
            session.commit()

        mas_records = []
        cd_records = []
        all_records = []

        llm = FakeLLMProvider() if use_fake else OpenRouterProvider(default_model=model)

        for t_idx, task in enumerate(tasks):
            t_id = task.get("task_id", f"task_{t_idx+1:02d}")
            t_name = task.get("name", t_id)
            req = task.get("description", "")
            cat = task.get("category", "Creation")

            print(f"\n[{t_idx+1}/{len(tasks)}] Evaluating Task: {t_name} ({t_id}) [{cat}]")

            for r_num in range(1, repeats + 1):
                # 1. Run MAS
                if "mas" in systems:
                    mas_run_id = f"mas_{t_id}_r{r_num}"
                    t_start = datetime.utcnow()
                    workflow = MASWorkflow(llm=llm)
                    state = workflow.run(
                        requirement=req,
                        task_id=t_id,
                        model_name=model,
                        run_id=mas_run_id,
                        workspace_base="./eval/workspaces",
                    )
                    t_end = datetime.utcnow()

                    mas_metrics = self.evaluator.evaluate_project(
                        workspace_path=state["workspace_path"],
                        requirement=req,
                        task_id=t_id,
                        run_id=mas_run_id,
                    )
                    totals = token_logger.get_run_totals(mas_run_id)
                    tot_tok = totals["total_tokens"]
                    q = mas_metrics["quality"]
                    q1k = round(q / (tot_tok / 1000), 4) if (q is not None and tot_tok and tot_tok > 0) else None
                    exec_mode = "SIMULATED" if use_fake else "LIVE_API"
                    prov_mode = "SIMULATED" if use_fake else ("PROVIDER_REPORTED" if (tot_tok and tot_tok > 0) else "UNAVAILABLE")
                    mas_manifest = generate_artifacts_manifest(state["workspace_path"])

                    with get_session() as session:
                        mas_row = session.query(Run).filter(Run.run_id == mas_run_id).first()
                        if mas_row:
                            mas_row.evaluation_id = eval_id
                            mas_row.status = "COMPLETED"
                            mas_row.execution_mode = exec_mode
                            mas_row.token_provenance = prov_mode
                            mas_row.workspace_path = state["workspace_path"]
                            mas_row.artifacts_manifest = json.dumps(mas_manifest)
                            if not mas_row.finished_at:
                                mas_row.finished_at = t_end
                        else:
                            session.add(
                                Run(
                                    run_id=mas_run_id,
                                    task_id=t_id,
                                    evaluation_id=eval_id,
                                    system="mas",
                                    model=model,
                                    actual_model=model,
                                    execution_mode=exec_mode,
                                    token_provenance=prov_mode,
                                    workspace_path=state["workspace_path"],
                                    artifacts_manifest=json.dumps(mas_manifest),
                                    status="COMPLETED",
                                    started_at=t_start,
                                    finished_at=t_end,
                                )
                            )
                        session.commit()

                    rec = {
                        "run_id": mas_run_id,
                        "task_id": t_id,
                        "system": "mas",
                        "model": model,
                        "repeat_no": r_num,
                        "ablation": "A0",
                        "quality": q,
                        "quality_per_1k_tokens": q1k,
                        "completeness": mas_metrics["completeness"],
                        "executability": mas_metrics["executability"],
                        "consistency": mas_metrics["consistency"],
                        "shared_test": mas_metrics["shared_test"],
                        "ruff": mas_metrics["ruff_violations"],
                        "bandit": mas_metrics["bandit_high"],
                        "radon": mas_metrics["radon_mi"],
                        "tokens": tot_tok,
                        "cost": totals["estimated_cost"],
                        "status": "COMPLETED",
                    }
                    mas_records.append(rec)
                    all_records.append(rec)
                    mas_q_disp = f"{q:.4f}" if q is not None else "None"
                    mas_q1k_disp = f"{q1k:.4f}" if q1k is not None else "None"
                    print(f"   [OK] MAS:     Quality={mas_q_disp} | Tokens={tot_tok} | Quality/1k={mas_q1k_disp}")

                # 2. Run ChatDev
                if "chatdev" in systems:
                    cd_run_id = f"cd_{t_id}_r{r_num}"
                    t_start = datetime.utcnow()
                    cd_adapter = ChatDevAdapter(llm=llm)
                    cd_out = cd_adapter.run_task(
                        task=task,
                        output_base_dir="./eval/workspaces",
                        model=model,
                        run_id=cd_run_id,
                        use_fake=use_fake,
                    )
                    t_end = datetime.utcnow()

                    cd_metrics = self.evaluator.evaluate_project(
                        workspace_path=cd_out["workspace_dir"],
                        requirement=req,
                        task_id=t_id,
                        run_id=cd_run_id,
                    )
                    totals = token_logger.get_run_totals(cd_run_id)
                    tot_tok = totals["total_tokens"]
                    q = cd_metrics["quality"]
                    q1k = round(q / (tot_tok / 1000), 4) if (q is not None and tot_tok and tot_tok > 0) else None
                    cd_manifest = generate_artifacts_manifest(cd_out["workspace_dir"])

                    with get_session() as session:
                        cd_row = session.query(Run).filter(Run.run_id == cd_run_id).first()
                        if cd_row:
                            cd_row.evaluation_id = eval_id
                            cd_row.status = "COMPLETED"
                            cd_row.execution_mode = exec_mode
                            cd_row.token_provenance = prov_mode
                            cd_row.workspace_path = cd_out["workspace_dir"]
                            cd_row.artifacts_manifest = json.dumps(cd_manifest)
                            if not cd_row.finished_at:
                                cd_row.finished_at = t_end
                        else:
                            session.add(
                                Run(
                                    run_id=cd_run_id,
                                    task_id=t_id,
                                    evaluation_id=eval_id,
                                    system="chatdev",
                                    model=model,
                                    actual_model=model,
                                    execution_mode=exec_mode,
                                    token_provenance=prov_mode,
                                    workspace_path=cd_out["workspace_dir"],
                                    artifacts_manifest=json.dumps(cd_manifest),
                                    status="COMPLETED",
                                    started_at=t_start,
                                    finished_at=t_end,
                                )
                            )
                        session.commit()

                    rec = {
                        "run_id": cd_run_id,
                        "task_id": t_id,
                        "system": "chatdev",
                        "model": model,
                        "repeat_no": r_num,
                        "ablation": "A0",
                        "quality": q,
                        "quality_per_1k_tokens": q1k,
                        "completeness": cd_metrics["completeness"],
                        "executability": cd_metrics["executability"],
                        "consistency": cd_metrics["consistency"],
                        "shared_test": cd_metrics["shared_test"],
                        "ruff": cd_metrics["ruff_violations"],
                        "bandit": cd_metrics["bandit_high"],
                        "radon": cd_metrics["radon_mi"],
                        "tokens": tot_tok,
                        "cost": totals["estimated_cost"],
                        "status": "COMPLETED",
                    }
                    cd_records.append(rec)
                    all_records.append(rec)
                    cd_q_disp = f"{q:.4f}" if q is not None else "None"
                    cd_q1k_disp = f"{q1k:.4f}" if q1k is not None else "None"
                    print(f"   [OK] ChatDev: Quality={cd_q_disp} | Tokens={tot_tok} | Quality/1k={cd_q1k_disp}")

        # Export CSV & Stats report
        export_results_csv(all_records, self.results_path)
        if mas_records and cd_records:
            generate_stats_markdown_report(mas_records, cd_records)

        # Summary calculations
        mas_valid_q = [r["quality"] for r in mas_records if r.get("quality") is not None]
        cd_valid_q = [r["quality"] for r in cd_records if r.get("quality") is not None]
        mas_avg_q = sum(mas_valid_q) / len(mas_valid_q) if mas_valid_q else 0.0
        cd_avg_q = sum(cd_valid_q) / len(cd_valid_q) if cd_valid_q else 0.0
        mas_avg_tok = sum(r["tokens"] for r in mas_records) / len(mas_records) if mas_records else 0.0
        cd_avg_tok = sum(r["tokens"] for r in cd_records) / len(cd_records) if cd_records else 0.0

        print("\n" + "=" * 70)
        print("EMPIRICAL BENCHMARK COMPLETE — FINAL SUMMARY")
        print("=" * 70)
        print(f"MAS Quality:         {mas_avg_q:.4f}  (Tokens/task: {mas_avg_tok:,.1f})")
        print(f"ChatDev Quality:     {cd_avg_q:.4f}  (Tokens/task: {cd_avg_tok:,.1f})")
        print(f"iCoder (Published):  0.7924  (Tokens/task: 104,883.2)")
        print("-" * 70)
        if cd_avg_q > 0:
            gain_vs_cd = ((mas_avg_q - cd_avg_q) / cd_avg_q) * 100
            print(f"MAS Quality Advantage vs ChatDev: {gain_vs_cd:+.1f}%")
        gain_vs_icoder = ((mas_avg_q - 0.7924) / 0.7924) * 100
        print(f"MAS Quality Advantage vs iCoder:  {gain_vs_icoder:+.1f}%")
        tok_reduction = (1.0 - (mas_avg_tok / 104883.2)) * 100
        print(f"MAS Token Reduction vs iCoder:    {tok_reduction:.1f}% LESS tokens consumed")
        print("=" * 70 + "\n")

        return {
            "evaluation_id": eval_id,
            "tasks_count": len(tasks),
            "mas_quality": mas_avg_q,
            "chatdev_quality": cd_avg_q,
            "mas_tokens_per_task": mas_avg_tok,
            "chatdev_tokens_per_task": cd_avg_tok,
            "icoder_reference_quality": 0.7924,
            "icoder_reference_tokens": 104883.2,
        }


def reset_environment():
    """Wipes all existing database records and workspace folders clean."""
    import shutil
    from mas.db.session import get_engine, init_db
    from mas.db.models import Base

    print("Cleaning database...")
    eng = get_engine()
    Base.metadata.drop_all(bind=eng)
    Base.metadata.create_all(bind=eng)

    print("Cleaning workspaces...")
    for ws_dir in ["./workspace", "./eval/workspaces"]:
        if os.path.exists(ws_dir):
            for item in os.listdir(ws_dir):
                item_path = os.path.join(ws_dir, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path, ignore_errors=True)
                elif not item.startswith("."):
                    try:
                        os.remove(item_path)
                    except Exception:
                        pass
    print("Environment reset complete.")


def main():
    parser = argparse.ArgumentParser(description="MAS Evaluation Runner")
    parser.add_argument("--dry-run", action="store_true", help="Print dry run plan (0 model calls)")
    parser.add_argument("--pilot", action="store_true", help="Run 1-task pilot for MAS and ChatDev")
    parser.add_argument("--benchmark", action="store_true", help="Run full 20-task benchmark across MAS and ChatDev")
    parser.add_argument("--reset", action="store_true", help="Wipe all existing database data and workspaces clean")
    parser.add_argument("--model", type=str, default="fake", help="Model condition (e.g. 'fake', 'openrouter/free', 'openai/gpt-4o')")
    parser.add_argument("--tasks", type=int, default=20, help="Number of benchmark tasks to run")
    parser.add_argument("--repeats", type=int, default=1, help="Repetitions per task")
    args = parser.parse_args()

    if args.reset:
        reset_environment()

    runner = EvaluationRunner()

    if args.dry_run:
        runner.print_dry_run()
    elif args.pilot:
        use_fake = (args.model == "fake")
        runner.run_pilot(model=args.model, use_fake=use_fake)
    elif args.benchmark:
        use_fake = (args.model == "fake")
        runner.run_benchmark(task_count=args.tasks, repeats=args.repeats, model=args.model, use_fake=use_fake)
    else:
        runner.print_dry_run()


if __name__ == "__main__":
    main()

