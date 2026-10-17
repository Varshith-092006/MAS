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
            plan = state.get("artifacts", {}).get("TaskPlan", {})
            acceptance_criteria = plan.get("acceptance_criteria", [])
            sprint_goals = plan.get("sprint_goals", [])
            arch = state.get("architecture", {})
            uml_slice = state.get("relevant_uml", [])
            review_feedback = state.get("review_report", {}).get("findings", [])
            test_feedback = state.get("mas_pytest_report", {}).get("details", [])
            sandbox_err = state.get("sandbox_execution", {}).get("stderr", "")

            prompt_sections = [
                f"Task Requirement:\n{req}\n",
                f"Iteration: {iteration}\n",
                "Acceptance Criteria:\n" + "\n".join(f"- {ac}" for ac in acceptance_criteria) + "\n",
            ]
            if sprint_goals:
                prompt_sections.append(f"Sprint Goals: {sprint_goals}\n")
            if arch and arch.get("components"):
                prompt_sections.append(f"Architecture Components: {arch['components']}\n")
            if uml_slice:
                prompt_sections.append(f"UML Context: {uml_slice}\n")
            if review_feedback:
                prompt_sections.append("Review Findings to Address:\n" + "\n".join(f"- {f}" for f in review_feedback) + "\n")
            if test_feedback:
                prompt_sections.append("Test Diagnostic Details:\n" + "\n".join(f"- {t}" for t in test_feedback) + "\n")
            if sandbox_err:
                prompt_sections.append(f"Sandbox Stderr:\n{sandbox_err}\n")
            if feedback:
                prompt_sections.append(f"Validator Feedback:\n{feedback}\n")

            prompt_sections.append(
                "Instructions:\n"
                "- Write complete Python code with entry point in main.py.\n"
                "- Handle column variations flexibly: 'product name'/'product'/'product_name', 'quantity'/'qty', and 'unit price'/'unit_price'/'price'.\n"
                "- Handle empty CSV files without crashing (output total 0).\n"
                "- Validate numeric inputs (quantity >= 0, unit_price >= 0.0), warning to stderr and skipping invalid/negative rows.\n"
                "- Handle malformed rows by warning to stderr and skipping.\n"
                "- When acceptance criteria specify automated tests, generate test_main.py alongside main.py.\n"
                "Return a single JSON object with these keys:\n"
                "- files: list of target file paths (e.g. ['main.py', 'test_main.py'])\n"
                "- file_contents: an object mapping each filename to its complete, non-truncated Python source code string\n"
                "- summary: a concise description of the implementation\n"
                "- tests_expected: list of test or verification cases\n"
            )
            prompt = "\n".join(prompt_sections)

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are DeveloperAgent. Generate complete, production-ready, executable Python code with a valid entry point (main.py). "
                        "The code must strictly satisfy the task requirements and all acceptance criteria. "
                        "Do NOT use placeholders, pass statements, or ellipsis stubs. "
                        "Return a valid CodePatch JSON containing files, file_contents mapping, summary, and tests_expected."
                    ),
                },
                {"role": "user", "content": prompt},
            ]

            target_model = state.get("model") or getattr(self.llm, "default_model", None)
            res = self.llm.generate(
                messages=messages,
                model=target_model,
                response_schema=CodePatch,
                run_id=run_id,
                agent_name="developer",
                max_tokens=6000,
            )
            if res.parsed_json and "files" in res.parsed_json and "file_contents" in res.parsed_json:
                return res.parsed_json

            # Fallback: check if model emitted python code block directly
            import re
            code_match = re.search(r"```(?:python)?\s*([\s\S]*?)\s*```", res.text)
            if code_match and len(code_match.group(1).strip()) > 30:
                extracted_code = code_match.group(1).strip()
                return {
                    "files": ["main.py"],
                    "file_contents": {"main.py": extracted_code},
                    "summary": "Extracted complete Python implementation from model code block",
                    "tests_expected": ["Execute main.py entry point and verify outputs"],
                }

            # Return error payload to trigger produce_valid_artifact retry mechanism
            return {
                "error": f"Developer LLM output could not be parsed as CodePatch JSON: {res.text[:300]}"
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
