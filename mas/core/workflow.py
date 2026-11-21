"""Workflow orchestrator implementing the MAS execution graph and adaptive loop."""

from datetime import datetime
import os
from typing import Optional
import uuid

from mas.agents.manager import ManagerAgent
from mas.agents.router import ComplexityRouter
from mas.agents.architect import ArchitectAgent
from mas.agents.developer import DeveloperAgent
from mas.agents.tester import TesterAgent
from mas.agents.reviewer import ReviewerAgent
from mas.agents.reflection import ReflectionAgent
from mas.analysis.ast_analyzer import ASTAnalyzer
from mas.analysis.quality_tools import QualityTools
from mas.core.checkpoints import CheckpointManager
from mas.core.events import event_logger
from mas.core.llm import (
    LLMProvider,
    FakeLLMProvider,
    token_logger,
    TokenCapExceededError,
    DispatchCeilingExceededError,
    DailyTransmissionsCeilingExceededError,
    ModelMismatchError,
    OpenRouterAPIError,
    resolve_openrouter_model,
)
from mas.core.state import MASState, create_initial_state
from mas.core.validator import SchemaValidator
from mas.db.models import Run, ConfigSnapshot
from mas.db.session import get_session, init_db


import json

def generate_artifacts_manifest(workspace_dir: str):
    """Generates an auditable manifest of files created in the workspace with SHA256 hashes."""
    if not os.path.exists(workspace_dir):
        return []
    manifest = []
    import hashlib
    for root, _, files in os.walk(workspace_dir):
        if any(x in root for x in [".git", "__pycache__", ".mas_snapshots"]):
            continue
        for fn in sorted(files):
            full_path = os.path.join(root, fn)
            rel_path = os.path.relpath(full_path, workspace_dir).replace("\\", "/")
            try:
                sz = os.path.getsize(full_path)
                mtime = os.path.getmtime(full_path)
                with open(full_path, "rb") as fh:
                    sha = hashlib.sha256(fh.read()).hexdigest()
                ext = os.path.splitext(fn)[1].lower()
                f_type = "code" if ext in [".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css"] else ("config" if ext in [".json", ".yaml", ".yml", ".toml", ".ini"] else "text")
                manifest.append({
                    "name": fn,
                    "path": rel_path,
                    "size": sz,
                    "type": f_type,
                    "hash": sha,
                    "mtime": mtime,
                })
            except Exception:
                pass
    return manifest


class MASWorkflow:
    """Orchestrates MAS multi-agent software engineering execution."""

    def __init__(
        self,
        llm: LLMProvider,
        config_path: str = "config.yaml",
        db_engine=None,
        ablation: Optional[str] = None,
    ):
        self.llm = llm
        self.config_path = config_path
        self.validator = SchemaValidator()
        self.router = ComplexityRouter(threshold=4)
        self.ast_analyzer = ASTAnalyzer()
        self.ablation = ablation
        init_db(db_engine)

    def run(
        self,
        requirement: str,
        task_id: str = "custom",
        model_name: Optional[str] = None,
        run_id: Optional[str] = None,
        workspace_base: str = "./workspace",
        ablation: Optional[str] = None,
    ) -> MASState:
        """Executes full end-to-end MAS workflow."""
        from mas.core.config import get_config
        cfg = get_config(self.config_path) if self.config_path else {}
        cfg_ablation = cfg.get("ablation", {}) if isinstance(cfg, dict) else {}
        active_ablation = (
            ablation
            or self.ablation
            or cfg_ablation.get("current")
            or "A0"
        )
        a1_disable_router = (active_ablation == "A1") or cfg_ablation.get("a1_disable_router", False)
        a2_disable_slicing = (active_ablation == "A2") or cfg_ablation.get("a2_disable_slicing", False)
        a3_disable_grounded_review = (active_ablation == "A3") or cfg_ablation.get("a3_disable_grounded_review", False)
        a4_single_iteration = (active_ablation == "A4") or cfg_ablation.get("a4_single_iteration", False)

        model_name = model_name or os.environ.get("OPENROUTER_MODEL", "cohere/north-mini-code:free")
        run_id = run_id or str(uuid.uuid4())
        workspace_path = os.path.abspath(os.path.join(workspace_base, run_id))
        os.makedirs(workspace_path, exist_ok=True)

        is_simulated = (model_name == "fake" or isinstance(self.llm, FakeLLMProvider))
        exec_mode = "SIMULATED" if is_simulated else "LIVE_API"
        token_prov = "SIMULATED" if is_simulated else "UNAVAILABLE"

        if hasattr(self.llm, "default_model") and not is_simulated:
            self.llm.default_model = resolve_openrouter_model(model_name)

        state = create_initial_state(
            run_id=run_id,
            requirement=requirement,
            task_id=task_id,
            workspace_path=workspace_path,
            model=model_name,
        )
        state["ablation"] = active_ablation

        checkpoint_mgr = CheckpointManager(workspace_path)

        # Initialize DB Run record
        with get_session() as session:
            existing_run = session.query(Run).filter(Run.run_id == run_id).first()
            if existing_run:
                existing_run.status = "RUNNING"
                existing_run.started_at = datetime.utcnow()
                existing_run.task_id = task_id if task_id != "custom" else None
                existing_run.model = model_name
                existing_run.execution_mode = exec_mode
                existing_run.token_provenance = token_prov
                existing_run.workspace_path = workspace_path
            else:
                db_run = Run(
                    run_id=run_id,
                    task_id=task_id if task_id != "custom" else None,
                    system="mas",
                    model=model_name,
                    actual_model=model_name,
                    execution_mode=exec_mode,
                    token_provenance=token_prov,
                    workspace_path=workspace_path,
                    seed=42,
                    status="RUNNING",
                    started_at=datetime.utcnow(),
                )
                session.add(db_run)
            session.commit()

        event_logger.emit(
            run_id=run_id,
            agent="system",
            event="run_started",
            summary=f"Run {run_id} started with model={model_name}, task={task_id}",
        )

        try:
            # 1. Manager Agent & Complexity Routing
            mgr = ManagerAgent(
                llm=self.llm,
                router=self.router,
                validator=self.validator,
                checkpoint_manager=checkpoint_mgr,
            )
            state = mgr.run(state)

            complexity = state.get("complexity", "SIMPLE")

            # 2. Architect Agent (STRUCTURED path, or always if Ablation A1)
            if complexity == "STRUCTURED" or a1_disable_router:
                architect = ArchitectAgent(
                    llm=self.llm,
                    validator=self.validator,
                    checkpoint_manager=checkpoint_mgr,
                )
                state = architect.run(state)

            # Iterative Loop
            dev = DeveloperAgent(
                llm=self.llm,
                validator=self.validator,
                checkpoint_manager=checkpoint_mgr,
            )
            tester = TesterAgent(
                llm=self.llm,
                validator=self.validator,
                checkpoint_manager=checkpoint_mgr,
            )
            reviewer = ReviewerAgent(
                llm=self.llm,
                validator=self.validator,
                checkpoint_manager=checkpoint_mgr,
                disable_grounded_review=a3_disable_grounded_review,
            )
            reflection = ReflectionAgent(
                llm=self.llm,
                config_path=self.config_path,
                validator=self.validator,
                checkpoint_manager=checkpoint_mgr,
            )
            from mas.core.context import ContextSlicer
            context_slicer = ContextSlicer(ast_analyzer=self.ast_analyzer)

            # Ablation A4: no reflection loop (one iteration only)
            max_iterations = 1 if a4_single_iteration else reflection.stopper.max_iterations

            while state.get("iteration", 1) <= max_iterations:
                curr_iter = state.get("iteration", 1)

                # Context slicing: if iteration > 1, slice files using changed_files UNION AST impact set
                dep_graph = state.get("ast_report", {}).get("dependency_graph", {})
                set_graph = {k: set(v) for k, v in dep_graph.items()}

                # Read current workspace files
                workspace_files = {}
                for root, _, fnames in os.walk(workspace_path):
                    if any(x in root for x in [".git", "__pycache__", ".mas_snapshots"]):
                        continue
                    for fn in fnames:
                        if fn.endswith(".py"):
                            full_fp = os.path.join(root, fn)
                            rel_fp = os.path.relpath(full_fp, workspace_path)
                            try:
                                with open(full_fp, "r", encoding="utf-8") as fhh:
                                    workspace_files[rel_fp] = fhh.read()
                            except Exception:
                                pass

                sliced_context = context_slicer.build_context(
                    state, workspace_files, set_graph, disable_slicing=a2_disable_slicing
                )
                state["relevant_uml"] = sliced_context["relevant_uml"]

                # Developer generates CodePatch & applies to workspace
                state = dev.run(state)

                # Deterministic repair before extra LLM call (Change 3)
                det_repair_cfg = cfg.get("quality_improvements", {}).get("deterministic_repair", True)
                from mas.analysis.deterministic_checker import DeterministicRepairChecker
                det_errors = DeterministicRepairChecker.run_checks(workspace_path)
                if det_errors and det_repair_cfg:
                    event_logger.emit(
                        run_id=run_id,
                        agent="developer",
                        event="deterministic_repair_requested",
                        summary=f"Found {len(det_errors)} deterministic defects; dispatching 1 targeted repair",
                    )
                    state = dev.targeted_repair(state, det_errors)
                    det_errors = DeterministicRepairChecker.run_checks(workspace_path)

                # Deterministic AST structural analysis
                ast_rep = self.ast_analyzer.analyze_workspace(workspace_path)
                state["ast_report"] = ast_rep
                event_logger.emit(
                    run_id=run_id,
                    agent="ast",
                    event="agent_completed",
                    summary=f"AST Analysis: {ast_rep['module_count']} modules, {len(ast_rep['cycles'])} cycles",
                )

                # Reverse-architecture conformance (design vs built code), STRUCTURED path only
                arch_art = state.get("artifacts", {}).get("Architecture")
                if arch_art:
                    from mas.analysis.conformance import check_conformance
                    conf = check_conformance(arch_art, workspace_path)
                    state["conformance_report"] = conf
                    if conf.get("applicable"):
                        event_logger.emit(
                            run_id=run_id,
                            agent="ast",
                            event="conformance_checked",
                            summary=f"Design conformance {conf['conformance_score']:.2f}; deviations: {len(conf['findings'])}",
                        )

                # Static quality analysis (Ruff, Bandit, Radon)
                q_rep = QualityTools.run_all(workspace_path)
                state["quality_report"] = q_rep

                # Internal MAS pytest diagnostics & sandbox execution
                state = tester.run(state)

                # Semantic review: skip unnecessary LLM review if clean (Change 4)
                skip_review_cfg = cfg.get("quality_improvements", {}).get("skip_unnecessary_review", True)
                test_rep = state.get("mas_pytest_report", {})
                smoke_exec = state.get("sandbox_execution", {})
                is_clean = (
                    not det_errors
                    and smoke_exec.get("is_success", False)
                    and q_rep.get("bandit", {}).get("high", 0) == 0
                    and test_rep.get("pass_rate", 0.0) == 1.0
                    and test_rep.get("failed_tests", 0) == 0
                )

                # Phase 8: the Tester is now deterministic (0 LLM calls), so "clean" no longer
                # implies the requirement is met. The semantic review therefore always runs at
                # least once; it is skipped only when an earlier review already PASSED and the
                # code is still clean (saves the call on later iterations without losing review).
                prev_review_passed = bool(state.get("review_passed_once", False))
                deterministic_tester = getattr(tester, "mode", "llm") == "deterministic"
                can_skip = is_clean and (prev_review_passed or not deterministic_tester)
                if can_skip and skip_review_cfg and not a3_disable_grounded_review and active_ablation != "A3":
                    state["review_report"] = {
                        "status": "PASSED",
                        "critical_issues": 0,
                        "major_issues": 0,
                        "minor_issues": 0,
                        "findings": [],
                        "summary": "Deterministic checks, smoke run, and internal tests all passed clean; skipped LLM review.",
                    }
                    state["artifacts"]["ReviewReport"] = state["review_report"]
                    event_logger.emit(
                        run_id=run_id,
                        agent="reviewer",
                        event="call_skipped",
                        summary="Reviewer LLM call skipped: all deterministic checks and tests passed clean",
                    )
                else:
                    state = reviewer.run(state)
                    if state.get("review_report", {}).get("status") == "PASSED":
                        state["review_passed_once"] = True

                # Reflection & Adaptive Stopper
                state = reflection.run(state)

                decision = state.get("artifacts", {}).get("ReflectionDecision", {}).get("decision", "STOP")

                if decision == "STOP":
                    break
                else:
                    state["iteration"] = curr_iter + 1

            # Determine final status distinguishing quality gate from iteration limit and infrastructure failure
            final_decision = state.get("artifacts", {}).get("ReflectionDecision", {})
            stop_reason = str(final_decision.get("reason", state.get("stop_reason", "")))
            last_review = state.get("review_report", {})
            last_crit = last_review.get("critical_issues", 0)
            last_status = last_review.get("status", "")
            sandbox_exec = state.get("sandbox_execution", {})
            sandbox_ok = sandbox_exec.get("is_success", False) if "is_success" in sandbox_exec else True

            has_open_findings = (last_crit > 0 or last_status in ("FAILED", "NEEDS_REVISION") or not sandbox_ok)

            if not has_open_findings and stop_reason.startswith("clean_result"):
                final_status = "COMPLETED_QUALITY_GATE"
                state["quality_gate_passed"] = True
            elif "max_iterations" in stop_reason or "marginal_gain" in stop_reason or has_open_findings:
                final_status = "STOPPED_MAX_ITERATIONS_WITH_OPEN_FINDINGS"
                state["quality_gate_passed"] = False
            else:
                final_status = "COMPLETED_QUALITY_GATE"
                state["quality_gate_passed"] = True

            state["status"] = final_status
            totals = token_logger.get_run_totals(run_id)
            state["input_tokens"] = totals["input_tokens"]
            state["output_tokens"] = totals["output_tokens"]
            state["total_tokens"] = totals["total_tokens"]
            state["estimated_cost"] = totals["estimated_cost"]

            manifest = generate_artifacts_manifest(workspace_path)

            with get_session() as session:
                run_row = session.query(Run).filter(Run.run_id == run_id).first()
                if run_row:
                    run_row.status = final_status
                    run_row.finished_at = datetime.utcnow()
                    run_row.workspace_path = workspace_path
                    run_row.artifacts_manifest = json.dumps(manifest)
                    if not run_row.execution_mode:
                        run_row.execution_mode = exec_mode
                    if not run_row.token_provenance:
                        run_row.token_provenance = "SIMULATED" if is_simulated else ("PROVIDER_REPORTED" if totals["total_tokens"] > 0 else "UNAVAILABLE")
                    session.commit()

            event_logger.emit(
                run_id=run_id,
                agent="system",
                event="run_completed",
                summary=(
                    f"Run {run_id} finished with status {final_status}. Tokens: {totals['total_tokens']}, "
                    f"Cost: ${totals['estimated_cost']:.4f}, Files: {len(manifest)}, Stop reason: {state.get('stop_reason')}"
                ),
            )

        except ModelMismatchError as e:
            state["status"] = "FAILED"
            state["stop_reason"] = "MODEL_MISMATCH_DIAGNOSTIC"
            with get_session() as session:
                run_row = session.query(Run).filter(Run.run_id == run_id).first()
                if run_row:
                    run_row.status = "MODEL_MISMATCH_DIAGNOSTIC"
                    run_row.failure_reason = f"MODEL_MISMATCH_DIAGNOSTIC: {str(e)}"
                    run_row.execution_mode = "FAILED"
                    run_row.finished_at = datetime.utcnow()
                    session.commit()
            event_logger.emit(
                run_id=run_id,
                agent="system",
                event="run_failed",
                status="failure",
                summary=f"Run {run_id} failed: MODEL_MISMATCH_DIAGNOSTIC ({str(e)})",
            )
            raise
        except (TokenCapExceededError, DispatchCeilingExceededError, DailyTransmissionsCeilingExceededError) as e:
            err_type = type(e).__name__
            state["status"] = "STOPPED_BUDGET_CEILING"
            state["stop_reason"] = err_type
            with get_session() as session:
                run_row = session.query(Run).filter(Run.run_id == run_id).first()
                if run_row:
                    run_row.status = "STOPPED_BUDGET_CEILING"
                    run_row.failure_reason = f"{err_type}: {str(e)}"
                    run_row.execution_mode = "STOPPED_BUDGET_CEILING"
                    run_row.finished_at = datetime.utcnow()
                    session.commit()
            event_logger.emit(
                run_id=run_id,
                agent="system",
                event="run_stopped_budget_ceiling",
                status="failure",
                summary=f"Run {run_id} checkpointed safely: {err_type} ({str(e)})",
            )
        except OpenRouterAPIError as e:
            if e.is_daily_quota_exhausted:
                err_type = "PROVIDER_DAILY_QUOTA_EXHAUSTED"
                terminal_status = "STOPPED_PROVIDER_QUOTA"
                event_name = "run_stopped_provider_quota"
            elif e.status_code == 429:
                err_type = "RATE_LIMIT_429"
                terminal_status = "STOPPED_BUDGET_CEILING"
                event_name = "run_stopped_rate_limit"
            elif e.status_code >= 500:
                err_type = f"OPENROUTER_SERVER_ERROR_{e.status_code}"
                terminal_status = "FAILED_INFRASTRUCTURE"
                event_name = "run_failed_infrastructure"
            else:
                err_type = f"OPENROUTER_ERROR_{e.status_code}"
                terminal_status = "FAILED"
                event_name = "run_failed"

            state["status"] = terminal_status
            state["stop_reason"] = f"{err_type}: {e.error_message or str(e)}"
            with get_session() as session:
                run_row = session.query(Run).filter(Run.run_id == run_id).first()
                if run_row:
                    run_row.status = terminal_status
                    run_row.failure_reason = f"{err_type}: {str(e)}"
                    run_row.execution_mode = terminal_status
                    run_row.finished_at = datetime.utcnow()
                    session.commit()
            event_logger.emit(
                run_id=run_id,
                agent="system",
                event=event_name,
                status="failure",
                summary=f"Run {run_id} halted: {err_type} ({str(e)})",
            )
        except Exception as e:
            is_infra = any(term in type(e).__name__.lower() for term in ("connect", "timeout", "network", "socket"))
            terminal_status = "FAILED_INFRASTRUCTURE" if is_infra else "FAILED"
            state["status"] = terminal_status
            state["stop_reason"] = f"ERROR: {str(e)}"
            with get_session() as session:
                run_row = session.query(Run).filter(Run.run_id == run_id).first()
                if run_row:
                    run_row.status = terminal_status
                    run_row.failure_reason = str(e)
                    run_row.execution_mode = terminal_status
                    run_row.finished_at = datetime.utcnow()
                    session.commit()
            event_logger.emit(
                run_id=run_id,
                agent="system",
                event="run_failed",
                status="failure",
                summary=f"Run {run_id} failed with error: {str(e)}",
            )
            raise

        return state
