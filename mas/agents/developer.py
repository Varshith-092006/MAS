"""Developer Agent: Writes code and outputs CodePatch artifacts using delimiter blocks or JSON."""

import ast
import os
import re
from typing import Any, Dict, List, Optional
import uuid

from mas.agents.base import BaseAgent
from mas.core.schemas import CodePatch
from mas.core.state import MASState
from mas.core.events import event_logger


def parse_delimiter_blocks(text: str) -> Optional[Dict[str, Any]]:
    """Parses source files from delimiter block format:
    === FILE: <filename> ===
    <raw code>
    === END FILE ===

    Robust to:
    - Reasoning text before the first marker
    - Multiple files
    - Missing END FILE marker (recovers up to next FILE or EOF)
    - Code with quotes, backslashes, and markdown code fences
    """
    if not text or "=== FILE:" not in text:
        return None

    # Tolerates `main.py`, "main.py" and **main.py** around the name (Lite-model variants).
    header_pattern = re.compile(r"===\s*FILE:\s*[`'\"*]*([a-zA-Z0-9_\-\.\/]+)[`'\"*]*\s*===", re.IGNORECASE)
    matches = list(header_pattern.finditer(text))
    if not matches:
        return None

    file_contents = {}
    for i, m in enumerate(matches):
        fname = os.path.basename(m.group(1).strip())
        content_start = m.end()
        if i + 1 < len(matches):
            chunk = text[content_start:matches[i + 1].start()]
        else:
            chunk = text[content_start:]

        # Accepts "=== END FILE ===" and variants such as "=== END FILE: main.py ===" (DEC-044).
        end_marker = re.search(r"===\s*END\s+FILE\b[^\n=]*===", chunk, re.IGNORECASE)
        if end_marker:
            code = chunk[:end_marker.start()]
        else:
            code = chunk

        code_str = code.strip()
        if code_str.startswith("```"):
            first_line_end = code_str.find("\n")
            if first_line_end != -1:
                code_str = code_str[first_line_end + 1:]
            if code_str.endswith("```"):
                code_str = code_str[:-3].rstrip()

        file_contents[fname] = code_str

    if not file_contents:
        return None

    return {
        "files": list(file_contents.keys()),
        "file_contents": file_contents,
        "summary": f"Extracted {len(file_contents)} files from delimiter blocks",
        "tests_expected": ["Execute main.py entry point and verify outputs"],
    }


def max_output_tokens() -> int:
    """Per-call output cap shared by MAS, the single-agent baseline and the ChatDev proxy (DEC-044)."""
    try:
        from mas.core.config import get_config
        return int(get_config().get("limits", {}).get("max_output_tokens", 8192))
    except Exception:
        return 8192


# Generic code-generation rules (no task-specific content). Used by the MAS Developer and the
# single-agent baseline so that MAS vs single isolates the multi-agent structure (DEC-044).
GENERATION_RULES = "".join(
    line + "\n"
    for line in (
        "- Start your answer directly with the first === FILE: block. No plan or explanation before it.",
        "- Keep the project small enough to write completely in one answer (at most 4 files). "
        "If a planned design has more modules, merge them: complete working code matters more than file count.",
        "- Use only the Python standard library; no third-party packages.",
        "- The program must not crash when no keyboard input is available: catch EOFError around input() "
        "and exit cleanly. 'python main.py --help' must print usage and exit with code 0.",
    )
)


MAX_DIAGRAM_CHARS = 2000
MAX_CONTEXT_CODE_CHARS = 24000  # about 6k input tokens; input is cheap, requests are not

SELF_TEST_GUIDANCE = (
    "Note on failing unit tests: some failing tests were written by you in an earlier iteration. "
    "First decide whether the program or the test is wrong. If a test's expected value is wrong, "
    "fix the test and keep the correct program behaviour. Do not spend the whole iteration on tests: "
    "also fix review findings about missing requirements.\n"
)


def current_code_section(files: Dict[str, str], budget: int = MAX_CONTEXT_CODE_CHARS) -> str:
    """Formats the current workspace code for the Developer prompt (P1, DEC-045).

    Files are shown in delimiter-block form so the model sees exactly the format it must
    return. When the budget runs out, the remaining files are listed by name only.
    """
    py_files = {k.replace("\\", "/"): v for k, v in files.items() if k.endswith(".py")}
    if not py_files:
        return ""
    # main.py first, then the rest in a stable order
    order = sorted(py_files, key=lambda f: (f != "main.py", f))
    parts, used, omitted = [], 0, []
    for name in order:
        code = py_files[name]
        block = f"=== FILE: {name} ===\n{code.rstrip()}\n=== END FILE ===\n"
        if used + len(block) > budget:
            omitted.append(name)
            continue
        parts.append(block)
        used += len(block)
    header = (
        "Current Code (from the previous iteration). Return ONLY the files you change, each one "
        "complete. Files you do not return are kept exactly as they are.\n"
    )
    tail = f"(Not shown, unchanged unless you return them: {', '.join(omitted)})\n" if omitted else ""
    return header + "".join(parts) + tail


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

    def targeted_repair(self, state: MASState, errors: List[str]) -> MASState:
        """Sends ONE targeted repair prompt containing only failing files and error text."""
        run_id = state.get("run_id", str(uuid.uuid4()))
        workspace = state.get("workspace_path", f"./workspace/{run_id}")

        event_logger.emit(
            run_id=run_id,
            agent="developer",
            event="agent_started",
            summary=f"Developer performing targeted deterministic repair ({len(errors)} issues)",
        )

        failing_files = {}
        if os.path.exists(workspace):
            for fn in os.listdir(workspace):
                if fn.endswith(".py"):
                    fp = os.path.join(workspace, fn)
                    try:
                        with open(fp, "r", encoding="utf-8") as fh:
                            failing_files[fn] = fh.read()
                    except Exception:
                        pass

        repair_prompt = (
            f"The following deterministic checks failed:\n"
            + "\n".join(f"- {e}" for e in errors[:5])
            + "\n\nCurrent code in failing files:\n"
            + "\n\n".join(f"=== {fn} ===\n{code}" for fn, code in failing_files.items())
            + "\n\nFix ONLY these defects and provide complete, corrected files using delimiter blocks:\n"
            "=== FILE: <filename> ===\n<corrected code>\n=== END FILE ===\n"
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are DeveloperAgent. Fix the specific deterministic errors identified. "
                    "Output complete, production-ready, corrected files using delimiter blocks: "
                    "=== FILE: <filename> ===\n<code>\n=== END FILE ==="
                ),
            },
            {"role": "user", "content": repair_prompt},
        ]

        target_model = state.get("model") or getattr(self.llm, "default_model", None)
        res = self.llm.generate(
            messages=messages,
            model=target_model,
            response_schema=CodePatch,
            run_id=run_id,
            agent_name="developer",
            max_tokens=max_output_tokens(),
        )

        data = parse_delimiter_blocks(res.text)
        if not data and res.parsed_json:
            data = res.parsed_json
        if not data and res.text:
            from mas.core.llm import extract_json
            data = extract_json(res.text)

        if data and isinstance(data, dict) and "file_contents" in data:
            files_list = data.get("files") or list(data["file_contents"].keys())
            patch = CodePatch(
                files=files_list,
                file_contents=data["file_contents"],
                summary=data.get("summary", "Targeted repair patch applied"),
                tests_expected=data.get("tests_expected", ["Run main.py entry point"]),
            )
            changed = self.apply_patch(patch, workspace)
            state["changed_files"] = changed
            state["artifacts"]["CodePatch"] = patch.model_dump()
            event_logger.emit(
                run_id=run_id,
                agent="developer",
                event="agent_completed",
                summary=f"Targeted repair applied: {len(changed)} files updated ({', '.join(changed)})",
            )

        return state

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
            arch = state.get("artifacts", {}).get("Architecture") or state.get("architecture", {})
            user_story = state.get("artifacts", {}).get("UserStory", {})
            if user_story and not acceptance_criteria:
                acceptance_criteria = user_story.get("acceptance_criteria", [])
            uml_slice = state.get("relevant_uml", [])
            # Cap review findings to latest 5 items for prompt hygiene
            review_feedback = (state.get("review_report", {}).get("findings", []))[-5:]
            test_feedback = (state.get("mas_pytest_report", {}).get("details", []))[-5:]
            sandbox_err = state.get("sandbox_execution", {}).get("stderr", "")

            prompt_sections = [
                f"Task Requirement:\n{req}\n",
                f"Iteration: {iteration}\n",
            ]
            if arch and isinstance(arch, dict):
                files_planned = arch.get("file_structure", [])
                if files_planned:
                    prompt_sections.append("Planned Architecture Modules:\n" + "\n".join(f"- {fp}" for fp in files_planned) + "\n")
                # P2 (DEC-045): the Architect's class diagram reaches the Developer. Long
                # diagrams are replaced by the slice relevant to the files in play.
                diagram = str(arch.get("uml_class_diagram") or "").strip()
                if len(diagram) > MAX_DIAGRAM_CHARS and uml_slice:
                    diagram = "\n".join(uml_slice)
                if diagram:
                    prompt_sections.append(
                        "Design (class diagram from the Architect). Use these class and method names "
                        "unless that would break the program:\n" + diagram[:MAX_DIAGRAM_CHARS] + "\n"
                    )
            # P1 (DEC-045): from iteration 2 on, show the current code (changed files plus their
            # AST dependents, chosen by the ContextSlicer) and ask only for the files that change.
            code_section = current_code_section(state.get("context_files") or {})
            if iteration > 1 and code_section:
                prompt_sections.append(code_section)
            if acceptance_criteria:
                prompt_sections.append("Acceptance Criteria:\n" + "\n".join(f"- {ac}" for ac in acceptance_criteria) + "\n")
            if review_feedback:
                prompt_sections.append("Review Findings to Fix:\n" + "\n".join(f"- {f}" for f in review_feedback) + "\n")
            if test_feedback:
                prompt_sections.append("Test Diagnostics:\n" + "\n".join(f"- {t}" for t in test_feedback) + "\n")
                # P4 (DEC-045): failing unit tests that the Developer wrote may themselves be wrong.
                if any("FAILED pytest" in str(t) for t in test_feedback):
                    prompt_sections.append(SELF_TEST_GUIDANCE)
            if sandbox_err:
                prompt_sections.append(f"Sandbox Error:\n{sandbox_err[:300]}\n")
            if feedback:
                prompt_sections.append(f"Validator Feedback:\n{feedback}\n")

            prompt_sections.append("Generation Rules:\n" + GENERATION_RULES)
            prompt_sections.append(
                "Instructions:\n"
                "- Write complete, self-contained, executable Python code with entry point in main.py.\n"
                "- Implement complete, working logic for all requirements.\n"
                "- Do NOT use trivial stubs, 'pass', or placeholder comments.\n"
                "- When input cannot be resolved, handle bad input cleanly without raising uncaught exceptions or crashing.\n"
                "- When the task specifies automated tests (e.g. test_main.py), generate test_main.py alongside main.py.\n\n"
                "Format your output using delimiter blocks for each file:\n"
                "=== FILE: main.py ===\n"
                "<complete python code for main.py>\n"
                "=== END FILE ===\n\n"
                "(If additional files or tests are needed, include additional === FILE: <filename> === blocks).\n"
            )
            prompt = "\n".join(prompt_sections)

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are DeveloperAgent. Output complete, production-ready, executable Python code with entry point in main.py.\n"
                        "Format each file using delimiter blocks:\n"
                        "=== FILE: <filename> ===\n"
                        "<raw code>\n"
                        "=== END FILE ===\n"
                        "Do NOT use placeholders, pass-only stubs, or TODO comments.\n"
                        "Return complete, functional code."
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
                max_tokens=max_output_tokens(),
            )

            # 1. First priority: Delimiter blocks format
            block_data = parse_delimiter_blocks(res.text)
            if block_data:
                return block_data

            # 2. Second priority: parsed JSON or extracted JSON
            data = res.parsed_json
            if not data and res.text:
                from mas.core.llm import extract_json
                data = extract_json(res.text)

            if data and isinstance(data, dict) and "files" in data and "file_contents" in data:
                return data

            # 3. Third priority: Extract multi-file markdown code blocks
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
                # From iteration 2 a patch may legitimately change only other files (DEC-045).
                if extracted_files and ("main.py" in extracted_files or iteration > 1):
                    return {
                        "files": list(extracted_files.keys()),
                        "file_contents": extracted_files,
                        "summary": f"Extracted {len(extracted_files)} files from markdown blocks",
                        "tests_expected": ["Execute main.py entry point and verify outputs"],
                    }

            # 4. Fourth priority: Single python code block
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

            return {
                "error": "Developer LLM output could not be parsed as CodePatch. Return files using delimiter blocks: === FILE: <filename> === ... === END FILE ==="
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
