"""Context slicing module: extracts minimal changed files, AST impact set, and sliced UML."""

import os
from typing import Any, Dict, List, Set

from mas.agents.architect import ArchitectAgent
from mas.analysis.ast_analyzer import ASTAnalyzer
from mas.core.state import MASState


class ContextSlicer:
    """Builds token-efficient sliced context for Developer in iterative loops."""

    def __init__(self, ast_analyzer: ASTAnalyzer = None):
        self.ast_analyzer = ast_analyzer or ASTAnalyzer()

    def get_sliced_files(
        self,
        state: MASState,
        all_workspace_files: Dict[str, str],
        dependency_graph: Dict[str, Set[str]],
    ) -> Dict[str, str]:
        """Returns only the sliced file contents rather than the full repository."""
        iteration = state.get("iteration", 1)

        # Iteration 1: return files initially planned by task plan or present files
        if iteration <= 1:
            task_files = state.get("artifacts", {}).get("TaskPlan", {}).get("files", [])
            if task_files:
                return {f: all_workspace_files[f] for f in task_files if f in all_workspace_files}
            return all_workspace_files

        # Iteration > 1: changed_files UNION AST impact set
        changed = state.get("changed_files", [])
        changed_modules = [os.path.splitext(os.path.basename(f))[0] for f in changed]

        impacted_modules = self.ast_analyzer.compute_impact_set(dependency_graph, changed_modules)
        target_modules = set(changed_modules) | impacted_modules

        sliced: Dict[str, str] = {}
        for f, content in all_workspace_files.items():
            mod = os.path.splitext(os.path.basename(f))[0]
            if mod in target_modules or f in changed:
                sliced[f] = content

        return sliced if sliced else all_workspace_files

    def build_context(
        self,
        state: MASState,
        all_workspace_files: Dict[str, str],
        dependency_graph: Dict[str, Set[str]],
    ) -> Dict[str, Any]:
        """Assembles token-efficient payload for Developer prompt."""
        sliced_files = self.get_sliced_files(state, all_workspace_files, dependency_graph)

        relevant_uml = []
        if state.get("complexity") == "STRUCTURED" and state.get("architecture"):
            arch_agent = ArchitectAgent(llm=None)
            relevant_uml = arch_agent.slice_uml(state["architecture"], list(sliced_files.keys()))

        findings = state.get("review_report", {}).get("findings", [])
        plan = state.get("artifacts", {}).get("TaskPlan", {})
        acceptance_criteria = plan.get("acceptance_criteria", [])

        return {
            "task": state.get("requirement", ""),
            "acceptance_criteria": acceptance_criteria,
            "iteration": state.get("iteration", 1),
            "files": sliced_files,
            "relevant_uml": relevant_uml,
            "review_findings": findings,
            "changed_files_count": len(state.get("changed_files", [])),
            "sliced_files_count": len(sliced_files),
            "total_files_in_repo": len(all_workspace_files),
        }
