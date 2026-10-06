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
from mas.core.llm import LLMProvider, token_logger, TokenCapExceededError
from mas.core.state import MASState, create_initial_state
from mas.core.validator import SchemaValidator
from mas.db.models import Run, ConfigSnapshot
from mas.db.session import get_session, init_db


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
        model_name: str = "gpt-4o",
        run_id: Optional[str] = None,
        workspace_base: str = "./workspace",
    ) -> MASState:
        """Executes full end-to-end MAS workflow."""
        run_id = run_id or str(uuid.uuid4())
        workspace_path = os.path.abspath(os.path.join(workspace_base, run_id))
        os.makedirs(workspace_path, exist_ok=True)

        state = create_initial_state(
            run_id=run_id,
            requirement=requirement,
            task_id=task_id,
            workspace_path=workspace_path,
        )

        checkpoint_mgr = CheckpointManager(workspace_path)

        # Initialize DB Run record
        with get_session() as session:
            db_run = Run(
                run_id=run_id,
                task_id=task_id if task_id != "custom" else None,
                system="mas",
                model=model_name,
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

                # Internal MAS pytest diagnostics
                state = tester.run(state)

                # Static quality analysis (Ruff, Bandit, Radon)
                q_rep = QualityTools.run_all(workspace_path)
                state["quality_report"] = q_rep

                # Semantic review using cheap model (GPT-4o-mini)
                state = reviewer.run(state)

                # Reflection & Adaptive Stopper
                state = reflection.run(state)

                decision = state.get("artifacts", {}).get("ReflectionDecision", {}).get("decision", "STOP")

                if decision == "STOP":
                    break
                else:
                    state["iteration"] = curr_iter + 1

            # Run completed successfully
            state["status"] = "COMPLETED"
            totals = token_logger.get_run_totals(run_id)
            state["input_tokens"] = totals["input_tokens"]
            state["output_tokens"] = totals["output_tokens"]
            state["total_tokens"] = totals["total_tokens"]
            state["estimated_cost"] = totals["estimated_cost"]

            with get_session() as session:
                run_row = session.query(Run).filter(Run.run_id == run_id).first()
                if run_row:
                    run_row.status = "COMPLETED"
                    run_row.finished_at = datetime.utcnow()
                    session.commit()

            event_logger.emit(
                run_id=run_id,
                agent="system",
                event="run_completed",
                summary=(
                    f"Run {run_id} COMPLETED. Tokens: {totals['total_tokens']}, "
                    f"Cost: ${totals['estimated_cost']:.4f}, Stop reason: {state.get('stop_reason')}"
                ),
            )

        except TokenCapExceededError as e:
            state["status"] = "FAILED"
            state["stop_reason"] = "TOKEN_CAP_EXCEEDED"
            with get_session() as session:
                run_row = session.query(Run).filter(Run.run_id == run_id).first()
                if run_row:
                    run_row.status = "FAILED"
                    run_row.finished_at = datetime.utcnow()
                    session.commit()
            event_logger.emit(
                run_id=run_id,
                agent="system",
                event="run_failed",
                status="failure",
                summary=f"Run {run_id} failed: TOKEN_CAP_EXCEEDED ({str(e)})",
            )
        except Exception as e:
            state["status"] = "FAILED"
            state["stop_reason"] = f"ERROR: {str(e)}"
            with get_session() as session:
                run_row = session.query(Run).filter(Run.run_id == run_id).first()
                if run_row:
                    run_row.status = "FAILED"
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
