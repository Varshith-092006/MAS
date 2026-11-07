"""Evaluation runner for benchmark experiments, dry runs, pilots, and ablations."""

import argparse
import json
import os
import sys
from datetime import datetime
import time
from typing import Any, Dict, List, Optional, Set

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

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


MANIFEST_FILE = os.path.abspath("eval/benchmark_manifest.json")


def load_benchmark_manifest(manifest_path: Optional[str] = None) -> Dict[str, Any]:
    """Loads the persistent benchmark execution manifest."""
    target = manifest_path or MANIFEST_FILE
    if os.path.exists(target):
        try:
            with open(target, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "version": "1.0",
        "benchmark": "srdd20",
        "last_updated_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runs": [],
        "summary": {
            "total_canonical_tasks": 20,
            "required_repeats": 3,
            "completed_paired_repeats": 0,
            "mas_completed_runs": 0,
            "chatdev_completed_runs": 0,
        },
    }


def resolve_attempt_run_id(
    prefix: str,
    system: str,
    task_id: str,
    repeat_no: int,
    start_attempt: Optional[int] = None,
) -> str:
    """Resolves an attempt-scoped run ID ensuring historical attempts are preserved."""
    canonical_id = f"{prefix}{system}_{task_id}_r{repeat_no}"
    try:
        with get_session() as session:
            existing = session.query(Run).filter(Run.run_id == canonical_id).first()
            if not existing and not start_attempt:
                return canonical_id
            attempt = start_attempt if start_attempt is not None else 2
            while True:
                candidate = f"{canonical_id}_attempt{attempt}"
                if not session.query(Run).filter(Run.run_id == candidate).first():
                    return candidate
                attempt += 1
    except Exception:
        return canonical_id


def update_benchmark_manifest(
    records: List[Dict[str, Any]],
    manifest_path: Optional[str] = None,
    canonical_task_ids: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """Persistently updates the benchmark manifest with new run records."""
    target_path = manifest_path or MANIFEST_FILE
    manifest = load_benchmark_manifest(target_path)
    existing_runs = {r["run_id"]: r for r in manifest.get("runs", [])}

    for rec in records:
        run_id = rec["run_id"]
        existing_runs[run_id] = rec

    runs_list = list(existing_runs.values())

    # Map pairs by (task_id, repeat_no), prioritizing compliant COMPLETED LIVE_API runs (<= 60,000 tokens) over FAILED/STOPPED/SIMULATED
    by_pair: Dict[Any, Dict[str, Any]] = {}
    for r in runs_list:
        key = (r.get("task_id"), r.get("repeat_no"))
        s_name = r.get("system")
        if key not in by_pair:
            by_pair[key] = {}
        prev = by_pair[key].get(s_name)
        r_is_compliant = (
            r.get("status") in ("COMPLETED", "COMPLETED_QUALITY_GATE")
            and r.get("execution_mode") == "LIVE_API"
            and (r.get("tokens") or 0) <= 60000
        )
        prev_is_compliant = (
            prev is not None
            and prev.get("status") in ("COMPLETED", "COMPLETED_QUALITY_GATE")
            and prev.get("execution_mode") == "LIVE_API"
            and (prev.get("tokens") or 0) <= 60000
        )
        if prev is None:
            by_pair[key][s_name] = r
        elif not prev_is_compliant and r_is_compliant:
            by_pair[key][s_name] = r
        elif prev_is_compliant and r_is_compliant:
            prev_attempt = 1
            cur_attempt = 1
            if "_attempt" in prev.get("run_id", ""):
                try:
                    prev_attempt = int(prev.get("run_id", "").split("_attempt")[-1])
                except ValueError:
                    pass
            if "_attempt" in r.get("run_id", ""):
                try:
                    cur_attempt = int(r.get("run_id", "").split("_attempt")[-1])
                except ValueError:
                    pass
            if cur_attempt >= prev_attempt:
                by_pair[key][s_name] = r

    for r in runs_list:
        r["is_paired_complete"] = False
        r["paired_counterpart_run_id"] = None

    for key, sys_dict in by_pair.items():
        has_mas = (
            "mas" in sys_dict
            and sys_dict["mas"].get("status") in ("COMPLETED", "COMPLETED_QUALITY_GATE")
            and sys_dict["mas"].get("execution_mode") == "LIVE_API"
            and (sys_dict["mas"].get("tokens") or 0) <= 60000
        )
        has_cd = (
            "chatdev" in sys_dict
            and sys_dict["chatdev"].get("status") in ("COMPLETED", "COMPLETED_QUALITY_GATE")
            and sys_dict["chatdev"].get("execution_mode") == "LIVE_API"
            and (sys_dict["chatdev"].get("tokens") or 0) <= 60000
        )
        is_paired = has_mas and has_cd
        if is_paired:
            sys_dict["mas"]["is_paired_complete"] = True
            sys_dict["chatdev"]["is_paired_complete"] = True
            sys_dict["mas"]["paired_counterpart_run_id"] = sys_dict["chatdev"]["run_id"]
            sys_dict["chatdev"]["paired_counterpart_run_id"] = sys_dict["mas"]["run_id"]

    if canonical_task_ids is None:
        canonical_task_ids = set()
        is_production_manifest = (os.path.abspath(target_path) == os.path.abspath(MANIFEST_FILE))
        if is_production_manifest:
            tasks_file = os.path.abspath("eval/tasks.json")
            if os.path.exists(tasks_file):
                try:
                    with open(tasks_file, "r", encoding="utf-8") as tf:
                        tasks_data = json.load(tf)
                        canonical_task_ids = {t["task_id"] for t in tasks_data if "task_id" in t}
                except Exception:
                    pass

    paired_count = sum(
        1
        for k, v in by_pair.items()
        if (not canonical_task_ids or k[0] in canonical_task_ids)
        and "mas" in v
        and "chatdev" in v
        and v["mas"].get("status") in ("COMPLETED", "COMPLETED_QUALITY_GATE")
        and v["mas"].get("execution_mode") == "LIVE_API"
        and (v["mas"].get("tokens") or 0) <= 60000
        and v["chatdev"].get("status") in ("COMPLETED", "COMPLETED_QUALITY_GATE")
        and v["chatdev"].get("execution_mode") == "LIVE_API"
        and (v["chatdev"].get("tokens") or 0) <= 60000
    )
    mas_live_count = len({
        (r.get("task_id"), r.get("repeat_no"))
        for r in runs_list
        if (not canonical_task_ids or r.get("task_id") in canonical_task_ids)
        and r.get("system") == "mas"
        and r.get("status") in ("COMPLETED", "COMPLETED_QUALITY_GATE")
        and r.get("execution_mode") == "LIVE_API"
        and (r.get("tokens") or 0) <= 60000
    })
    cd_live_count = len({
        (r.get("task_id"), r.get("repeat_no"))
        for r in runs_list
        if (not canonical_task_ids or r.get("task_id") in canonical_task_ids)
        and r.get("system") == "chatdev"
        and r.get("status") in ("COMPLETED", "COMPLETED_QUALITY_GATE")
        and r.get("execution_mode") == "LIVE_API"
        and (r.get("tokens") or 0) <= 60000
    })
    sim_count = sum(
        1 for r in runs_list if r.get("status") == "SIMULATION_ONLY" or r.get("execution_mode") == "SIMULATED"
    )
    non_canonical_count = sum(
        1 for r in runs_list if canonical_task_ids and r.get("task_id") not in canonical_task_ids
    )

    manifest["last_updated_utc"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest["runs"] = runs_list
    manifest["summary"] = {
        "total_canonical_tasks": len(canonical_task_ids) or 20,
        "required_repeats": 3,
        "completed_paired_repeats": paired_count,
        "mas_completed_live_runs": mas_live_count,
        "chatdev_completed_live_runs": cd_live_count,
        "simulation_runs_excluded": sim_count,
        "non_canonical_test_runs_excluded": non_canonical_count,
        "semantics_note": "mas_completed_live_runs and chatdev_completed_live_runs strictly count COMPLETED live runs under canonical SRDD-20 task definitions within the 60,000 token cap. Failed, stopped, over-budget, simulated, and non-canonical test fixture runs are excluded.",
    }

    os.makedirs(os.path.dirname(target_path) or ".", exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return manifest


def start_proxy_daemon_if_needed(port: int = 8089):
    """Starts local logging proxy in a daemon thread if not already running."""
    import requests
    import threading
    try:
        r = requests.get(f"http://127.0.0.1:{port}/health", timeout=1)
        if r.status_code == 200:
            return
    except Exception:
        pass

    try:
        import uvicorn
        from mas.core.proxy import proxy_app

        def _serve():
            uvicorn.run(proxy_app, host="127.0.0.1", port=port, log_level="warning")

        t = threading.Thread(target=_serve, daemon=True)
        t.start()
        time.sleep(1.5)
    except Exception as e:
        print(f"[Proxy Warning] Could not start proxy daemon on port {port}: {e}")


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
        repeat_no: int = 1,
        task_id: Optional[str] = None,
        model: str = "fake",
        use_fake: bool = True,
        systems: Optional[List[str]] = None,
        benchmark_name: str = "srdd20",
        attempt: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Executes full benchmark evaluation across sampled SRDD tasks under identical conditions."""
        systems = systems or ["mas", "chatdev"]
        all_tasks = self.load_tasks()
        if task_id:
            tasks = [t for t in all_tasks if t.get("task_id") == task_id]
            if not tasks:
                raise ValueError(f"Task ID '{task_id}' not found in canonical tasks specification.")
        else:
            tasks = all_tasks[:task_count]

        print("\n" + "=" * 70)
        print(f"STARTING EMPIRICAL BENCHMARK: {benchmark_name.upper()}")
        print(f"Tasks: {len(tasks)} | Systems: {systems} | Repeats: {repeats} (Start Repeat: {repeat_no}) | Model: {model}")
        print("=" * 70)

        # Budget-aware governor check for live API runs
        if not use_fake:
            from mas.core.governor import ProviderQuotaGovernor
            governor = ProviderQuotaGovernor()
            stats = governor.get_ledger_stats()
            batch_pairs = len(tasks) * repeats
            min_required_attempts = min(32, 22 * batch_pairs) if ("mas" in systems and "chatdev" in systems) else min(16, 10 * batch_pairs)
            remaining = stats.get("remaining_internal_attempts", 0)
            if remaining < min_required_attempts:
                print(f"\n[GOVERNOR HALT] Insufficient remaining daily transmissions for benchmark batch:")
                print(f"  Current UTC date: {stats.get('utc_date')}")
                print(f"  Used attempts today: {stats.get('total_attributable_attempts')} / {stats.get('internal_daily_cap')}")
                print(f"  Remaining attempts: {remaining} (Minimum required with safety margin: {min_required_attempts})")
                print(f"  Execution safely stopped before ceiling breach.")
                print(f"  Scheduled next execution after UTC reset: 00:00:00 UTC")
                return {"status": "STOPPED_DAILY_CEILING", "stats": stats}

            if "chatdev" in systems:
                start_proxy_daemon_if_needed(port=8089)

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

            for r_num in range(repeat_no, repeat_no + repeats):
                prefix = "sim_" if use_fake else ""
                run_status = "SIMULATION_ONLY" if use_fake else "COMPLETED"
                exec_mode = "SIMULATED" if use_fake else "LIVE_API"
                prov_mode = "SIMULATED" if use_fake else "PROVIDER_REPORTED"

                # 1. Run MAS
                if "mas" in systems:
                    mas_run_id = resolve_attempt_run_id(prefix, "mas", t_id, r_num, start_attempt=attempt)
                    t_start = datetime.utcnow()
                    try:
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
                        mas_manifest = generate_artifacts_manifest(state["workspace_path"])
                        mas_cost = 0.0 if use_fake else totals["estimated_cost"]

                        st_status = state.get("status")
                        actual_mas_status = run_status
                        actual_mas_exec_mode = exec_mode
                        mas_failure_reason = None
                        if st_status in ("STOPPED_BUDGET_CEILING", "STOPPED_PROVIDER_QUOTA", "FAILED_INFRASTRUCTURE", "FAILED"):
                            actual_mas_status = st_status
                            actual_mas_exec_mode = st_status
                            mas_failure_reason = state.get("stop_reason")
                        elif not use_fake and tot_tok > 60000:
                            actual_mas_status = "STOPPED_BUDGET_CEILING"
                            actual_mas_exec_mode = "STOPPED_BUDGET_CEILING"
                            mas_failure_reason = f"TokenCapExceededError: Run exceeded token cap ({tot_tok} > 60000)"

                        with get_session() as session:
                            mas_row = session.query(Run).filter(Run.run_id == mas_run_id).first()
                            if mas_row:
                                mas_row.evaluation_id = eval_id
                                mas_row.status = actual_mas_status
                                mas_row.execution_mode = actual_mas_exec_mode
                                mas_row.token_provenance = prov_mode
                                mas_row.workspace_path = state["workspace_path"]
                                mas_row.artifacts_manifest = json.dumps(mas_manifest)
                                if mas_failure_reason and not mas_row.failure_reason:
                                    mas_row.failure_reason = mas_failure_reason
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
                                        execution_mode=actual_mas_exec_mode,
                                        token_provenance=prov_mode,
                                        workspace_path=state["workspace_path"],
                                        artifacts_manifest=json.dumps(mas_manifest),
                                        status=actual_mas_status,
                                        failure_reason=mas_failure_reason,
                                        started_at=t_start,
                                        finished_at=t_end,
                                    )
                                )
                            session.commit()

                        rec = {
                            "run_id": mas_run_id,
                            "task_id": t_id,
                            "task_name": t_name,
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
                            "cost": mas_cost,
                            "status": actual_mas_status,
                            "execution_mode": actual_mas_exec_mode,
                            "token_provenance": prov_mode,
                            "is_live_benchmark": not use_fake,
                            "timestamp_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                        }
                        if mas_failure_reason:
                            rec["error"] = mas_failure_reason
                        mas_records.append(rec)
                        all_records.append(rec)
                        mas_q_disp = f"{q:.4f}" if q is not None else "None"
                        mas_q1k_disp = f"{q1k:.4f}" if q1k is not None else "None"
                        print(f"   [{actual_mas_status}] MAS:     Quality={mas_q_disp} | Tokens={tot_tok} | Quality/1k={mas_q1k_disp}")

                    except Exception as exc:
                        t_end = datetime.utcnow()
                        print(f"   [FAILED] MAS: Runtime exception in {mas_run_id}: {exc}")
                        totals = token_logger.get_run_totals(mas_run_id)
                        tot_tok = totals.get("total_tokens", 0)
                        mas_cost = 0.0 if use_fake else totals.get("estimated_cost", 0.0)

                        with get_session() as session:
                            mas_row = session.query(Run).filter(Run.run_id == mas_run_id).first()
                            if mas_row:
                                mas_row.status = "FAILED"
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
                                        workspace_path=f"./eval/workspaces/{mas_run_id}",
                                        status="FAILED",
                                        started_at=t_start,
                                        finished_at=t_end,
                                    )
                                )
                            session.commit()

                        fail_rec = {
                            "run_id": mas_run_id,
                            "task_id": t_id,
                            "task_name": t_name,
                            "system": "mas",
                            "model": model,
                            "repeat_no": r_num,
                            "ablation": "A0",
                            "quality": None,
                            "quality_per_1k_tokens": None,
                            "completeness": None,
                            "executability": None,
                            "consistency": None,
                            "shared_test": None,
                            "ruff": None,
                            "bandit": None,
                            "radon": None,
                            "tokens": tot_tok,
                            "cost": mas_cost,
                            "status": "FAILED",
                            "execution_mode": exec_mode,
                            "token_provenance": prov_mode,
                            "is_live_benchmark": not use_fake,
                            "timestamp_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "error": str(exc),
                        }
                        mas_records.append(fail_rec)
                        all_records.append(fail_rec)

                # 2. Run ChatDev
                if "chatdev" in systems:
                    cd_run_id = resolve_attempt_run_id(prefix, "cd", t_id, r_num, start_attempt=attempt)
                    t_start = datetime.utcnow()
                    skip_cd = False
                    if not use_fake:
                        stats = governor.get_ledger_stats()
                        if stats.get("remaining_internal_attempts", 0) < 12:
                            print(f"   [GOVERNOR HALT] Insufficient remaining daily transmissions for ChatDev ({stats.get('remaining_internal_attempts', 0)} < 12). Skipping ChatDev run.")
                            skip_cd = True

                    if skip_cd:
                        rec = {
                            "run_id": cd_run_id,
                            "task_id": t_id,
                            "task_name": t_name,
                            "system": "chatdev",
                            "model": model,
                            "repeat_no": r_num,
                            "ablation": "A0",
                            "quality": None,
                            "quality_per_1k_tokens": None,
                            "completeness": None,
                            "executability": None,
                            "consistency": None,
                            "shared_test": None,
                            "ruff": None,
                            "bandit": None,
                            "radon": None,
                            "tokens": 0,
                            "cost": 0.0,
                            "status": "STOPPED_BUDGET_CEILING",
                            "execution_mode": exec_mode,
                            "token_provenance": prov_mode,
                            "is_live_benchmark": not use_fake,
                            "timestamp_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "error": "Governor quota ceiling threshold reached before ChatDev dispatch",
                        }
                        cd_records.append(rec)
                        all_records.append(rec)
                        print(f"   [SKIPPED] ChatDev: Halted by transmission governor")
                    else:
                        try:
                            cd_adapter = ChatDevAdapter(llm=llm, proxy_url="http://127.0.0.1:8089/v1")
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
                            cd_cost = 0.0 if use_fake else totals["estimated_cost"]

                            cd_status = cd_out.get("status")
                            actual_cd_status = run_status
                            actual_cd_exec_mode = exec_mode
                            cd_failure_reason = cd_out.get("failed_reason") or cd_out.get("stop_reason")

                            main_py_exists = os.path.exists(os.path.join(cd_out["workspace_dir"], "main.py"))

                            if cd_status in ("FAILED", "INCOMPLETE", "STOPPED_BUDGET_CEILING", "STOPPED_PROVIDER_QUOTA", "FAILED_INFRASTRUCTURE", "TIMEOUT"):
                                actual_cd_status = cd_status
                                actual_cd_exec_mode = cd_status
                            elif not main_py_exists:
                                actual_cd_status = "INCOMPLETE"
                                actual_cd_exec_mode = "INCOMPLETE"
                                cd_failure_reason = "Missing required artifact: main.py was not produced."
                            elif not use_fake and tot_tok > 60000:
                                actual_cd_status = "STOPPED_BUDGET_CEILING"
                                actual_cd_exec_mode = "STOPPED_BUDGET_CEILING"
                                cd_failure_reason = f"TokenCapExceededError: Run exceeded token cap ({tot_tok} > 60000)"
                            else:
                                actual_cd_status = run_status
                                actual_cd_exec_mode = exec_mode

                            with get_session() as session:
                                cd_row = session.query(Run).filter(Run.run_id == cd_run_id).first()
                                if cd_row:
                                    cd_row.evaluation_id = eval_id
                                    cd_row.status = actual_cd_status
                                    cd_row.execution_mode = actual_cd_exec_mode
                                    cd_row.token_provenance = prov_mode
                                    cd_row.workspace_path = cd_out["workspace_dir"]
                                    cd_row.artifacts_manifest = json.dumps(cd_manifest)
                                    if cd_failure_reason:
                                        cd_row.failure_reason = cd_failure_reason
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
                                            execution_mode=actual_cd_exec_mode,
                                            token_provenance=prov_mode,
                                            workspace_path=cd_out["workspace_dir"],
                                            artifacts_manifest=json.dumps(cd_manifest),
                                            status=actual_cd_status,
                                            failure_reason=cd_failure_reason,
                                            started_at=t_start,
                                            finished_at=t_end,
                                        )
                                    )
                                session.commit()

                            is_cd_success = actual_cd_status in ("COMPLETED", "COMPLETED_QUALITY_GATE")
                            rec = {
                                "run_id": cd_run_id,
                                "task_id": t_id,
                                "task_name": t_name,
                                "system": "chatdev",
                                "model": model,
                                "repeat_no": r_num,
                                "ablation": "A0",
                                "quality": q if is_cd_success else None,
                                "quality_per_1k_tokens": q1k if is_cd_success else None,
                                "completeness": cd_metrics["completeness"] if is_cd_success else None,
                                "executability": cd_metrics["executability"] if is_cd_success else None,
                                "consistency": cd_metrics["consistency"] if is_cd_success else None,
                                "shared_test": cd_metrics["shared_test"] if is_cd_success else None,
                                "ruff": cd_metrics["ruff_violations"] if is_cd_success else None,
                                "bandit": cd_metrics["bandit_high"] if is_cd_success else None,
                                "radon": cd_metrics["radon_mi"] if is_cd_success else None,
                                "tokens": tot_tok,
                                "cost": cd_cost,
                                "status": actual_cd_status,
                                "execution_mode": actual_cd_exec_mode,
                                "token_provenance": prov_mode,
                                "is_live_benchmark": not use_fake,
                                "timestamp_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                            }
                            if cd_failure_reason:
                                rec["error"] = cd_failure_reason
                            cd_records.append(rec)
                            all_records.append(rec)
                            cd_q_disp = f"{q:.4f}" if q is not None else "None"
                            cd_q1k_disp = f"{q1k:.4f}" if q1k is not None else "None"
                            print(f"   [{actual_cd_status}] ChatDev: Quality={cd_q_disp} | Tokens={tot_tok} | Quality/1k={cd_q1k_disp}")

                        except Exception as exc:
                            t_end = datetime.utcnow()
                            print(f"   [FAILED] ChatDev: Runtime exception in {cd_run_id}: {exc}")
                            totals = token_logger.get_run_totals(cd_run_id)
                            tot_tok = totals.get("total_tokens", 0)
                            cd_cost = 0.0 if use_fake else totals.get("estimated_cost", 0.0)

                            with get_session() as session:
                                cd_row = session.query(Run).filter(Run.run_id == cd_run_id).first()
                                if cd_row:
                                    cd_row.status = "FAILED"
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
                                            workspace_path=f"./eval/workspaces/{cd_run_id}",
                                            status="FAILED",
                                            started_at=t_start,
                                            finished_at=t_end,
                                        )
                                    )
                                session.commit()

                            fail_rec = {
                                "run_id": cd_run_id,
                                "task_id": t_id,
                                "task_name": t_name,
                                "system": "chatdev",
                                "model": model,
                                "repeat_no": r_num,
                                "ablation": "A0",
                                "quality": None,
                                "quality_per_1k_tokens": None,
                                "completeness": None,
                                "executability": None,
                                "consistency": None,
                                "shared_test": None,
                                "ruff": None,
                                "bandit": None,
                                "radon": None,
                                "tokens": tot_tok,
                                "cost": cd_cost,
                                "status": "FAILED",
                                "execution_mode": exec_mode,
                                "token_provenance": prov_mode,
                                "is_live_benchmark": not use_fake,
                                "timestamp_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                                "error": str(exc),
                            }
                            cd_records.append(fail_rec)
                            all_records.append(fail_rec)

        # Export CSV & Stats report & Update persistent manifest
        manifest = update_benchmark_manifest(all_records)
        export_results_csv(manifest.get("runs", []), self.results_path)
        generate_stats_markdown_report(
            [r for r in manifest.get("runs", []) if r.get("system") == "mas"],
            [r for r in manifest.get("runs", []) if r.get("system") == "chatdev"],
        )

        # Summary calculations
        mas_valid_q = [r["quality"] for r in mas_records if r.get("quality") is not None]
        cd_valid_q = [r["quality"] for r in cd_records if r.get("quality") is not None]
        mas_avg_q = sum(mas_valid_q) / len(mas_valid_q) if mas_valid_q else 0.0
        cd_avg_q = sum(cd_valid_q) / len(cd_valid_q) if cd_valid_q else 0.0
        mas_avg_tok = sum(r["tokens"] for r in mas_records) / len(mas_records) if mas_records else 0.0
        cd_avg_tok = sum(r["tokens"] for r in cd_records) / len(cd_records) if cd_records else 0.0

        print("\n" + "=" * 70)
        print("EMPIRICAL BENCHMARK BATCH COMPLETE — SUMMARY")
        print("=" * 70)
        print(f"MAS Quality:         {mas_avg_q:.4f}  (Tokens/task: {mas_avg_tok:,.1f})")
        print(f"ChatDev Quality:     {cd_avg_q:.4f}  (Tokens/task: {cd_avg_tok:,.1f})")
        print(f"iCoder (Published):  0.7924  (Tokens/task: 104,883.2)")
        print(f"Manifest Updated:    {MANIFEST_FILE} (Completed Paired Repeats: {manifest['summary']['completed_paired_repeats']})")
        print("-" * 70)
        if cd_avg_q > 0:
            gain_vs_cd = ((mas_avg_q - cd_avg_q) / cd_avg_q) * 100
            print(f"MAS Quality Difference vs ChatDev: {gain_vs_cd:+.1f}%")
        gain_vs_icoder = ((mas_avg_q - 0.7924) / 0.7924) * 100
        print(f"MAS Quality Difference vs iCoder:  {gain_vs_icoder:+.1f}%")
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
            "manifest_summary": manifest["summary"],
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
    parser.add_argument("--benchmark", action="store_true", help="Run benchmark across MAS and ChatDev")
    parser.add_argument("--reset", action="store_true", help="Wipe all existing database data and workspaces clean")
    parser.add_argument("--task-id", "--task", dest="task_id", type=str, default=None, help="Target a specific canonical task ID (e.g. srdd_educ_01)")
    parser.add_argument("--systems", "--system", dest="systems", type=str, default="mas,chatdev", help="Comma-separated systems to evaluate: mas,chatdev, or 'all'")
    parser.add_argument("--model", type=str, default="fake", help="Model condition (e.g. 'fake', 'cohere/north-mini-code:free', 'openai/gpt-4o')")
    parser.add_argument("--tasks", type=int, default=20, help="Number of benchmark tasks to run if task-id is omitted")
    parser.add_argument("--repeats", type=int, default=1, help="Repetitions per task")
    parser.add_argument("--repeat-no", type=int, default=1, help="Starting repeat number for execution")
    parser.add_argument("--attempt", type=int, default=None, help="Explicit attempt number override")
    parser.add_argument("--live", action="store_true", help="Explicitly declare live API execution mode")
    args = parser.parse_args()

    if args.reset:
        reset_environment()

    runner = EvaluationRunner()

    raw_systems = args.systems.strip().lower()
    if raw_systems in ("all", "both"):
        systems_list = ["mas", "chatdev"]
    else:
        systems_list = [s.strip().lower() for s in raw_systems.split(",") if s.strip()]

    use_fake = (args.model == "fake" and not args.live)

    if args.dry_run:
        runner.print_dry_run()
    elif args.pilot:
        runner.run_pilot(model=args.model, use_fake=use_fake)
    elif args.benchmark or args.task_id:
        runner.run_benchmark(
            task_count=args.tasks,
            repeats=args.repeats,
            repeat_no=args.repeat_no,
            task_id=args.task_id,
            model=args.model,
            use_fake=use_fake,
            systems=systems_list,
            attempt=args.attempt,
        )
    else:
        runner.print_dry_run()


if __name__ == "__main__":
    main()


