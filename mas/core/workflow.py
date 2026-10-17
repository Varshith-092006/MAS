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
    ):
        self.llm = llm
        self.config_path = config_path
        self.validator = SchemaValidator()
        self.router = ComplexityRouter(threshold=4)
        self.ast_analyzer = ASTAnalyzer()
        init_db(db_engine)

    def run(
        self,
        requirement: str,
        task_id: str = "custom",
        model_name: Optional[str] = None,
        run_id: Optional[str] = None,
        workspace_base: str = "./workspace",
    ) -> MASState:
        """Executes full end-to-end MAS workflow."""
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

            # 2. Architect Agent (STRUCTURED path only)
            if complexity == "STRUCTURED":
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
            )
            reflection = ReflectionAgent(
                llm=self.llm,
                config_path=self.config_path,
                validator=self.validator,
                checkpoint_manager=checkpoint_mgr,
            )
            from mas.core.context import ContextSlicer
            context_slicer = ContextSlicer(ast_analyzer=self.ast_analyzer)

            max_iterations = reflection.stopper.max_iterations

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

                sliced_context = context_slicer.build_context(state, workspace_files, set_graph)
                state["relevant_uml"] = sliced_context["relevant_uml"]

                # Developer generates CodePatch & applies to workspace
                state = dev.run(state)

                # Deterministic AST structural analysis
                ast_rep = self.ast_analyzer.analyze_workspace(workspace_path)
                state["ast_report"] = ast_rep
                event_logger.emit(
                    run_id=run_id,
                    agent="ast",
                    event="agent_completed",
                    summary=f"AST Analysis: {ast_rep['module_count']} modules, {len(ast_rep['cycles'])} cycles",
                )

                # Static quality analysis (Ruff, Bandit, Radon)
                q_rep = QualityTools.run_all(workspace_path)
                state["quality_report"] = q_rep

                # Internal MAS pytest diagnostics & sandbox execution
                state = tester.run(state)

                # Semantic review examining code, static analysis, and test outcomes
                state = reviewer.run(state)

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
