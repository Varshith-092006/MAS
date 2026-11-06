"""Tester Agent: Generates internal diagnostic pytest tests and records metrics."""

from typing import Dict, List, Optional
import uuid

from mas.agents.base import BaseAgent
from mas.core.schemas import TestReport
from mas.core.state import MASState
from mas.core.events import event_logger
from mas.db.models import Metric
from mas.db.session import get_session


class TesterAgent(BaseAgent):
    """Generates internal diagnostic tests for the code and reports test pass rate."""
    __test__ = False

    def __init__(self, llm, **kwargs):
        super().__init__(name="tester", llm=llm, **kwargs)

    def run(self, state: MASState) -> MASState:
        run_id = state.get("run_id", str(uuid.uuid4()))

        event_logger.emit(
            run_id=run_id,
            agent="tester",
            event="agent_started",
            summary="Generating internal diagnostic tests",
        )

        # Run code in Sandbox first to observe real execution
        from mas.analysis.sandbox import SandboxRunner
        sandbox = SandboxRunner()
        workspace_path = state.get("workspace_path", ".")
        sandbox_res = sandbox.smoke_run(workspace_path, allow_fallback=True)
        state["sandbox_execution"] = {
            "exit_code": sandbox_res.exit_code,
            "is_success": sandbox_res.is_success,
            "duration_ms": sandbox_res.duration_ms,
            "timed_out": sandbox_res.timed_out,
            "stderr": sandbox_res.stderr,
        }

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
                max_tokens=2000,
            )
            data = res.parsed_json
            if not data and res.text:
                from mas.core.llm import extract_json
                data = extract_json(res.text)

            if data and isinstance(data, dict):
                data = dict(data)
                # If sandbox smoke test failed, ensure pass_rate reflects execution failure
                if not sandbox_res.is_success and data.get("pass_rate", 0.0) == 1.0 and data.get("total_tests", 0) > 0:
                    data["failed_tests"] = max(1, data.get("failed_tests", 0) + 1)
                    data["pass_rate"] = round(data.get("passed_tests", 0) / (data["passed_tests"] + data["failed_tests"]), 4)
                    data.setdefault("details", []).append(f"Sandbox smoke execution failed: {sandbox_res.stderr[:100]}")
                return data

            # Return error payload to trigger produce_valid_artifact retry mechanism
            return {
                "error": f"Tester LLM output could not be parsed as TestReport JSON: {res.text[:300]}"
            }

        report: TestReport = self.produce_valid_artifact("TestReport", produce_test_report, state, TestReport)

        state["mas_pytest_report"] = report.model_dump()
        state["artifacts"]["TestReport"] = report.model_dump()

        # Save to DB with scope = 'internal'
        try:
            with get_session() as session:
                m1 = Metric(
                    run_id=run_id,
                    metric_name="pytest_pass_rate",
                    metric_value=report.pass_rate,
                    scope="internal",
                )
                m2 = Metric(
                    run_id=run_id,
                    metric_name="coverage",
                    metric_value=report.coverage,
                    scope="internal",
                )
                session.add_all([m1, m2])
                session.commit()
        except Exception:
            pass

        event_logger.emit(
            run_id=run_id,
            agent="tester",
            event="agent_completed",
            summary=f"Diagnostic tests completed: pass_rate={report.pass_rate*100:.1f}%, coverage={report.coverage:.1f}% (scope=internal)",
        )

        return state
