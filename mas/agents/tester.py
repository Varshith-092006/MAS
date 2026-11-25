"""Tester Agent: produces an internal TestReport from real execution evidence.

Default mode ("deterministic", Phase 8) makes ZERO LLM calls. It executes:
  1. the entry-point smoke protocol (python main.py, headless),
  2. the CLI contract probe (python main.py --help must exit 0),
  3. a placeholder scan (functions whose body is pass/.../NotImplementedError,
     docstring-only bodies, TODO/FIXME markers),
  4. any pytest files the Developer wrote (test_*.py / *_test.py).
Every check is a real, reproducible observation, so pass_rate is no longer a number the
model invents. This is the iCoder "automated testing module" (Sec. 3.2.4) implemented
with tools instead of an LLM.

Legacy mode ("llm") keeps the old behaviour, where the LLM writes the TestReport JSON.
It is kept only for comparison (config: quality_improvements.deterministic_tester: false).
"""

import ast
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from mas.agents.base import BaseAgent
from mas.core.schemas import TestReport
from mas.core.state import MASState
from mas.core.events import event_logger
from mas.db.models import Metric
from mas.db.session import get_session

_SKIP_DIRS = (".git", "__pycache__", ".mas_snapshots", ".pytest_cache")
_TODO_RE = re.compile(r"#\s*(TODO|FIXME)\b", re.IGNORECASE)
_PYTEST_SUMMARY_RE = re.compile(r"(\d+)\s+(passed|failed|error|errors)\b")

# Dependency-free test runner executed inside the sandbox (python:3.11-slim has no pytest).
# Runs module-level test_* functions and unittest.TestCase classes; prints a pytest-style summary.
MINI_TEST_RUNNER = r'''
import sys, os, importlib, inspect, traceback, unittest, io
sys.path.insert(0, '.')
passed = failed = 0
for path in sys.argv[1:]:
    name = os.path.splitext(path)[0].replace('/', '.').replace(os.sep, '.')
    try:
        mod = importlib.import_module(name)
    except BaseException:
        failed += 1
        print('ERROR collecting ' + path + ':\n' + traceback.format_exc()[-800:])
        continue
    for fname, fn in sorted(inspect.getmembers(mod, inspect.isfunction)):
        if not fname.startswith('test') or fn.__module__ != mod.__name__:
            continue
        if inspect.signature(fn).parameters:
            continue  # needs pytest fixtures; not executable without pytest
        try:
            fn()
            passed += 1
        except BaseException:
            failed += 1
            print('FAILED ' + path + '::' + fname + '\n' + traceback.format_exc()[-800:])
    suite = unittest.defaultTestLoader.loadTestsFromModule(mod)
    if suite.countTestCases():
        res = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        bad = len(res.failures) + len(res.errors)
        failed += bad
        passed += res.testsRun - bad
        for case, tb in (res.failures + res.errors)[:3]:
            print('FAILED ' + str(case) + '\n' + tb[-800:])
print(str(passed) + ' passed, ' + str(failed) + ' failed')
'''


def _iter_py_files(workspace_path: str):
    for root, _, files in os.walk(workspace_path):
        if any(s in root for s in _SKIP_DIRS):
            continue
        for fn in sorted(files):
            if fn.endswith(".py"):
                full = os.path.join(root, fn)
                yield os.path.relpath(full, workspace_path).replace("\\", "/"), full


def placeholder_reason(node: ast.AST) -> Optional[str]:
    """Returns why a function body counts as unimplemented, or None if it is implemented."""
    body = getattr(node, "body", [])
    if not body:
        return "empty body"
    stmts = list(body)
    if isinstance(stmts[0], ast.Expr) and isinstance(getattr(stmts[0], "value", None), ast.Constant) and isinstance(stmts[0].value.value, str):
        stmts = stmts[1:]
        if not stmts:
            return "docstring-only body"
    for stmt in stmts:
        if isinstance(stmt, ast.Pass):
            return "empty 'pass' body" if len(stmts) == 1 else "'pass' statement in body"
        if isinstance(stmt, ast.Expr) and isinstance(getattr(stmt, "value", None), ast.Constant) and stmt.value.value is Ellipsis:
            return "ellipsis '...' body"
        if isinstance(stmt, ast.Raise) and stmt.exc is not None:
            exc = stmt.exc
            name = getattr(exc, "id", "") or getattr(getattr(exc, "func", None), "id", "")
            if name == "NotImplementedError":
                return "raises NotImplementedError"
    return None


def scan_placeholders(workspace_path: str) -> Tuple[int, int, List[str]]:
    """Returns (total_functions, placeholder_functions, findings) for non-test source files."""
    total, unimpl, findings = 0, 0, []
    for rel, full in _iter_py_files(workspace_path):
        base = os.path.basename(rel)
        if base.startswith("test_") or base.endswith("_test.py"):
            continue
        try:
            with open(full, "r", encoding="utf-8") as fh:
                src = fh.read()
            tree = ast.parse(src, filename=rel)
        except Exception:
            continue
        lines = src.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                total += 1
                end = getattr(node, "end_lineno", node.lineno) or node.lineno
                has_todo = any(_TODO_RE.search(lines[i]) for i in range(node.lineno - 1, min(end, len(lines))))
                reason = placeholder_reason(node) or ("TODO/FIXME marker" if has_todo else None)
                if reason:
                    unimpl += 1
                    findings.append(f"{rel}:{node.lineno} function '{node.name}' is unimplemented ({reason}).")
    return total, unimpl, findings


def find_test_files(workspace_path: str) -> List[str]:
    out = []
    for rel, _ in _iter_py_files(workspace_path):
        base = os.path.basename(rel)
        if base.startswith("test_") or base.endswith("_test.py"):
            out.append(rel)
    return out


def parse_pytest_counts(output: str) -> Tuple[int, int]:
    """Parses pytest's final summary line into (passed, failed_or_error)."""
    passed = failed = 0
    tail = "\n".join((output or "").strip().splitlines()[-5:])
    for num, kind in _PYTEST_SUMMARY_RE.findall(tail):
        if kind == "passed":
            passed += int(num)
        else:
            failed += int(num)
    return passed, failed


def _trim(text: str, max_lines: int = 40, max_chars: int = 1500) -> str:
    lines = (text or "").strip().splitlines()
    out = "\n".join(lines[-max_lines:])
    return out[-max_chars:]


class TesterAgent(BaseAgent):
    """Builds the internal TestReport from real execution (default) or, legacy, from an LLM."""
    __test__ = False

    def __init__(self, llm, mode: Optional[str] = None, sandbox=None, **kwargs):
        super().__init__(name="tester", llm=llm, **kwargs)
        if mode is None:
            try:
                from mas.core.config import get_config
                qi = get_config().get("quality_improvements", {}) or {}
                mode = "deterministic" if qi.get("deterministic_tester", True) else "llm"
            except Exception:
                mode = "deterministic"
        self.mode = mode
        self._sandbox = sandbox

    def _get_sandbox(self):
        if self._sandbox is None:
            from mas.analysis.sandbox import SandboxRunner
            self._sandbox = SandboxRunner()
        return self._sandbox

    # ------------------------------------------------------------------ deterministic
    def deterministic_report(self, workspace_path: str, sandbox_res) -> Dict[str, Any]:
        sandbox = self._get_sandbox()
        checks: List[Tuple[str, bool, str]] = []

        # 1. Smoke protocol
        checks.append((
            "smoke: entry point runs without crashing",
            bool(sandbox_res.is_success),
            "" if sandbox_res.is_success else _trim(sandbox_res.stderr or sandbox_res.stdout or f"exit code {sandbox_res.exit_code}"),
        ))

        # 2. CLI --help contract (part of the shared requirement text for every system)
        entry = "main.py" if os.path.exists(os.path.join(workspace_path, "main.py")) else None
        if entry:
            try:
                help_res = sandbox.execute(workspace_path, ["python", entry, "--help"], allow_fallback=True)
                ok = help_res.exit_code == 0 and "traceback (most recent call last)" not in (help_res.stderr or "").lower()
                checks.append((
                    "cli: 'python main.py --help' exits with code 0",
                    ok,
                    "" if ok else _trim(help_res.stderr or help_res.stdout or f"exit code {help_res.exit_code}"),
                ))
            except Exception as e:
                checks.append(("cli: 'python main.py --help' exits with code 0", False, f"could not execute: {e}"))
        else:
            checks.append(("entry: main.py exists", False, "main.py is missing from the workspace"))

        # 3. Placeholder scan
        total_funcs, unimpl, ph_findings = scan_placeholders(workspace_path)
        checks.append((
            "completeness: no unimplemented functions or TODO markers",
            unimpl == 0,
            "\n".join(ph_findings[:5]),
        ))

        # 4. Developer-written tests (test_*.py), executed with the dependency-free runner
        test_files = find_test_files(workspace_path)
        py_passed = py_failed = 0
        pytest_detail = ""
        if test_files:
            try:
                res = sandbox.execute(
                    workspace_path,
                    ["python", "-c", MINI_TEST_RUNNER, *test_files],
                    allow_fallback=True,
                )
                py_passed, py_failed = parse_pytest_counts((res.stdout or "") + "\n" + (res.stderr or ""))
                if py_passed == 0 and py_failed == 0 and res.exit_code != 0:
                    py_failed = 1  # collection error / pytest missing: count as one failure
                if py_failed:
                    pytest_detail = _trim(res.stdout or res.stderr)
            except Exception as e:
                py_failed, pytest_detail = 1, f"pytest could not run: {e}"

        passed = sum(1 for _, ok, _ in checks if ok) + py_passed
        failed = sum(1 for _, ok, _ in checks if not ok) + py_failed
        total = passed + failed
        details = [f"FAILED {name}: {why}" if why else f"FAILED {name}" for name, ok, why in checks if not ok]
        if pytest_detail:
            details.append(f"FAILED pytest ({py_failed} failing): {pytest_detail}")

        internal_completeness = 1.0 if total_funcs == 0 else round(1.0 - unimpl / total_funcs, 4)
        return {
            "report": {
                "total_tests": total,
                "passed_tests": passed,
                "failed_tests": failed,
                "pass_rate": round(passed / total, 4) if total else 0.0,
                "coverage": 0.0,  # not measured; never invented
                "details": details[:5],
            },
            "internal_completeness": internal_completeness,
            "pytest_files": test_files,
            "pytest_passed": py_passed,
            "pytest_failed": py_failed,
        }

    # ------------------------------------------------------------------ main entry
    def run(self, state: MASState) -> MASState:
        run_id = state.get("run_id", str(uuid.uuid4()))
        event_logger.emit(
            run_id=run_id,
            agent="tester",
            event="agent_started",
            summary=f"Tester running ({self.mode} mode)",
        )

        sandbox = self._get_sandbox()
        workspace_path = state.get("workspace_path", ".")
        sandbox_res = sandbox.smoke_run(workspace_path, allow_fallback=True)
        state["sandbox_execution"] = {
            "exit_code": sandbox_res.exit_code,
            "is_success": sandbox_res.is_success,
            "duration_ms": sandbox_res.duration_ms,
            "timed_out": sandbox_res.timed_out,
            "stderr": sandbox_res.stderr,
        }

        if self.mode == "deterministic":
            det = self.deterministic_report(workspace_path, sandbox_res)
            report = TestReport(**det["report"])
            state["internal_completeness"] = det["internal_completeness"]
            self._record_artifact(run_id, "TestReport", state.get("iteration", 1), report)
        else:
            report = self._llm_report(state, run_id, sandbox_res)

        state["mas_pytest_report"] = report.model_dump()
        state["artifacts"]["TestReport"] = report.model_dump()

        try:
            with get_session() as session:
                session.add_all([
                    Metric(run_id=run_id, metric_name="pytest_pass_rate", metric_value=report.pass_rate, scope="internal"),
                    Metric(run_id=run_id, metric_name="coverage", metric_value=report.coverage, scope="internal"),
                ])
                session.commit()
        except Exception:
            pass

        event_logger.emit(
            run_id=run_id,
            agent="tester",
            event="agent_completed",
            summary=(
                f"Tester ({self.mode}) checks: {report.passed_tests}/{report.total_tests} passed "
                f"(pass_rate={report.pass_rate*100:.1f}%, scope=internal, llm_calls={'0' if self.mode == 'deterministic' else '>=1'})"
            ),
        )
        return state

    # ------------------------------------------------------------------ legacy LLM mode
    def _llm_report(self, state: MASState, run_id: str, sandbox_res) -> TestReport:
        plan = state.get("artifacts", {}).get("TaskPlan", {})
        acceptance_criteria = plan.get("acceptance_criteria", [])

        def produce_test_report(feedback=None):
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are TesterAgent. Generate an honest, structured TestReport based on actual acceptance criteria and sandbox execution outcomes.\n"
                        "Mandatory instructions:\n"
                        "1. Return ONLY a single valid JSON object matching the TestReport schema.\n"
                        "2. Required JSON keys: 'total_tests', 'passed_tests', 'failed_tests', 'pass_rate' (passed_tests / total_tests), 'coverage', and 'details'.\n"
                        "3. Do NOT output any introductory commentary, conversational preamble, chain-of-thought analysis, or markdown text outside the JSON object.\n"
                        "4. Do NOT fabricate passing tests if the code failed to execute.\n"
                        "5. Ensure the complete JSON object is closed properly."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Task: {state.get('requirement', '')}\n"
                        f"Acceptance Criteria: {acceptance_criteria}\n"
                        f"Changed Files: {state.get('changed_files', [])}\n"
                        f"Sandbox Smoke Test Exit Code: {sandbox_res.exit_code} (Success: {sandbox_res.is_success})\n"
                        f"Sandbox Stderr: {sandbox_res.stderr or 'None'}\n"
                        f"Feedback: {feedback or 'None'}\n\n"
                        f"Generate the TestReport JSON now starting immediately with '{{' and ending with '}}':"
                    ),
                },
            ]
            target_model = state.get("model") or getattr(self.llm, "default_model", None)
            res = self.llm.generate(
                messages=messages,
                model=target_model,
                response_schema=TestReport,
                run_id=run_id,
                agent_name="tester",
                max_tokens=3500,
            )
            data = res.parsed_json
            if not data and res.text:
                from mas.core.llm import extract_json
                data = extract_json(res.text)

            if data and isinstance(data, dict):
                data = dict(data)
                if not sandbox_res.is_success and data.get("pass_rate", 0.0) == 1.0 and data.get("total_tests", 0) > 0:
                    data["failed_tests"] = max(1, data.get("failed_tests", 0) + 1)
                    data["pass_rate"] = round(data.get("passed_tests", 0) / (data["passed_tests"] + data["failed_tests"]), 4)
                    data.setdefault("details", []).append(f"Sandbox smoke execution failed: {sandbox_res.stderr[:100]}")
                raw_details = data.get("details", [])
                if isinstance(raw_details, list):
                    data["details"] = ["\n".join(str(item).splitlines()[:40]) for item in raw_details[:5]]
                return data

            return {
                "error": "Tester LLM output could not be parsed as TestReport JSON. Return a valid JSON object matching the TestReport schema."
            }

        return self.produce_valid_artifact("TestReport", produce_test_report, state, TestReport)
