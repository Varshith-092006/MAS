"""Evaluation runner for benchmark experiments, dry runs, pilots, and ablations."""

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.abspath("."))

from eval.chatdev_adapter import ChatDevAdapter
from eval.neutral_evaluator import NeutralEvaluator
from eval.reports import export_results_csv, generate_stats_markdown_report
from eval.srdd_loader import load_srdd_benchmark_tasks, save_and_persist_tasks
from mas.core.llm import FakeLLMProvider, OpenAIProvider
from mas.core.workflow import MASWorkflow
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

    def run_pilot(self, task_index: int = 0, model: str = "gpt-4o", use_fake: bool = True) -> Dict[str, Any]:
        """Runs the 1-task real or fake pilot for both MAS and ChatDev."""
        tasks = self.load_tasks()
        selected_task = tasks[task_index]
        print(f"\nRunning 1-Task Pilot on Task: {selected_task['name']} (ID: {selected_task['task_id']})")

        # 1. Run MAS
        mas_run_id = f"pilot_mas_{selected_task['task_id']}"
        llm = FakeLLMProvider() if use_fake else OpenAIProvider()
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
            run_id=f"pilot_chatdev_{selected_task['task_id']}",
            use_fake=use_fake,
        )

        cd_metrics = self.evaluator.evaluate_project(
            workspace_path=cd_output["workspace_dir"],
            requirement=selected_task["description"],
            task_id=selected_task["task_id"],
            run_id=cd_output["run_id"],
        )

        mas_tokens = mas_state.get("total_tokens", 1)
        cd_tokens = cd_output.get("total_tokens", 1)

        mas_q1k = round(mas_metrics["quality"] / (mas_tokens / 1000), 4) if mas_tokens else 0.0
        cd_q1k = round(cd_metrics["quality"] / (cd_tokens / 1000), 4) if cd_tokens else 0.0

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
        print(f"MAS:     Tokens={mas_tokens}, Quality={mas_metrics['quality']:.3f}, Quality/1k={mas_q1k:.4f}")
        print(f"ChatDev: Tokens={cd_tokens}, Quality={cd_metrics['quality']:.3f}, Quality/1k={cd_q1k:.4f}")
        print("=" * 60 + "\n")

        return pilot_results


def main():
    parser = argparse.ArgumentParser(description="MAS Evaluation Runner")
    parser.add_argument("--dry-run", action="store_true", help="Print dry run plan (0 model calls)")
    parser.add_argument("--pilot", action="store_true", help="Run 1-task pilot for MAS and ChatDev")
    parser.add_argument("--model", type=str, default="fake", help="Model condition (fake, gpt-4o, gpt-4o-mini)")
    args = parser.parse_args()

    runner = EvaluationRunner()
    if args.dry_run:
        runner.print_dry_run()
    elif args.pilot:
        use_fake = (args.model == "fake")
        runner.run_pilot(use_fake=use_fake)
    else:
        runner.print_dry_run()


if __name__ == "__main__":
    main()
