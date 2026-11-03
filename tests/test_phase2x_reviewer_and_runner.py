"""Tests for Phase 2X: Reviewer schema-compliant error handling, runner resilience, and evaluator consistency."""

import json
import pytest
from unittest.mock import MagicMock, patch

from mas.agents.reviewer import ReviewerAgent
from mas.core.llm import ModelResult
from mas.core.schemas import ReviewReport
from eval.neutral_evaluator import NeutralEvaluator
from eval.runner import resolve_attempt_run_id, update_benchmark_manifest
from mas.db.models import Run
from mas.db.session import get_session, init_db


class MockLLMForReviewer:
    """Configurable mock LLM for testing ReviewerAgent edge cases."""
    def __init__(self, responses):
        self.responses = list(responses)
        self.call_count = 0
        self.default_model = "fake"

    def generate(self, *args, **kwargs):
        self.call_count += 1
        resp_text = self.responses.pop(0) if self.responses else "MALFORMED"
        return ModelResult(
            text=resp_text,
            model_name="fake",
            provider_model_version="fake_v1",
            requested_model="fake",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            latency_ms=10,
            request_id="fake_req_id",
            estimated_cost=0.0,
            execution_mode="SIMULATED",
            token_provenance="SIMULATED",
        )


def test_reviewer_malformed_json_exhaustion_returns_needs_revision(tmp_path):
    """Test 1: When LLM outputs non-JSON repeatedly, retry exhaustion yields schema-compliant NEEDS_REVISION."""
    # 3 responses: all invalid JSON strings
    mock_llm = MockLLMForReviewer(["This is not JSON at all.", "Still invalid JSON...", "Definitely broken JSON."])
    agent = ReviewerAgent(llm=mock_llm)

    state = {
        "run_id": "test_malformed_review",
        "iteration": 1,
        "task_id": "srdd_educ_01",
        "requirement": "Science Question Solver",
        "artifacts": {
            "CodePatch": {"files": ["main.py"], "summary": "Initial", "tests_expected": []},
            "TestReport": {"pass_rate": 1.0, "details": []},
        },
        "ast_report": {"cycles": []},
        "quality_report": {},
        "workspace_path": str(tmp_path),
    }
    (tmp_path / "main.py").write_text("print('hello')", encoding="utf-8")

    res_state = agent.run(state)

    # Must make 3 calls (attempt 1, attempt 2 with feedback, attempt 3 with strict feedback)
    assert mock_llm.call_count == 3
    assert "review_report" in res_state
    rep = res_state["review_report"]
    assert rep["status"] == "NEEDS_REVISION"
    assert rep["major_issues"] >= 1
    assert any("could not be parsed" in f for f in rep["findings"])


def test_reviewer_malformed_json_retry_success(tmp_path):
    """Test 2: Malformed output on attempt 1 triggers retry; valid JSON on attempt 2 succeeds."""
    valid_json = json.dumps({
        "status": "PASSED",
        "critical_issues": 0,
        "major_issues": 0,
        "minor_issues": 0,
        "findings": ["Clean code."],
        "summary": "Passed inspection."
    })
    mock_llm = MockLLMForReviewer([
        'Broken text without JSON structure',
        valid_json,  # Successful retry
    ])
    agent = ReviewerAgent(llm=mock_llm)

    state = {
        "run_id": "test_retry_review",
        "iteration": 1,
        "task_id": "srdd_educ_01",
        "requirement": "Science Question Solver",
        "artifacts": {
            "CodePatch": {"files": ["main.py"], "summary": "Initial", "tests_expected": []},
            "TestReport": {"pass_rate": 1.0, "details": []},
        },
        "ast_report": {"cycles": []},
        "quality_report": {},
        "workspace_path": str(tmp_path),
    }
    (tmp_path / "main.py").write_text("print('hello')", encoding="utf-8")

    res_state = agent.run(state)
    assert mock_llm.call_count == 2
    rep = res_state["review_report"]
    assert rep["status"] == "PASSED"
    assert rep["critical_issues"] == 0


def test_reviewer_truncation_recovery(tmp_path):
    """Test 2b: Truncated JSON on attempt 1 is automatically repaired without needing retry."""
    mock_llm = MockLLMForReviewer([
        '{"status": "PASSED", "critical_issues": 0, "major_issues": 0, "findings": ["Clean code.',  # Truncated trailing
    ])
    agent = ReviewerAgent(llm=mock_llm)

    state = {
        "run_id": "test_trunc_repair",
        "iteration": 1,
        "task_id": "srdd_educ_01",
        "requirement": "Science Question Solver",
        "artifacts": {
            "CodePatch": {"files": ["main.py"], "summary": "Initial", "tests_expected": []},
            "TestReport": {"pass_rate": 1.0, "details": []},
        },
        "ast_report": {"cycles": []},
        "quality_report": {},
        "workspace_path": str(tmp_path),
    }
    (tmp_path / "main.py").write_text("print('hello')", encoding="utf-8")

    res_state = agent.run(state)
    assert mock_llm.call_count == 1
    rep = res_state["review_report"]
    assert rep["status"] == "PASSED"
    assert rep["critical_issues"] == 0


def test_reviewer_propagates_needs_revision_status():
    """Test 3: Schema validation requires permitted status values."""
    rep = ReviewReport(
        status="NEEDS_REVISION",
        critical_issues=1,
        major_issues=0,
        minor_issues=0,
        findings=["Unparseable reviewer output"],
        summary="Review incomplete"
    )
    assert rep.status == "NEEDS_REVISION"
    assert rep.critical_issues == 1
    assert len(rep.findings) == 1


def test_resolve_attempt_run_id_preserves_existing():
    """Test 4: resolve_attempt_run_id produces non-colliding attempt IDs."""
    init_db()
    with get_session() as session:
        # Check if canonical exists or insert test run
        r1 = session.query(Run).filter(Run.run_id == "test_dummy_task_r1").first()
        if not r1:
            session.add(Run(run_id="test_dummy_task_r1", task_id="dummy", status="FAILED"))
            session.commit()

    id1 = resolve_attempt_run_id("", "test_dummy", "task", 1)
    assert id1 == "test_dummy_task_r1_attempt2"

    with get_session() as session:
        session.add(Run(run_id="test_dummy_task_r1_attempt2", task_id="dummy", status="FAILED"))
        session.commit()

    id2 = resolve_attempt_run_id("", "test_dummy", "task", 1)
    assert id2 == "test_dummy_task_r1_attempt3"


def test_manifest_pairs_completed_over_failed(tmp_path):
    """Test 5: update_benchmark_manifest pairs completed attempt with counterpart."""
    records = [
        {
            "run_id": "mas_task_r1",
            "task_id": "task_01",
            "system": "mas",
            "repeat_no": 1,
            "status": "FAILED",
            "execution_mode": "LIVE_API",
            "tokens": 100,
            "cost": 0.0,
        },
        {
            "run_id": "mas_task_r1_attempt2",
            "task_id": "task_01",
            "system": "mas",
            "repeat_no": 1,
            "status": "COMPLETED",
            "execution_mode": "LIVE_API",
            "tokens": 200,
            "cost": 0.0,
        },
        {
            "run_id": "cd_task_r1",
            "task_id": "task_01",
            "system": "chatdev",
            "repeat_no": 1,
            "status": "COMPLETED",
            "execution_mode": "LIVE_API",
            "tokens": 300,
            "cost": 0.0,
        },
    ]
    test_mf_path = str(tmp_path / "test_manifest.json")
    manifest = update_benchmark_manifest(records, manifest_path=test_mf_path)
    # The paired completed repeat count must be exactly 1
    assert manifest["summary"]["completed_paired_repeats"] == 1
    # Check that counterpart run IDs point to each other
    run_dict = {r["run_id"]: r for r in manifest["runs"]}
    assert run_dict["mas_task_r1_attempt2"]["paired_counterpart_run_id"] == "cd_task_r1"
    assert run_dict["cd_task_r1"]["paired_counterpart_run_id"] == "mas_task_r1_attempt2"
    assert run_dict["mas_task_r1_attempt2"]["is_paired_complete"] is True
    assert run_dict["cd_task_r1"]["is_paired_complete"] is True
    assert run_dict["mas_task_r1"]["is_paired_complete"] is False


def test_evaluator_consistency_on_valid_and_invalid(tmp_path):
    """Test 6: NeutralEvaluator consistency across valid execution, CLI usage, and syntax crash."""
    ne = NeutralEvaluator()

    # Case A: Normal script
    ws_valid = tmp_path / "valid_app"
    ws_valid.mkdir()
    (ws_valid / "main.py").write_text("def solve(): return 42\nif __name__ == '__main__': print(solve())\n", encoding="utf-8")
    res_valid = ne.evaluate_project(str(ws_valid), "Solve math", persist_to_db=False)
    assert res_valid["executability"] == 1.0

    # Case B: Argparse CLI requiring argument
    ws_cli = tmp_path / "cli_app"
    ws_cli.mkdir()
    (ws_cli / "main.py").write_text(
        "import argparse\nparser = argparse.ArgumentParser()\nparser.add_argument('-q', required=True)\nargs = parser.parse_args()\nprint(args.q)\n",
        encoding="utf-8"
    )
    res_cli = ne.evaluate_project(str(ws_cli), "Solve science question", persist_to_db=False)
    assert res_cli["executability"] == 1.0

    # Case C: Syntax Error (must evaluate to E=0.0)
    ws_broken = tmp_path / "broken_app"
    ws_broken.mkdir()
    (ws_broken / "main.py").write_text("def syntax_error(\n", encoding="utf-8")
    res_broken = ne.evaluate_project(str(ws_broken), "Solve question", persist_to_db=False)
    assert res_broken["executability"] == 0.0
