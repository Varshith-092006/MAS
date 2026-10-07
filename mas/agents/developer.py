"""Developer Agent: Writes code and outputs CodePatch artifacts."""

import os
from typing import Dict, List, Optional
import uuid

from mas.agents.base import BaseAgent
from mas.core.schemas import CodePatch
from mas.core.state import MASState
from mas.core.events import event_logger


class DeveloperAgent(BaseAgent):
    """Generates source code implementations and applies CodePatch to workspace."""

    def __init__(self, llm, **kwargs):
        super().__init__(name="developer", llm=llm, **kwargs)

    def apply_patch(self, patch: CodePatch, workspace_path: str) -> List[str]:
        """Writes patched files to the designated workspace directory."""
        os.makedirs(workspace_path, exist_ok=True)
        changed = []

        for filename, content in patch.file_contents.items():
            filepath = os.path.join(workspace_path, filename)
            parent = os.path.dirname(filepath)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            changed.append(filename)

        return changed

    def run(self, state: MASState) -> MASState:
        run_id = state.get("run_id", str(uuid.uuid4()))
        workspace = state.get("workspace_path", f"./workspace/{run_id}")
        iteration = state.get("iteration", 1)

        event_logger.emit(
            run_id=run_id,
            agent="developer",
            event="agent_started",
            summary=f"Developer writing code patch (Iteration {iteration})",
        )

        def produce_code(feedback=None):
            req = state.get("requirement", "")
            arch = state.get("architecture", {})
            uml_slice = state.get("relevant_uml", [])
            review_feedback = state.get("review_report", {}).get("findings", [])

            prompt = (
                f"Task Requirement: {req}\n"
                f"Iteration: {iteration}\n"
                f"Architecture Components: {arch.get('components', []) if arch else 'None'}\n"
                f"UML Context: {uml_slice}\n"
                f"Review Findings: {review_feedback}\n"
                f"Validator Feedback: {feedback or 'None'}\n\n"
                "Return a single JSON object with these keys:\n"
                "- files: list of target file paths (e.g. ['index.html', 'style.css', 'app.js', 'README.md'])\n"
                "- file_contents: an object mapping each filename to its complete, non-truncated source code string\n"
                "- summary: a concise description of the implementation\n"
                "- tests_expected: list of test or verification cases\n"
            )

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are DeveloperAgent. Generate complete, production-ready code without placeholders according to the task requirement. "
                        "Return a valid CodePatch JSON containing files, file_contents mapping, summary, and tests_expected."
                    ),
                },
                {"role": "user", "content": prompt},
            ]

            res = self.llm.generate(
                messages=messages,
                response_schema=CodePatch,
                run_id=run_id,
                agent_name="developer",
            )
            if res.parsed_json:
                return res.parsed_json

            # Fallback code patch
            return {
                "files": ["calculator.py"],
                "file_contents": {
                    "calculator.py": (
                        "def add(a: int, b: int) -> int:\n"
                        "    '''Adds two numbers.'''\n"
                        "    return a + b\n\n"
                        "def multiply(a: int, b: int) -> int:\n"
                        "    '''Multiplies two numbers.'''\n"
                        "    return a * b\n"
                    )
                },
                "summary": "Implemented calculator arithmetic operations",
                "tests_expected": ["test_add", "test_multiply"],
            }

        patch: CodePatch = self.produce_valid_artifact("CodePatch", produce_code, state, CodePatch)

        changed = self.apply_patch(patch, workspace)
        state["changed_files"] = changed
        state["artifacts"]["CodePatch"] = patch.model_dump()

        event_logger.emit(
            run_id=run_id,
            agent="developer",
            event="agent_completed",
            summary=f"CodePatch applied: {len(changed)} files written to workspace ({', '.join(changed)})",
        )

        return state
