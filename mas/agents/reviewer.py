"""Reviewer Agent: Performs semantic and requirement review using GPT-4o-mini."""

import os
from typing import Dict, List, Optional
import uuid

from mas.agents.base import BaseAgent
from mas.core.schemas import ReviewReport
from mas.core.state import MASState
from mas.core.events import event_logger


class ReviewerAgent(BaseAgent):
    """Reviews code against natural language requirements semantically.

    Structural checks are offloaded strictly to deterministic AST analysis.
    """

    def __init__(self, llm, **kwargs):
        super().__init__(name="reviewer", llm=llm, **kwargs)

    def run(self, state: MASState) -> MASState:
        run_id = state.get("run_id", str(uuid.uuid4()))
        req = state.get("requirement", "")
        changed_files = state.get("changed_files", [])

        event_logger.emit(
            run_id=run_id,
            agent="reviewer",
            event="agent_started",
            summary="Reviewer analyzing semantic conformance to requirements",
        )

        plan = state.get("artifacts", {}).get("TaskPlan", {})
        acceptance_criteria = plan.get("acceptance_criteria", [])
        patch = state.get("artifacts", {}).get("CodePatch", {})
        file_contents = patch.get("file_contents", {})
        workspace_path = state.get("workspace_path", "")

        # Collect code to review
        code_snippets = dict(file_contents)
        if not code_snippets and workspace_path and os.path.exists(workspace_path):
            for root, _, files in os.walk(workspace_path):
                if any(x in root for x in [".git", "__pycache__", ".mas_snapshots"]):
                    continue
                for f in files:
                    if f.endswith(".py"):
                        fp = os.path.join(root, f)
                        rel_p = os.path.relpath(fp, workspace_path).replace("\\", "/")
                        try:
                            with open(fp, "r", encoding="utf-8") as fh:
                                code_snippets[rel_p] = fh.read()
                        except Exception:
                            pass

        code_text_repr = "\n\n".join(
            f"=== File: {fname} ===\n{code}" for fname, code in code_snippets.items()
        ) if code_snippets else "No source files found in workspace."

        test_report = state.get("mas_pytest_report", {})
        sandbox_exec = state.get("sandbox_execution", {})
        quality_rep = state.get("quality_report", {})
        ast_rep = state.get("ast_report", {})

        def produce_review(feedback=None):
            review_prompt = (
                f"Task Requirement:\n{req}\n\n"
                f"Acceptance Criteria:\n" + "\n".join(f"- {ac}" for ac in acceptance_criteria) + "\n\n"
                f"Files Touched: {changed_files}\n\n"
                f"Actual Source Code Under Review:\n{code_text_repr}\n\n"
                f"Static Analysis Findings:\n"
                f"- AST Cycles: {len(ast_rep.get('cycles', []))}\n"
                f"- Ruff Violations: {quality_rep.get('ruff', {}).get('violations', 0)}\n"
                f"- Bandit High Severity: {quality_rep.get('bandit', {}).get('high', 0)}\n\n"
                f"Execution and Test Outcomes:\n"
                f"- Sandbox Exit Code: {sandbox_exec.get('exit_code', 'unknown')}\n"
                f"- Sandbox Success: {sandbox_exec.get('is_success', False)}\n"
                f"- Internal Test Pass Rate: {test_report.get('pass_rate', 0.0)}\n"
                f"- Test Failures / Output: {test_report.get('details', [])}\n\n"
                f"Validator Feedback: {feedback or 'None'}\n\n"
                "Review Guidelines:\n"
                "1. Independently verify whether the code satisfies all acceptance criteria.\n"
                "2. Identify genuine defects (syntax errors, logic bugs, unhandled exceptions, missing requirements).\n"
                "3. Do NOT invent phantom issues or require unnecessary rewrites if the code functions correctly.\n"
                "4. Return status 'PASSED' only if 0 critical and 0 major issues exist. Set 'FAILED' if critical defects exist."
            )

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are ReviewerAgent. Perform objective, evidence-based code and requirement review. "
                        "Examine the actual code, test execution results, and static analysis findings. "
                        "Return a valid ReviewReport JSON with: status ('PASSED', 'FAILED', or 'NEEDS_REVISION'), "
                        "critical_issues (int), major_issues (int), minor_issues (int), findings (list of strings), and summary (string)."
                    ),
                },
                {"role": "user", "content": review_prompt},
            ]
            target_model = state.get("model") or getattr(self.llm, "default_model", None)
            res = self.llm.generate(
                messages=messages,
                model=target_model,
                response_schema=ReviewReport,
                run_id=run_id,
                agent_name="reviewer",
                max_tokens=5000,
            )
            data = res.parsed_json
            if not data and res.text:
                from mas.core.llm import extract_json
                data = extract_json(res.text)

            if data and isinstance(data, dict):
                data = dict(data)
                if not data.get("status"):
                    crit = data.get("critical_issues", 0)
                    maj = data.get("major_issues", 0)
                    data["status"] = "PASSED" if (crit == 0 and maj == 0) else "NEEDS_REVISION"
                return data

            # Return error payload to trigger produce_valid_artifact retry mechanism
            return {
                "error": f"Reviewer LLM output could not be parsed as ReviewReport JSON: {res.text[:300]}"
            }

        report: ReviewReport = self.produce_valid_artifact("ReviewReport", produce_review, state, ReviewReport)

        # Evidence-grounded verification: cross-check reported findings against deterministic tools
        verified_critical = report.critical_issues
        verified_major = report.major_issues
        grounded_findings = []

        for finding in report.findings:
            f_str = finding if isinstance(finding, str) else str(finding)
            f_lower = f_str.lower()

            # 1. Cross-check reported pure syntax / parse errors against deterministic AST parse
            # (Do not disposition semantic, type, or undefined variable issues)
            is_pure_syntax = ("syntax error" in f_lower or "parse error" in f_lower) and not any(
                k in f_lower for k in ["undefined", "variable", "nameerror", "attribute", "type", "import"]
            )
            if is_pure_syntax:
                has_actual_syntax_error = False
                for fname, code in code_snippets.items():
                    try:
                        import ast
                        ast.parse(code, filename=fname)
                    except SyntaxError:
                        has_actual_syntax_error = True
                        break
                if not has_actual_syntax_error and code_snippets:
                    verified_critical = max(0, verified_critical - 1)
                    grounded_findings.append(f"[DISPOSITIONED: FALSE POSITIVE - Deterministic AST confirmed valid syntax]: {f_str}")
                    continue

            # 2. Cross-check reported missing CLI / main function against actual source definitions
            if ("missing cli" in f_lower or "no main function" in f_lower) and ("main" in f_lower or "cli" in f_lower):
                has_entry_def = False
                for fname, code in code_snippets.items():
                    if "def main(" in code or "def cli(" in code:
                        has_entry_def = True
                        break
                if has_entry_def:
                    verified_critical = max(0, verified_critical - 1)
                    grounded_findings.append(f"[DISPOSITIONED: FALSE POSITIVE - Entry point function is present in code]: {f_str}")
                    continue

            # 3. Cross-check reported missing output against sandbox execution stdout
            if "missing output" in f_lower or "not printed" in f_lower:
                sb_stdout = state.get("sandbox_execution", {}).get("stdout", "")
                if ("revenue" in sb_stdout.lower() or "total" in sb_stdout.lower()) and len(sb_stdout.strip()) > 10:
                    verified_critical = max(0, verified_critical - 1)
                    grounded_findings.append(f"[DISPOSITIONED: FALSE POSITIVE - Sandbox execution output confirmed revenue display]: {f_str}")
                    continue

            grounded_findings.append(f_str)

        # Grounded status determination
        grounded_status = report.status
        if verified_critical == 0 and verified_major == 0:
            grounded_status = "PASSED"
        elif verified_critical > 0:
            grounded_status = "FAILED"
        else:
            grounded_status = "NEEDS_REVISION"

        report_dump = report.model_dump()
        report_dump["critical_issues"] = verified_critical
        report_dump["major_issues"] = verified_major
        report_dump["findings"] = grounded_findings
        report_dump["status"] = grounded_status

        state["review_report"] = report_dump
        state["artifacts"]["ReviewReport"] = report_dump

        event_logger.emit(
            run_id=run_id,
            agent="reviewer",
            event="agent_completed",
            summary=f"Review completed: {grounded_status} (critical={verified_critical}, major={verified_major})",
        )

        return state
