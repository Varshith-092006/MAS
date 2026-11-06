"""Regression tests for Phase 2AN: TaskPlan validation and unmasked error diagnostics."""

import pytest
from pydantic import ValidationError

from mas.core.schemas import TaskPlan
from mas.core.validator import SchemaValidator
from mas.core.llm import extract_json


def test_validator_preserves_explicit_producer_error_payload():
    """Verify that SchemaValidator does not mask producer error payloads into Pydantic missing-field errors."""
    error_payload = {
        "error": "Manager LLM output could not be parsed as TaskPlan JSON: {\"id\": \"plan-1\", ... truncated"
    }
    res = SchemaValidator.validate_artifact("TaskPlan", error_payload)
    assert not res.is_valid
    assert len(res.errors) == 1
    assert "Manager LLM output could not be parsed as TaskPlan JSON" in res.errors[0]
    # Ensure it did NOT mask into generic required field errors
    assert "('id',): Field required" not in res.error_summary()
    assert "('task_id',): Field required" not in res.error_summary()


def test_validator_preserves_producer_exception_payload():
    """Verify that SchemaValidator preserves __producer_exception__ payloads."""
    exc_payload = {
        "__producer_exception__": "RuntimeError: Connection to OpenRouter timed out after 90s"
    }
    res = SchemaValidator.validate_artifact("TaskPlan", exc_payload)
    assert not res.is_valid
    assert "Connection to OpenRouter timed out after 90s" in res.error_summary()
    assert "('id',): Field required" not in res.error_summary()


def test_validator_strictly_enforces_required_taskplan_fields_on_data_payloads():
    """Verify that schema validation is NOT weakened: non-error payloads missing required fields fail Pydantic validation."""
    incomplete_plan = {
        "files": ["main.py"],
        "sprint_goals": ["Goal 1"],
        # Missing id, task_id, name, description
    }
    res = SchemaValidator.validate_artifact("TaskPlan", incomplete_plan)
    assert not res.is_valid
    summary = res.error_summary()
    assert "('id',)" in summary
    assert "('task_id',)" in summary
    assert "('name',)" in summary
    assert "('description',)" in summary


def test_validator_accepts_valid_taskplan():
    """Verify that a valid TaskPlan dictionary passes validation and parses successfully."""
    valid_plan = {
        "id": "plan-srdd_educ_01",
        "task_id": "srdd_educ_01",
        "name": "Science Question Solver",
        "description": "Step-by-step science question solver providing explanations and solutions.",
        "complexity": "SIMPLE",
        "files": ["main.py", "solver.py"],
        "sprint_goals": ["Implement CLI solver"],
        "acceptance_criteria": ["Clean exit with code 0"],
        "ambiguities": [],
    }
    res = SchemaValidator.validate_artifact("TaskPlan", valid_plan)
    assert res.is_valid
    assert isinstance(res.parsed_artifact, TaskPlan)
    assert res.parsed_artifact.id == "plan-srdd_educ_01"
    assert res.parsed_artifact.task_id == "srdd_educ_01"


def test_extract_json_handles_truncated_and_code_fence_json():
    """Verify extract_json behavior on truncated outputs and markdown code fences."""
    # Truncated JSON should return None
    truncated = '{"id": "plan-1", "name": "Science Solver", "description": "truncated...'
    assert extract_json(truncated) is None

    # Complete markdown code fence should parse cleanly
    fenced = '```json\n{"id": "plan-2", "task_id": "t1", "name": "N", "description": "D"}\n```'
    parsed = extract_json(fenced)
    assert parsed is not None
    assert parsed["id"] == "plan-2"
