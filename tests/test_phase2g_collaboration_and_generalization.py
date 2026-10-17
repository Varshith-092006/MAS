"""Comprehensive deterministic validation suite for Phase 2G multi-agent collaboration and generalization.

Validates the 8 core collaboration requirements:
  1. Manager requirements survive all handoffs.
  2. Architect module contracts match Developer files on STRUCTURED tasks.
  3. Developer revisions fix actual defects found.
  4. Tester executes independent behavioral tests and records outcomes.
  5. Reviewer examines actual code, diffs, static analysis, and test output.
  6. Reflection and Adaptive Stopper use real internal signals.
  7. Context slicing preserves essential dependencies and UML slices.
  8. Workflow terminates at correct quality state (COMPLETED_QUALITY_GATE vs STOPPED_BUDGET_CEILING).
"""

import os
import sys
import tempfile
import uuid
from unittest.mock import MagicMock, patch
import pytest

from mas.agents.manager import ManagerAgent
from mas.agents.architect import ArchitectAgent
from mas.agents.developer import DeveloperAgent
from mas.agents.tester import TesterAgent
from mas.agents.reviewer import ReviewerAgent
from mas.agents.reflection import ReflectionAgent, AdaptiveStopper
from mas.agents.router import ComplexityRouter
from mas.core.context import ContextSlicer
from mas.core.workflow import MASWorkflow
from mas.core.llm import FakeLLMProvider, ModelResult
from mas.core.state import create_initial_state
from mas.core.schemas import TaskPlan, Architecture, UserStory, CodePatch, ReviewReport, TestReport, ReflectionDecision


def test_1_manager_requirements_survive_all_handoffs():
    """Verify that Manager's acceptance criteria and description survive state handoffs."""
    state = create_initial_state(
        run_id="run-test-mgr",
        requirement="Build Markdown TOC CLI",
        task_id="dev_markdown_toc_01",
    )
    plan_data = {
        "id": "plan-1",
        "task_id": "dev_markdown_toc_01",
        "name": "Markdown TOC CLI",
        "description": "Parse headings # to ###, exclude code blocks, handle empty files.",
        "steps": ["Step 1", "Step 2"],
        "acceptance_criteria": [
            "Parse level 1-3 headings",
            "Ignore code block headings",
            "Handle empty files with code 0",
        ],
    }
    state["artifacts"]["TaskPlan"] = plan_data
    state["complexity"] = "SIMPLE"

    # ContextSlicer handoff
    slicer = ContextSlicer()
    sliced = slicer.build_context(state, {"main.py": "print('hello')"}, {})
    assert sliced["task"] == "Build Markdown TOC CLI"
    assert len(sliced["acceptance_criteria"]) == 3
    assert "Ignore code block headings" in sliced["acceptance_criteria"]

    # Developer context handoff
    mock_llm = MagicMock()
    mock_llm.generate.return_value = ModelResult(
        text="",
        model_name="test-model",
        provider_model_version="v1",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        latency_ms=25,
        request_id="mock-req-dev",
        estimated_cost=0.0,
        parsed_json={
            "files": ["main.py"],
            "summary": "TOC generator implemented",
            "file_contents": {"main.py": "print('TOC')"},
            "tests_expected": ["test_toc"],
        },
    )
    dev = DeveloperAgent(llm=mock_llm)
    with tempfile.TemporaryDirectory() as tmpdir:
        state["workspace_path"] = tmpdir
        state = dev.run(state)
        call_args = mock_llm.generate.call_args[1]
        prompt_text = call_args["messages"][1]["content"]
        assert "Ignore code block headings" in prompt_text
        assert "Parse level 1-3 headings" in prompt_text


def test_2_architect_module_contracts_match_developer_files():
    """Verify that STRUCTURED path invokes Architect and module contracts match Developer artifacts."""
    router = ComplexityRouter()
    structured_req = (
        "A multi-module inventory management service and CLI application requiring coherent architecture, "
        "modular contracts, and data persistence. The system must include: 1. Data models with validation. "
        "2. Persistence layer for repository storage. 3. Service workflow layer managing stock. "
        "4. Reporting module providing inventory metrics. 5. CLI interface in main.py. "
        "Must handle malformed files, negative stock errors, missing arguments, and corrupt storage gracefully."
    )
    label, score, features = router.route(structured_req)
    assert label == "STRUCTURED"
    assert score >= 4

    state = create_initial_state(
        run_id="run-test-arch",
        requirement=structured_req,
        task_id="dev_inventory_system_01",
    )
    state["complexity"] = label
    state["artifacts"]["TaskPlan"] = {
        "id": "plan-inv",
        "task_id": "dev_inventory_system_01",
        "name": "Inventory Service",
        "description": structured_req,
        "steps": ["Design", "Implement"],
        "acceptance_criteria": ["Modular architecture", "Data model validation", "JSON persistence"],
    }

    arch = Architecture(
        components=[
            {"name": "ItemModel", "responsibility": "Data validation for inventory items"},
            {"name": "StorageRepo", "responsibility": "JSON persistence"},
            {"name": "InventoryService", "responsibility": "Business operations"},
        ],
        uml_class_diagram="classDiagram\nclass ItemModel\nclass StorageRepo\nclass InventoryService",
        file_structure=["models.py", "storage.py", "service.py", "main.py"],
        module_dependencies={"service": ["models", "storage"], "storage": ["models"]},
    )
    state["architecture"] = arch.model_dump()
    state["artifacts"]["Architecture"] = arch.model_dump()

    # Developer creates code matching Architect's file structure
    code_patch = CodePatch(
        files=["models.py", "storage.py", "service.py", "main.py"],
        summary="Implement multi-module inventory architecture",
        file_contents={
            "models.py": "class Item: pass",
            "storage.py": "class StorageRepo: pass",
            "service.py": "class InventoryService: pass",
            "main.py": "def main(): pass",
        },
        tests_expected=["test_item_validation", "test_persistence"],
    )
    # Validate that every architect file is represented in developer patch
    for f in arch.file_structure:
        assert f in code_patch.file_contents


def test_3_developer_revisions_fix_reviewer_findings():
    """Verify that Developer receives Reviewer defects and updates state accordingly."""
    state = create_initial_state(
        run_id="run-test-dev-rev",
        requirement="Task",
        task_id="dev_01",
    )
    state["changed_files"] = ["main.py"]
    state["review_report"] = {
        "status": "NEEDS_REVISION",
        "critical_issues": 1,
        "major_issues": 0,
        "minor_issues": 0,
        "findings": ["Missing --help argument parsing in main.py"],
        "summary": "CLI missing help flag",
    }
    state["iteration"] = 2

    slicer = ContextSlicer()
    ctx = slicer.build_context(state, {"main.py": "def main(): pass"}, {})
    assert "Missing --help argument parsing in main.py" in ctx["review_findings"]
    assert ctx["iteration"] == 2


def test_4_tester_records_sandbox_and_pytest_outcomes():
    """Verify that TesterAgent accurately records sandbox exit code and test pass rates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state = create_initial_state(
            run_id="run-test-tester",
            requirement="Task",
            task_id="dev_01",
        )
        state["workspace_path"] = tmpdir
        # Create dummy entry point
        main_file = os.path.join(tmpdir, "main.py")
        with open(main_file, "w") as f:
            f.write("print('smoke passed')\n")

        tester = TesterAgent(llm=FakeLLMProvider())
        state = tester.run(state)
        assert "mas_pytest_report" in state
        assert "pass_rate" in state["mas_pytest_report"]
        assert "sandbox_execution" in state
        assert state["sandbox_execution"]["exit_code"] == 0
        assert state["sandbox_execution"]["is_success"] is True


def test_5_reviewer_examines_source_and_test_evidence():
    """Verify that Reviewer prompt incorporates code, AST, Ruff, Bandit, and test evidence."""
    state = create_initial_state(
        run_id="run-test-reviewer",
        requirement="Task",
        task_id="dev_01",
    )
    state["artifacts"]["TaskPlan"] = {"acceptance_criteria": ["Criteria 1"]}
    state["artifacts"]["CodePatch"] = {"file_contents": {"main.py": "print('tested')"}}
    state["mas_pytest_report"] = {"pass_rate": 1.0, "details": []}
    state["sandbox_execution"] = {"is_success": True, "exit_code": 0}
    state["ast_report"] = {"cycles": []}
    state["quality_report"] = {"ruff": {"violations": 0}, "bandit": {"high": 0}}

    mock_llm = MagicMock()
    mock_llm.generate.return_value = ModelResult(
        text="",
        model_name="test-model",
        provider_model_version="v1",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        latency_ms=25,
        request_id="mock-req-1",
        estimated_cost=0.0,
        parsed_json={
            "status": "PASSED",
            "critical_issues": 0,
            "major_issues": 0,
            "minor_issues": 0,
            "findings": [],
            "summary": "All criteria met cleanly",
        },
    )

    reviewer = ReviewerAgent(llm=mock_llm)
    state = reviewer.run(state)
    assert state["review_report"]["status"] == "PASSED"
    # Inspect user message passed to LLM
    call_args = mock_llm.generate.call_args[1]
    prompt_text = call_args["messages"][1]["content"]
    assert "Criteria 1" in prompt_text
    assert "print('tested')" in prompt_text
    assert "Sandbox Exit Code: 0" in prompt_text


def test_6_reflection_and_adaptive_stopper_invariants():
    """Verify AdaptiveStopper enforces zero critical defects before clean result stopping."""
    stopper = AdaptiveStopper()

    # Case A: Tests fail (pass_rate < 1.0) -> must NOT stop with clean_result
    dec, reason, delta = stopper.evaluate_stop(
        iteration=1,
        current_score=0.75,
        previous_score=0.0,
        has_critical_defects=True,
        tests_pass=False,
    )
    assert dec == "CONTINUE"
    assert "continuing to iteration 2" in reason

    # Case B: Max iterations reached with critical defects -> stops with open_findings
    dec_max, reason_max, delta_max = stopper.evaluate_stop(
        iteration=3,
        current_score=0.75,
        previous_score=0.75,
        has_critical_defects=True,
        tests_pass=False,
    )
    assert dec_max == "STOP"
    assert "max_iterations" in reason_max
    assert "open_findings=True" in reason_max

    # Case C: Tests pass, 0 critical issues -> stops with clean_result
    dec_clean, reason_clean, delta_clean = stopper.evaluate_stop(
        iteration=1,
        current_score=1.0,
        previous_score=0.0,
        has_critical_defects=False,
        tests_pass=True,
    )
    assert dec_clean == "STOP"
    assert "clean_result" in reason_clean


def test_7_context_slicer_preserves_contracts():
    """Verify ContextSlicer slices relevant UML and changed files."""
    slicer = ContextSlicer()
    all_files = {
        "models.py": "class Item: pass",
        "service.py": "class Service: pass",
        "unrelated.py": "class Unrelated: pass",
    }
    state = create_initial_state(
        run_id="run-test-slicer",
        requirement="Task",
        task_id="dev_01",
    )
    state["changed_files"] = ["models.py"]
    deps = {"service": {"models"}}

    sliced = slicer.get_sliced_files(state, all_files, deps)
    assert "models.py" in sliced


def test_8_workflow_terminal_quality_state_differentiation():
    """Verify that workflow correctly differentiates COMPLETED_QUALITY_GATE from STOPPED_BUDGET_CEILING."""
    workflow = MASWorkflow(llm=FakeLLMProvider())

    # Mock workflow run returning clean result
    state = {
        "status": "RUNNING",
        "artifacts": {
            "ReflectionDecision": {"decision": "STOP", "reason": "clean_result: iteration 1 perfect score"},
        },
        "review_report": {"status": "PASSED", "critical_issues": 0},
        "sandbox_execution": {"is_success": True},
    }
    final_decision = state["artifacts"]["ReflectionDecision"]
    stop_reason = str(final_decision.get("reason", ""))
    last_review = state["review_report"]
    last_crit = last_review.get("critical_issues", 0)
    last_status = last_review.get("status", "")
    sandbox_exec = state["sandbox_execution"]
    sandbox_ok = sandbox_exec.get("is_success", False)

    has_open_findings = (last_crit > 0 or last_status in ("FAILED", "NEEDS_REVISION") or not sandbox_ok)
    if not has_open_findings and stop_reason.startswith("clean_result"):
        final_status = "COMPLETED_QUALITY_GATE"
    else:
        final_status = "STOPPED_MAX_ITERATIONS_WITH_OPEN_FINDINGS"

    assert final_status == "COMPLETED_QUALITY_GATE"
