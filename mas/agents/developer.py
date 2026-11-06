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
            arch = state.get("artifacts", {}).get("Architecture") or state.get("architecture", {})
            user_story = state.get("artifacts", {}).get("UserStory", {})
            if user_story and not acceptance_criteria:
                acceptance_criteria = user_story.get("acceptance_criteria", [])
            sprint_goals = plan.get("sprint_goals", [])
            uml_slice = state.get("relevant_uml", [])
            review_feedback = state.get("review_report", {}).get("findings", [])
            test_feedback = state.get("mas_pytest_report", {}).get("details", [])
            sandbox_err = state.get("sandbox_execution", {}).get("stderr", "")

            prompt_sections = [
                f"Task Requirement:\n{req}\n",
                f"Iteration: {iteration}\n",
            ]
            if arch and isinstance(arch, dict):
                files_planned = arch.get("file_structure", [])
                if files_planned:
                    prompt_sections.append("Planned Architecture Modules:\n" + "\n".join(f"- {fp}" for fp in files_planned) + "\n")
            if acceptance_criteria:
                prompt_sections.append("Acceptance Criteria:\n" + "\n".join(f"- {ac}" for ac in acceptance_criteria) + "\n")
            if review_feedback:
                prompt_sections.append("Review Findings to Fix:\n" + "\n".join(f"- {f}" for f in review_feedback) + "\n")
            if test_feedback:
                prompt_sections.append("Test Diagnostics:\n" + "\n".join(f"- {t}" for t in test_feedback) + "\n")
            if sandbox_err:
                prompt_sections.append(f"Sandbox Error:\n{sandbox_err}\n")
            if feedback:
                prompt_sections.append(f"Validator Feedback:\n{feedback}\n")

            prompt_sections.append(
                "Instructions:\n"
                "- Write complete, self-contained, executable Python code with entry point in main.py.\n"
                "- Entry point & CLI interface:\n"
                "  * If running from command line with '--help', print usage instructions and exit cleanly with status code 0.\n"
                "  * Running without arguments (e.g. 'python main.py' or calling main()) must execute cleanly and exit or return with code 0 without crashing.\n"
                "  * Provide a clear solver interface: define a function `solve(query: str) -> str` or a class `ScienceQuestionSolver` with method `solve(query: str) -> str`.\n"
                "- Multi-Domain Requirements:\n"
                "  * Implement complete, working logic for Physics (speed/velocity/distance/time), Chemistry (atomic numbers, symbols, carbon), and Biology (photosynthesis step-by-step).\n"
                "  * Do NOT use trivial stubs, 'pass', or placeholder comments.\n"
                "  * When input cannot be resolved, return a helpful explanation string instead of raising uncaught exceptions (like ValueError, IndexError) or exiting with code 1.\n"
                "- When the task specifies automated tests (e.g. test_main.py), generate test_main.py alongside main.py.\n\n"
                "Return a single JSON object matching this schema:\n"
                "{\n"
                '  "files": ["main.py", "test_main.py"],\n'
                '  "file_contents": {\n'
                '    "main.py": "<complete python code for main.py>",\n'
                '    "test_main.py": "<complete python code for test_main.py>"\n'
                '  },\n'
                '  "summary": "Implementation summary",\n'
                '  "tests_expected": ["test case 1", "test case 2"]\n'
                "}\n\n"
                "Generate the CodePatch JSON now starting immediately with '{' and ending with '}':"
            )
            prompt = "\n".join(prompt_sections)

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are DeveloperAgent. Output ONLY a valid JSON object matching the CodePatch schema, starting with { and ending with }.\n"
                        "Mandatory instructions:\n"
                        "1. Return ONLY a single valid JSON object matching the CodePatch schema.\n"
                        "2. Do NOT output any conversational preamble, chain-of-thought analysis, or markdown outside the JSON.\n"
                        "3. Generate complete, production-ready, executable Python code with entry point in main.py.\n"
                        "4. The application must handle '--help' and zero arguments cleanly with exit code 0.\n"
                        "5. The code must strictly satisfy the task requirements and all acceptance criteria without placeholders.\n"
                        "6. Ensure the complete JSON object is properly closed."
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
                max_tokens=4000,
            )
            data = res.parsed_json
            if not data and res.text:
                from mas.core.llm import extract_json
                data = extract_json(res.text)

            if data and isinstance(data, dict) and "files" in data and "file_contents" in data:
                return data

            # Fallback 1: Extract multi-file markdown code blocks
            import re
            import ast
            file_pattern = re.compile(
                r"(?:#{1,4}\s*[`*]*([a-zA-Z0-9_\-\.\/]+\.py)[`*]*|(?:\*\*|`)([a-zA-Z0-9_\-\.\/]+\.py)(?:\*\*|`):?|#\s*(?:file|filename):\s*([a-zA-Z0-9_\-\.\/]+\.py))\s*\n[\s\S]*?```(?:python)?\s*([\s\S]*?)(?:```|$)",
                re.IGNORECASE,
            )
            matches = file_pattern.findall(res.text or "")
            if matches:
                extracted_files = {}
                for m in matches:
                    fname = m[0] or m[1] or m[2]
                    fcontent = m[3].strip()
                    if fname and fcontent:
                        try:
                            ast.parse(fcontent)
                            extracted_files[os.path.basename(fname)] = fcontent
                        except SyntaxError:
                            pass
                if extracted_files and "main.py" in extracted_files:
                    return {
                        "files": list(extracted_files.keys()),
                        "file_contents": extracted_files,
                        "summary": f"Extracted {len(extracted_files)} files from markdown blocks",
                        "tests_expected": ["Execute main.py entry point and verify outputs"],
                    }

            # Fallback 2: Single python code block
            code_match = re.search(r"```(?:python)?\s*([\s\S]*?)(?:```|$)", res.text or "")
            if code_match and len(code_match.group(1).strip()) > 30:
                extracted_code = code_match.group(1).strip()
                try:
                    ast.parse(extracted_code)
                    return {
                        "files": ["main.py"],
                        "file_contents": {"main.py": extracted_code},
                        "summary": "Extracted complete Python implementation from model code block",
                        "tests_expected": ["Execute main.py entry point and verify outputs"],
                    }
                except SyntaxError:
                    pass

            # Return error payload to trigger produce_valid_artifact retry mechanism without polluting context
            return {
                "error": "Developer LLM output could not be parsed as CodePatch JSON. Return a valid JSON object with 'files' and 'file_contents'."
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
