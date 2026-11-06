"""Regression tests for Phase 2AO: TesterAgent TestReport extraction, validation, and conversational error handling."""

import pytest
from pydantic import ValidationError

from mas.core.schemas import TestReport
from mas.core.validator import SchemaValidator
from mas.core.llm import extract_json, ModelResult, FakeLLMProvider
from mas.agents.tester import TesterAgent
from mas.core.state import MASState


def test_attempt4_conversational_preamble_fails_extraction_without_fabrication():
    """Reproduce exact Attempt 4 failure snippet: pure conversational preamble without valid JSON fails safely."""
    attempt4_snippet = (
        "We need to generate a TestReport based on acceptance criteria and sandbox execution outcomes. "
        "The sandbox smoke test exit code is 0 (Success: True). Stderr: None. The changed file is main.py. "
        "We need to evaluate whether the program meets acceptance criteria. We need to run tests? We have no actual t"
    )
    # extract_json must return None because no valid JSON object exists
    assert extract_json(attempt4_snippet) is None

    # Error payload must be preserved by SchemaValidator without fabricating a passing report
    error_payload = {
        "error": f"Tester LLM output could not be parsed as TestReport JSON: {attempt4_snippet[:100]}"
    }
    val_res = SchemaValidator.validate_artifact("TestReport", error_payload)
    assert not val_res.is_valid
    assert "Tester LLM output could not be parsed as TestReport JSON" in val_res.error_summary()


def test_fenced_json_with_surrounding_commentary_extracts_cleanly():
    """Verify that TestReport JSON wrapped in markdown fences with commentary extracts and validates cleanly."""
    fenced_output = """Here is the diagnostic test report based on acceptance criteria:
```json
{
  "total_tests": 4,
  "passed_tests": 4,
  "failed_tests": 0,
  "pass_rate": 1.0,
  "coverage": 85.0,
  "details": [
    "PASSED: --help argument outputs usage instructions",
    "PASSED: Zero-argument run exits with code 0",
    "PASSED: Physics speed calculation",
    "PASSED: Chemistry carbon atomic number"
  ]
}
```
All tests executed successfully.
"""
    data = extract_json(fenced_output)
    assert data is not None
    assert data["total_tests"] == 4
    assert data["pass_rate"] == 1.0

    val_res = SchemaValidator.validate_artifact("TestReport", data)
    assert val_res.is_valid
    report: TestReport = val_res.parsed_artifact
    assert isinstance(report, TestReport)
    assert report.total_tests == 4
    assert report.passed_tests == 4
    assert report.failed_tests == 0
    assert report.pass_rate == 1.0


def test_raw_json_with_surrounding_text_extracts_cleanly():
    """Verify that raw un-fenced JSON surrounded by commentary extracts cleanly."""
    raw_output = """Based on the execution:
{
  "total_tests": 2,
  "passed_tests": 2,
  "failed_tests": 0,
  "pass_rate": 1.0,
  "coverage": 75.0,
  "details": ["Test 1 ok", "Test 2 ok"]
}
End of report.
"""
    data = extract_json(raw_output)
    assert data is not None
    assert data["total_tests"] == 2
    val_res = SchemaValidator.validate_artifact("TestReport", data)
    assert val_res.is_valid
    assert val_res.parsed_artifact.total_tests == 2


def test_testreport_schema_strictness_and_bounds():
    """Verify that TestReport schema bounds are strictly enforced and cannot be weakened."""
    # pass_rate cannot exceed 1.0
    with pytest.raises(ValidationError):
        TestReport(total_tests=5, passed_tests=6, failed_tests=0, pass_rate=1.2, coverage=50.0)

    # total_tests cannot be negative
    with pytest.raises(ValidationError):
        TestReport(total_tests=-1, passed_tests=0, failed_tests=0, pass_rate=0.0, coverage=0.0)

    # Valid bounds succeed
    valid = TestReport(total_tests=3, passed_tests=2, failed_tests=1, pass_rate=0.6667, coverage=70.0)
    assert valid.pass_rate == 0.6667


def test_tester_agent_runs_with_fake_llm():
    """Verify TesterAgent produces valid TestReport artifact in state using fake LLM."""
    fake_llm = FakeLLMProvider()
    agent = TesterAgent(llm=fake_llm)
    state = MASState(
        run_id="test_tester_run",
        requirement="Step-by-step science question solver",
        artifacts={
            "TaskPlan": {
                "id": "p1",
                "task_id": "srdd_educ_01",
                "name": "Science Solver",
                "description": "Solver",
                "acceptance_criteria": ["Clean exit with code 0"],
            }
        },
        changed_files=["main.py"],
        iteration=1,
    )
    new_state = agent.run(state)
    assert "TestReport" in new_state["artifacts"]
    report_dict = new_state["artifacts"]["TestReport"]
    assert "pass_rate" in report_dict
    assert "total_tests" in report_dict

