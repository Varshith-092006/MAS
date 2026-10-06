"""Unit tests for artifact schemas and SchemaValidator."""

import pytest
from mas.core.schemas import (
    TaskPlan,
    UserStory,
    Architecture,
    CodePatch,
    ReviewReport,
    TestReport,
    ReflectionDecision,
    get_json_schema,
)
from mas.core.validator import SchemaValidator


def test_json_schema_export():
    for art in ["TaskPlan", "UserStory", "Architecture", "CodePatch", "ReviewReport", "TestReport", "ReflectionDecision"]:
        schema = get_json_schema(art)
        assert isinstance(schema, dict)
        assert "properties" in schema


def test_task_plan_validation():
    valid_data = {
        "id": "TP-01",
        "task_id": "T-100",
        "name": "Math Utility",
        "description": "Calculates math functions",
        "complexity": "SIMPLE",
        "files": ["math.py"],
        "sprint_goals": ["Goal 1"],
    }
    res = SchemaValidator.validate_artifact("TaskPlan", valid_data)
    assert res.is_valid is True
    assert isinstance(res.parsed_artifact, TaskPlan)

    # Missing required field
    invalid_data = {"id": "TP-01"}
    res_bad = SchemaValidator.validate_artifact("TaskPlan", invalid_data)
    assert res_bad.is_valid is False
    assert len(res_bad.errors) > 0


def test_user_story_validation():
    valid = {
        "id": "US-1",
        "role": "admin",
        "action": "view dashboard",
        "goal": "monitor metrics",
        "acceptance_criteria": ["renders metrics"],
        "priority": "high",
        "estimate": 2,
    }
    res = SchemaValidator.validate_artifact("UserStory", valid)
    assert res.is_valid is True

    # Invalid estimate (< 1)
    invalid = dict(valid, estimate=0)
    res_bad = SchemaValidator.validate_artifact("UserStory", invalid)
    assert res_bad.is_valid is False


def test_code_patch_validation():
    valid = {
        "files": ["main.py"],
        "file_contents": {"main.py": "print('hello')"},
        "summary": "Initial hello script",
        "tests_expected": ["test_print"],
    }
    res = SchemaValidator.validate_artifact("CodePatch", valid)
    assert res.is_valid is True


def test_review_report_validation():
    valid = {
        "status": "PASSED",
        "critical_issues": 0,
        "major_issues": 0,
        "minor_issues": 1,
        "findings": ["Consider adding type hints"],
        "summary": "Good code",
    }
    res = SchemaValidator.validate_artifact("ReviewReport", valid)
    assert res.is_valid is True


def test_test_report_validation():
    valid = {
        "total_tests": 5,
        "passed_tests": 5,
        "failed_tests": 0,
        "pass_rate": 1.0,
        "coverage": 95.0,
        "details": ["all passed"],
    }
    res = SchemaValidator.validate_artifact("TestReport", valid)
    assert res.is_valid is True


def test_reflection_decision_validation():
    valid = {
        "decision": "STOP",
        "reason": "clean_result",
        "adaptive_score": 0.95,
        "marginal_gain": 0.1,
        "iteration": 1,
    }
    res = SchemaValidator.validate_artifact("ReflectionDecision", valid)
    assert res.is_valid is True
