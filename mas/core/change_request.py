"""Requirement Change Request flow (LLD Sec 6.3 & 7.6)."""

import ast
import difflib
import os
import re
from typing import Any, Dict, List, Set, Tuple

from eval.neutral_evaluator import NeutralEvaluator
from eval.scorers.shared_test import SharedTestHarness
from mas.agents.architect import ArchitectAgent
from mas.agents.developer import DeveloperAgent
from mas.analysis.ast_analyzer import ASTAnalyzer
from mas.core.checkpoints import CheckpointManager
from mas.core.events import event_logger
from mas.core.llm import LLMProvider, token_logger
from mas.core.schemas import CodePatch
from mas.core.state import MASState
from mas.db.models import Run
from mas.db.session import get_session


class ChangeRequestManager:
    """Orchestrates requirement updates, AST impact propagation, and regression validation."""

    def __init__(self, llm: LLMProvider, ast_analyzer: ASTAnalyzer = None):
        self.llm = llm
        self.ast_analyzer = ast_analyzer or ASTAnalyzer()
        self.evaluator = NeutralEvaluator()
        self.shared_test = SharedTestHarness()

    def compute_requirement_diff(self, old_req: str, new_req: str) -> Dict[str, Any]:
        """Calculates textual and keyword differences between requirements."""
        old_words = set(re.findall(r"\w+", old_req.lower()))
        new_words = set(re.findall(r"\w+", new_req.lower()))

        added_terms = list(new_words - old_words)
        removed_terms = list(old_words - new_words)

        diff = difflib.unified_diff(
            old_req.splitlines(),
            new_req.splitlines(),
            fromfile="original_requirement",
            tofile="modified_requirement",
            lineterm="",
        )

        return {
            "diff_text": "\n".join(diff),
            "added_terms": added_terms,
            "removed_terms": removed_terms,
            "has_changes": len(added_terms) > 0 or len(removed_terms) > 0,
        }

    def detect_seed_modules(
        self,
        workspace_path: str,
        added_terms: List[str],
        removed_terms: List[str],
    ) -> List[str]:
        """Finds modules whose names, functions, or content match changed terms."""
        seeds = set()
        search_terms = set(added_terms + removed_terms)

        for root, _, files in os.walk(workspace_path):
            if any(x in root for x in [".git", "__pycache__", ".mas_snapshots"]):
                continue
            for f in files:
                if f.endswith(".py"):
                    mod_name = os.path.splitext(f)[0]
                    full_p = os.path.join(root, f)
                    try:
                        with open(full_p, "r", encoding="utf-8") as fh:
                            content = fh.read().lower()
                        if any(term in content or term in mod_name.lower() for term in search_terms):
                            seeds.add(mod_name)
                    except Exception:
                        pass

        # If no explicit term match, default to main module
        if not seeds:
            for root, _, files in os.walk(workspace_path):
                for f in files:
                    if f.endswith(".py"):
                        seeds.add(os.path.splitext(f)[0])
                        break

        return list(seeds)

    def detect_obsolete_code(self, workspace_path: str, removed_terms: List[str]) -> List[str]:
        """Detects functions or definitions related to removed requirement terms."""
        obsolete = []
        for root, _, files in os.walk(workspace_path):
            if any(x in root for x in [".git", "__pycache__", ".mas_snapshots"]):
                continue
            for f in files:
                if f.endswith(".py"):
                    full_p = os.path.join(root, f)
                    try:
                        with open(full_p, "r", encoding="utf-8") as fh:
                            tree = ast.parse(fh.read(), filename=full_p)
                        for node in ast.walk(tree):
                            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                if any(term in node.name.lower() for term in removed_terms):
                                    obsolete.append(f"{f}:{node.name}")
                    except Exception:
                        pass
        return obsolete

    def apply_change_request(
        self,
        run_id: str,
        new_requirement: str,
        workspace_path: str,
        old_requirement: str = "",
        task_id: str = "custom",
    ) -> Dict[str, Any]:
        """Executes full change-request flow."""
        abs_workspace = os.path.abspath(workspace_path)
        cp_mgr = CheckpointManager(abs_workspace)
        pre_change_cp = cp_mgr.save_checkpoint()

        event_logger.emit(
            run_id=run_id,
            agent="change_manager",
            event="requirement_changed",
            summary=f"Applying change request for run {run_id}",
        )

        # 1. Requirement diff
        diff_info = self.compute_requirement_diff(old_requirement, new_requirement)

        # 2. Build current AST graph
        ast_info = self.ast_analyzer.analyze_workspace(abs_workspace)
        graph = {k: set(v) for k, v in ast_info.get("dependency_graph", {}).items()}

        # 3. Identify seeds & compute impact set
        seeds = self.detect_seed_modules(abs_workspace, diff_info["added_terms"], diff_info["removed_terms"])
        impacted = self.ast_analyzer.compute_impact_set(graph, seeds)
        affected_modules = list(set(seeds) | impacted)

        # Map modules to filenames
        affected_files = [f"{m}.py" for m in affected_modules]

        # 4. Check obsolete code
        obsolete_detected = self.detect_obsolete_code(abs_workspace, diff_info["removed_terms"])

        # 5. Generate and apply updated patch for affected files
        dev = DeveloperAgent(llm=self.llm, checkpoint_manager=cp_mgr)
        state_mock: MASState = {
            "run_id": run_id,
            "requirement": new_requirement,
            "changed_files": affected_files,
            "iteration": 2,
            "workspace_path": abs_workspace,
            "artifacts": {},
        }
        state_updated = dev.run(state_mock)

        # 6. Run regression tests
        reg_test = self.shared_test.evaluate(abs_workspace, task_id=task_id)

        # 7. Final neutral evaluation
        final_metrics = self.evaluator.evaluate_project(
            workspace_path=abs_workspace,
            requirement=new_requirement,
            task_id=task_id,
            run_id=run_id,
        )

        totals = token_logger.get_run_totals(run_id)

        result = {
            "update_success": True,
            "diff_summary": diff_info["diff_text"][:200],
            "seeds": seeds,
            "affected_modules": affected_modules,
            "affected_files": affected_files,
            "obsolete_code_detected": obsolete_detected,
            "regression_score": reg_test["score"],
            "final_quality": final_metrics["quality"],
            "total_tokens": totals["total_tokens"],
            "pre_change_checkpoint": pre_change_cp,
        }

        event_logger.emit(
            run_id=run_id,
            agent="change_manager",
            event="agent_completed",
            summary=(
                f"Change applied: {len(affected_files)} files updated. "
                f"Regression: {reg_test['score']}, Final Quality: {final_metrics['quality']:.3f}"
            ),
        )

        return result
