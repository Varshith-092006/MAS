"""Deterministic tests for Phase 2F Adaptive Stopping, Quality Gates, and Review Grounding.

Tests:
  1. Stopping status distinguishes COMPLETED_QUALITY_GATE from STOPPED_MAX_ITERATIONS_WITH_OPEN_FINDINGS.
  2. Actual executed behavioral tests outweigh unsupported self-assessment.
  3. Critical findings cannot disappear without traceable fix or evidence-based disposition.
  4. Review findings are checked against AST and code evidence (hallucination defense).
  5. A score improvement cannot hide a new critical defect.
  6. The iteration limit bounds work but does not transform incomplete quality into success.
  7. Final run status communicates whether the quality gate passed.
"""

import ast
import tempfile
from unittest.mock import MagicMock
import pytest

from mas.agents.reflection import AdaptiveStopper, ReflectionAgent
from mas.agents.reviewer import ReviewerAgent
from mas.core.schemas import ReviewReport, CodePatch
from mas.core.state import MASState
from mas.core.workflow import MASWorkflow


def test_evaluate_stop_clean_result():
    stopper = AdaptiveStopper(max_iterations=3)
    decision, reason, delta = stopper.evaluate_stop(
        iteration=1,
        current_score=0.90,
        previous_score=0.0,
        has_critical_defects=False,
        tests_pass=True,
    )
    assert decision == "STOP"
    assert "clean_result" in reason
    assert delta == 0.90


def test_evaluate_stop_max_iterations_with_open_findings():
    stopper = AdaptiveStopper(max_iterations=3)
    decision, reason, delta = stopper.evaluate_stop(
        iteration=3,
        current_score=0.45,
        previous_score=0.55,
        has_critical_defects=True,
        tests_pass=False,
    )
    assert decision == "STOP"
    assert "max_iterations" in reason
    assert "open_findings=True" in reason


def test_evaluate_stop_marginal_gain_plateau_with_open_findings():
    stopper = AdaptiveStopper(stop_epsilon=0.02, patience=2, max_iterations=5)
    # Iteration 1: delta small
    d1, r1, _ = stopper.evaluate_stop(iteration=1, current_score=0.40, previous_score=0.395, has_critical_defects=True, tests_pass=False)
    assert d1 == "CONTINUE"

    # Iteration 2: delta small again -> patience exceeded
    d2, r2, _ = stopper.evaluate_stop(iteration=2, current_score=0.405, previous_score=0.40, has_critical_defects=True, tests_pass=False)
    assert d2 == "STOP"
    assert "marginal_gain_plateau" in r2
    assert "open_findings=True" in r2


def test_score_improvement_cannot_hide_critical_defect():
    stopper = AdaptiveStopper(max_iterations=3)
    # Score improved significantly (+0.30), but has_critical_defects is True
    decision, reason, delta = stopper.evaluate_stop(
        iteration=1,
        current_score=0.85,
        previous_score=0.55,
        has_critical_defects=True,
        tests_pass=False,
    )
    # Must NOT stop with clean_result! Must continue iterating to resolve defect
    assert decision == "CONTINUE"
    assert delta == 0.30


def test_failing_behavioral_tests_force_critical_defects():
    reflection_agent = ReflectionAgent(llm=None)
    state: MASState = {
        "run_id": "test_run_stopper_01",
        "iteration": 1,
        "requirement": "Calculate sales",
        "artifacts": {},
        "review_report": {
            "status": "PASSED",
            "critical_issues": 0,
            "major_issues": 0,
            "findings": [],
        },
        "mas_pytest_report": {
            "pass_rate": 0.0,
            "total_tests": 2,
            "passed_tests": 0,
            "failed_tests": 2,
        },
        "sandbox_execution": {
            "is_success": False,
            "exit_code": 1,
            "stderr": "AssertionError: revenue mismatch",
        },
        "quality_report": {},
        "ast_report": {"cycles": []},
    }

    state = reflection_agent.run(state)
    ref_decision = state["artifacts"]["ReflectionDecision"]
    # Despite review report claiming PASSED (self-assessment), real tests failed -> cannot be clean stop
    assert ref_decision["decision"] == "CONTINUE"
    assert "clean_result" not in ref_decision["reason"]


def test_reviewer_hallucinated_syntax_error_dispositioned_by_ast():
    mock_llm = MagicMock()
    mock_llm.generate.return_value = MagicMock(
        parsed_json={
            "status": "FAILED",
            "critical_issues": 1,
            "major_issues": 0,
            "minor_issues": 0,
            "findings": ["Syntax error: incomplete code after 'if not results: p' causing parse error."],
            "summary": "Syntax error detected in main.py",
        },
        text=None,
    )

    reviewer = ReviewerAgent(llm=mock_llm)
    # Code with completely valid syntax
    valid_code = (
        "def main():\n"
        "    results = []\n"
        "    if not results:\n"
        "        print('No data found')\n"
        "        return\n"
    )
    state: MASState = {
        "run_id": "test_grounding_01",
        "requirement": "Simple entry point",
        "changed_files": ["main.py"],
        "artifacts": {
            "CodePatch": {
                "file_contents": {"main.py": valid_code},
            }
        },
        "sandbox_execution": {"stdout": "No data found", "is_success": True, "exit_code": 0},
    }

    state = reviewer.run(state)
    report = state["artifacts"]["ReviewReport"]
    # Grounding check must detect AST parse succeeded and disposition the hallucination
    assert report["critical_issues"] == 0
    assert report["status"] == "PASSED"
    assert any("DISPOSITIONED: FALSE POSITIVE" in f for f in report["findings"])


def test_reviewer_real_syntax_error_preserved():
    mock_llm = MagicMock()
    mock_llm.generate.return_value = MagicMock(
        parsed_json={
            "status": "FAILED",
            "critical_issues": 1,
            "major_issues": 0,
            "minor_issues": 0,
            "findings": ["Syntax error: invalid indentation in def broken."],
            "summary": "Real syntax error in main.py",
        },
        text=None,
    )

    reviewer = ReviewerAgent(llm=mock_llm)
    # Genuinely broken code
    broken_code = "def broken(\n  invalid indentation line!\n"
    state: MASState = {
        "run_id": "test_real_syntax_01",
        "requirement": "Simple entry point",
        "changed_files": ["main.py"],
        "artifacts": {
            "CodePatch": {
                "file_contents": {"main.py": broken_code},
            }
        },
        "sandbox_execution": {"stdout": "", "is_success": False, "exit_code": 1},
    }

    state = reviewer.run(state)
    report = state["artifacts"]["ReviewReport"]
    # Real syntax error must NOT be dispositioned; critical count must remain 1
    assert report["critical_issues"] == 1
    assert report["status"] == "FAILED"
    assert not any("DISPOSITIONED: FALSE POSITIVE" in f for f in report["findings"])


def test_workflow_status_distinguishes_quality_gate_from_max_iterations(tmp_path):
    from mas.core.llm import FakeLLMProvider
    fake_llm = FakeLLMProvider()
    wf = MASWorkflow(llm=fake_llm)

    # Clean run with FakeLLMProvider: all checks pass -> COMPLETED_QUALITY_GATE
    state = wf.run(
        requirement="Write a simple math calculator",
        task_id="task_calc_clean",
        model_name="fake",
        workspace_base=str(tmp_path / "ws_clean"),
    )
    assert state["status"] == "COMPLETED_QUALITY_GATE"
    assert state["quality_gate_passed"] is True
