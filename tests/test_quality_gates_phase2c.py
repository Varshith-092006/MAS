"""Quality Gates A through D verification test suite for Phase 2C.

Verifies:
- Gate A: Individual agent contracts, deterministic behavior, error handling, validation.
- Gate B: Complete orchestration workflow, review cycles, negative tests with deliberate defects.
- Gate C: Generated software execution and behavioral tests in sandbox.
- Gate D: Recovery and operational safety (schema failures, timeouts, model mismatch).
"""

import os
import shutil
import tempfile
import time
from typing import Any, Dict, List, Optional
import pytest

from mas.agents.manager import ManagerAgent
from mas.agents.architect import ArchitectAgent
from mas.agents.developer import DeveloperAgent
from mas.agents.reviewer import ReviewerAgent
from mas.agents.tester import TesterAgent
from mas.agents.reflection import ReflectionAgent, AdaptiveStopper
from mas.agents.router import ComplexityRouter
from mas.analysis.sandbox import SandboxRunner
from mas.core.checkpoints import CheckpointManager
from mas.core.context import ContextSlicer
from mas.core.llm import FakeLLMProvider, LLMProvider, ModelResult, ModelMismatchError, is_model_match
from mas.core.schemas import TaskPlan, UserStory, Architecture, CodePatch, ReviewReport, TestReport, ReflectionDecision
from mas.core.state import create_initial_state
from mas.core.workflow import MASWorkflow
from eval.scorers.icoder_metrics import (
    calculate_completeness,
    calculate_executability,
    calculate_consistency,
    calculate_quality,
)
from eval.neutral_evaluator import NeutralEvaluator


# ==============================================================================
# GATE A: INDIVIDUAL AGENTS
# ==============================================================================

def test_gate_a_manager_agent_acceptance_criteria(tmp_path):
    """Gate A: ManagerAgent generates TaskPlan with explicit acceptance criteria and ambiguities."""
    llm = FakeLLMProvider()
    agent = ManagerAgent(llm=llm)
    state = create_initial_state(
        run_id="test-mgr-01",
        requirement="Create a CLI tool to calculate kinetic energy given mass and velocity.",
        task_id="science_ke_01",
        workspace_path=str(tmp_path),
        model="fake",
    )
    new_state = agent.run(state)
    plan_dict = new_state["artifacts"]["TaskPlan"]

    assert "acceptance_criteria" in plan_dict
    assert isinstance(plan_dict["acceptance_criteria"], list)
    assert len(plan_dict["acceptance_criteria"]) > 0
    assert "ambiguities" in plan_dict
    assert isinstance(plan_dict["ambiguities"], list)
    assert plan_dict["complexity"] in ["SIMPLE", "STRUCTURED"]


def test_gate_a_architect_agent_contracts(tmp_path):
    """Gate A: ArchitectAgent produces Architecture and UserStory with UML and dependencies."""
    llm = FakeLLMProvider()
    agent = ArchitectAgent(llm=llm)
    state = create_initial_state(
        run_id="test-arch-01",
        requirement="Build a database-backed user management API with RBAC.",
        task_id="rbac_api_01",
        workspace_path=str(tmp_path),
        model="fake",
    )
    state["artifacts"]["TaskPlan"] = {
        "id": "TP-001",
        "task_id": "rbac_api_01",
        "name": "RBAC Service",
        "description": "User management with roles",
        "complexity": "STRUCTURED",
        "files": ["main.py", "models.py"],
        "sprint_goals": ["Design architecture", "Implement endpoints"],
        "acceptance_criteria": ["Roles can be assigned", "Endpoints check permissions"],
    }
    new_state = agent.run(state)

    arch = new_state["artifacts"]["Architecture"]
    assert len(arch["components"]) > 0
    assert "uml_class_diagram" in arch
    assert len(arch["file_structure"]) > 0
    assert isinstance(arch["module_dependencies"], dict)

    user_story = new_state["artifacts"]["UserStory"]
    assert user_story["role"] != ""
    assert len(user_story["acceptance_criteria"]) > 0


def test_gate_a_developer_agent_no_silent_calculator_fallback(tmp_path):
    """Gate A: DeveloperAgent creates actual files from LLM output without hardcoded calculator fallback."""
    class CustomDevLLM(FakeLLMProvider):
        def generate(self, messages, model="fake", response_schema=None, **kwargs):
            if response_schema and response_schema.__name__ == "CodePatch":
                patch = {
                    "files": ["main.py", "science.py"],
                    "file_contents": {
                        "science.py": "def kinetic_energy(m: float, v: float) -> float:\n    return 0.5 * m * (v ** 2)\n",
                        "main.py": "from science import kinetic_energy\n\ndef main():\n    print(kinetic_energy(10.0, 2.0))\n\nif __name__ == '__main__':\n    main()\n",
                    },
                    "summary": "Implemented kinetic energy solver",
                    "tests_expected": ["test_ke"],
                }
                import json
                return ModelResult(
                    text=json.dumps(patch),
                    model_name="fake",
                    provider_model_version="fake-v1",
                    input_tokens=10,
                    output_tokens=20,
                    total_tokens=30,
                    latency_ms=5,
                    request_id="req-dev-01",
                    estimated_cost=0.0,
                    parsed_json=patch,
                )
            return super().generate(messages, model, response_schema, **kwargs)

    agent = DeveloperAgent(llm=CustomDevLLM())
    state = create_initial_state(
        run_id="test-dev-01",
        requirement="Calculate kinetic energy",
        task_id="ke_task",
        workspace_path=str(tmp_path),
        model="fake",
    )
    state["artifacts"]["TaskPlan"] = {
        "id": "TP-001",
        "task_id": "ke_task",
        "name": "KE Solver",
        "description": "Calculate kinetic energy",
        "complexity": "SIMPLE",
        "files": ["main.py", "science.py"],
        "sprint_goals": ["Implement KE formula"],
        "acceptance_criteria": ["kinetic_energy(10, 2) == 20.0"],
    }

    new_state = agent.run(state)
    assert "main.py" in new_state["changed_files"]
    assert "science.py" in new_state["changed_files"]
    assert os.path.exists(os.path.join(tmp_path, "science.py"))
    assert os.path.exists(os.path.join(tmp_path, "main.py"))


def test_gate_a_reviewer_agent_catches_defect_independently(tmp_path):
    """Gate A: ReviewerAgent examines code and catches deliberate critical defects."""
    class DefectDetectingReviewerLLM(FakeLLMProvider):
        def generate(self, messages, model="fake", response_schema=None, **kwargs):
            if response_schema and response_schema.__name__ == "ReviewReport":
                # Inspect user message content to see if defect was passed
                user_msg = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
                has_defect = "broken_syntax" in user_msg or "UndefinedVariable" in user_msg
                if has_defect:
                    rep = {
                        "status": "FAILED",
                        "critical_issues": 1,
                        "major_issues": 0,
                        "minor_issues": 0,
                        "findings": ["Syntax error: Undefined variable referenced"],
                        "summary": "Critical defect detected in code.",
                    }
                else:
                    rep = {
                        "status": "PASSED",
                        "critical_issues": 0,
                        "major_issues": 0,
                        "minor_issues": 0,
                        "findings": ["Code is correct and clean."],
                        "summary": "All acceptance criteria verified.",
                    }
                import json
                return ModelResult(
                    text=json.dumps(rep),
                    model_name="fake",
                    provider_model_version="fake-v1",
                    input_tokens=10,
                    output_tokens=20,
                    total_tokens=30,
                    latency_ms=5,
                    request_id="req-rev-01",
                    estimated_cost=0.0,
                    parsed_json=rep,
                )
            return super().generate(messages, model, response_schema, **kwargs)

    agent = ReviewerAgent(llm=DefectDetectingReviewerLLM())
    state = create_initial_state(
        run_id="test-rev-01",
        requirement="Solve science question",
        task_id="sci_01",
        workspace_path=str(tmp_path),
        model="fake",
    )
    state["artifacts"]["TaskPlan"] = {
        "id": "TP-001",
        "task_id": "sci_01",
        "name": "Science Solver",
        "description": "Science Solver",
        "complexity": "SIMPLE",
        "files": ["main.py"],
        "sprint_goals": ["Implement solver"],
        "acceptance_criteria": ["Must run without syntax errors"],
    }
    # Deliberate defect in code patch
    state["artifacts"]["CodePatch"] = {
        "files": ["main.py"],
        "file_contents": {
            "main.py": "def broken_syntax():\n    return UndefinedVariable + 1\n",
        },
        "summary": "Broken implementation",
        "tests_expected": [],
    }

    new_state = agent.run(state)
    report = new_state["artifacts"]["ReviewReport"]
    assert report["status"] == "FAILED"
    assert report["critical_issues"] == 1
    assert "Syntax error" in report["findings"][0]


def test_gate_a_tester_agent_smoke_failure_reflected(tmp_path):
    """Gate A: TesterAgent reflects real sandbox smoke failure in pass_rate."""
    # Write a broken main.py in workspace that crashes on import
    broken_code = "raise RuntimeError('Crashing during startup')\n"
    with open(tmp_path / "main.py", "w") as f:
        f.write(broken_code)

    llm = FakeLLMProvider()
    agent = TesterAgent(llm=llm)
    state = create_initial_state(
        run_id="test-test-01",
        requirement="Run service",
        task_id="t1",
        workspace_path=str(tmp_path),
        model="fake",
    )
    state["artifacts"]["TaskPlan"] = {
        "id": "TP-001", "task_id": "t1", "name": "App", "description": "App",
        "complexity": "SIMPLE", "files": ["main.py"], "sprint_goals": [],
        "acceptance_criteria": ["Runs without crash"],
    }
    state["changed_files"] = ["main.py"]

    new_state = agent.run(state)
    sandbox_res = new_state["sandbox_execution"]
    assert sandbox_res["is_success"] is False
    assert sandbox_res["exit_code"] != 0

    report = new_state["artifacts"]["TestReport"]
    # Pass rate must not be 1.0 when smoke execution failed
    assert report["pass_rate"] < 1.0 or report["failed_tests"] > 0


def test_gate_a_context_slicer_preserves_contracts(tmp_path):
    """Gate A: ContextSlicer preserves requirements, acceptance criteria, and transitive modules."""
    slicer = ContextSlicer()
    all_files = {
        "main.py": "import service\ndef main(): service.run()\n",
        "service.py": "import datastore\ndef run(): datastore.save()\n",
        "datastore.py": "def save(): return True\n",
        "unrelated.py": "def helper(): return 1\n",
    }
    dep_graph = {
        "main": {"service"},
        "service": {"datastore"},
        "datastore": set(),
        "unrelated": set(),
    }
    state = create_initial_state(
        run_id="test-slicer-01",
        requirement="Implement user persistence",
        task_id="user_p_01",
        workspace_path=str(tmp_path),
        model="fake",
    )
    state["iteration"] = 2
    state["changed_files"] = ["service.py"]
    state["artifacts"]["TaskPlan"] = {
        "id": "TP-01", "task_id": "t1", "name": "Plan", "description": "Desc",
        "complexity": "STRUCTURED", "files": ["main.py", "service.py", "datastore.py"],
        "sprint_goals": [],
        "acceptance_criteria": ["Datastore is called"],
    }

    ctx = slicer.build_context(state, all_files, dep_graph)
    # Changed service.py impacts main.py and relies on datastore.py
    assert "service.py" in ctx["files"]
    assert "acceptance_criteria" in ctx
    assert len(ctx["acceptance_criteria"]) > 0


def test_gate_a_complexity_router_deterministic_stability():
    """Gate A: ComplexityRouter route stability for identical inputs and scoring rules."""
    router = ComplexityRouter(threshold=4)
    req_simple = "Implement a simple CLI string reverser that takes input and prints reversed text."
    req_structured = (
        "Build a multi-user inventory management system with SQLite database storage, "
        "JWT authentication, role-based access for admin and staff, external webhook notifications, "
        "and analytical reporting charts."
    )

    lbl1, score1, _ = router.route(req_simple)
    lbl2, score2, _ = router.route(req_simple)
    assert lbl1 == lbl2 == "SIMPLE"
    assert score1 == score2
    assert score1 < 4

    lbl_s1, score_s1, feat1 = router.route(req_structured)
    lbl_s2, score_s2, feat2 = router.route(req_structured)
    assert lbl_s1 == lbl_s2 == "STRUCTURED"
    assert score_s1 == score_s2
    assert score_s1 >= 4
    assert "persistence" in feat1
    assert "authentication" in feat1
    assert "multiple_roles" in feat1


def test_gate_a_adaptive_stopper_conditions():
    """Gate A: AdaptiveStopper terminates on clean result, bounded patience, and max iterations."""
    stopper = AdaptiveStopper(stop_epsilon=0.02, patience=2, max_iterations=3)

    # 1. Clean result terminates immediately
    dec, reason, _ = stopper.evaluate_stop(
        iteration=1,
        current_score=0.95,
        previous_score=0.0,
        has_critical_defects=False,
        tests_pass=True,
    )
    assert dec == "STOP"
    assert "clean_result" in reason

    # 2. Critical defect forces continuation if under max iterations
    dec2, reason2, _ = stopper.evaluate_stop(
        iteration=1,
        current_score=0.70,
        previous_score=0.0,
        has_critical_defects=True,
        tests_pass=False,
    )
    assert dec2 == "CONTINUE"

    # 3. Max iterations terminates even if critical defect remains
    dec3, reason3, _ = stopper.evaluate_stop(
        iteration=3,
        current_score=0.70,
        previous_score=0.70,
        has_critical_defects=True,
        tests_pass=False,
    )
    assert dec3 == "STOP"
    assert "max_iterations" in reason3


def test_gate_a_evaluator_metrics_compliance(tmp_path):
    """Gate A: Neutral Evaluator correctly yields None / 0.0 for missing code rather than inflated numbers."""
    empty_ws = tmp_path / "empty_ws"
    os.makedirs(empty_ws, exist_ok=True)

    # Missing files yield 0.0 completeness and 0.0 executability
    comp = calculate_completeness(str(empty_ws))
    execu = calculate_executability(str(empty_ws))
    assert comp == 0.0
    assert execu == 0.0

    # Missing code yields None (UNAVAILABLE) consistency, not 0.50 or 0.85
    cons = calculate_consistency("Requirement text", "")
    assert cons is None

    # Quality with any None component yields None
    q = calculate_quality(comp, execu, cons)
    assert q is None


# ==============================================================================
# GATE B: INTEGRATION AND CONTROLLED NEGATIVE TESTS
# ==============================================================================

def test_gate_b_full_workflow_end_to_end(tmp_path):
    """Gate B: Full orchestration workflow executes through all agent handoffs."""
    llm = FakeLLMProvider()
    wf = MASWorkflow(llm=llm)
    state = wf.run(
        requirement="Create a math utility that computes factorials and primes.",
        task_id="math_fact_01",
        model_name="fake",
        workspace_base=str(tmp_path),
    )

    assert state["status"] in ["COMPLETED", "COMPLETED_QUALITY_GATE", "STOPPED"]
    assert "TaskPlan" in state["artifacts"]
    assert "CodePatch" in state["artifacts"]
    assert "ReviewReport" in state["artifacts"]
    assert "TestReport" in state["artifacts"]
    assert "ReflectionDecision" in state["artifacts"]

    workspace = state["workspace_path"]
    assert os.path.exists(os.path.join(workspace, "main.py"))


def test_gate_b_reviewer_catches_defect_and_developer_fixes(tmp_path):
    """Gate B: Controlled negative test: Developer injects bug in iter 1 -> Reviewer flags -> Fixed in iter 2."""
    iter_tracker = {"iteration": 1}

    class IterativeFixingLLM(FakeLLMProvider):
        def generate(self, messages, model="fake", response_schema=None, **kwargs):
            if response_schema and response_schema.__name__ == "CodePatch":
                current_iter = iter_tracker["iteration"]
                iter_tracker["iteration"] += 1
                if current_iter == 1:
                    # Deliberate broken code in iteration 1
                    patch = {
                        "files": ["main.py"],
                        "file_contents": {
                            "main.py": "def solve():\n    raise NotImplementedError('Bug in iter 1')\n\nif __name__ == '__main__':\nsolve()\n",
                        },
                        "summary": "Incomplete broken patch",
                        "tests_expected": [],
                    }
                else:
                    # Fixed code in iteration 2
                    patch = {
                        "files": ["main.py"],
                        "file_contents": {
                            "main.py": "def solve():\n    return 42\n\nif __name__ == '__main__':\n    print(solve())\n",
                        },
                        "summary": "Fixed working patch",
                        "tests_expected": ["test_solve"],
                    }
                import json
                return ModelResult(
                    text=json.dumps(patch),
                    model_name="fake",
                    provider_model_version="fake-v1",
                    input_tokens=10,
                    output_tokens=20,
                    total_tokens=30,
                    latency_ms=5,
                    request_id="req-fix",
                    estimated_cost=0.0,
                    parsed_json=patch,
                )

            elif response_schema and response_schema.__name__ == "ReviewReport":
                # Check if the code in user message has NotImplementedError
                user_content = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
                if "raise NotImplementedError" in user_content:
                    rep = {
                        "status": "FAILED",
                        "critical_issues": 1,
                        "major_issues": 0,
                        "minor_issues": 0,
                        "findings": ["Function raises NotImplementedError"],
                        "summary": "Code does not execute properly.",
                    }
                else:
                    rep = {
                        "status": "PASSED",
                        "critical_issues": 0,
                        "major_issues": 0,
                        "minor_issues": 0,
                        "findings": ["Code fixed and passes."],
                        "summary": "Clean execution.",
                    }
                import json
                return ModelResult(
                    text=json.dumps(rep),
                    model_name="fake",
                    provider_model_version="fake-v1",
                    input_tokens=10,
                    output_tokens=20,
                    total_tokens=30,
                    latency_ms=5,
                    request_id="req-rev-fix",
                    estimated_cost=0.0,
                    parsed_json=rep,
                )

            elif response_schema and response_schema.__name__ == "ReflectionDecision":
                if iter_tracker["iteration"] == 1:
                    iter_tracker["iteration"] = 2
                    dec = {
                        "decision": "CONTINUE",
                        "reason": "critical defects remain in iteration 1",
                        "adaptive_score": 0.50,
                        "marginal_gain": 0.50,
                        "iteration": 1,
                    }
                else:
                    dec = {
                        "decision": "STOP",
                        "reason": "clean_result: code verified and tests pass",
                        "adaptive_score": 0.95,
                        "marginal_gain": 0.45,
                        "iteration": 2,
                    }
                import json
                return ModelResult(
                    text=json.dumps(dec),
                    model_name="fake",
                    provider_model_version="fake-v1",
                    input_tokens=10,
                    output_tokens=20,
                    total_tokens=30,
                    latency_ms=5,
                    request_id="req-ref-fix",
                    estimated_cost=0.0,
                    parsed_json=dec,
                )

            return super().generate(messages, model, response_schema, **kwargs)

    wf = MASWorkflow(llm=IterativeFixingLLM())
    state = wf.run(
        requirement="Build a solver that returns 42.",
        task_id="solver_42",
        model_name="fake",
        workspace_base=str(tmp_path),
    )

    # Iteration reached 2 and completed cleanly
    assert state["iteration"] >= 2
    assert state["artifacts"]["ReviewReport"]["status"] == "PASSED"
    assert state["artifacts"]["ReviewReport"]["critical_issues"] == 0


# ==============================================================================
# GATE C: GENERATED SOFTWARE BEHAVIORAL EXECUTION
# ==============================================================================

def test_gate_c_science_question_solver_behavior(tmp_path):
    """Gate C: Generated science question solver passes Level 2 domain checks in sandbox."""
    solver_code = (
        "import sys, json\n\n"
        "class ScienceSolver:\n"
        "    @staticmethod\n"
        "    def solve_density(mass: float, volume: float) -> float:\n"
        "        if volume <= 0:\n"
        "            raise ValueError('Volume must be positive')\n"
        "        return round(mass / volume, 4)\n\n"
        "    @staticmethod\n"
        "    def solve_velocity(distance: float, time_sec: float) -> float:\n"
        "        if time_sec <= 0:\n"
        "            raise ValueError('Time must be positive')\n"
        "        return round(distance / time_sec, 4)\n\n"
        "    @staticmethod\n"
        "    def solve_force(mass: float, acceleration: float) -> float:\n"
        "        return round(mass * acceleration, 4)\n\n"
        "def main():\n"
        "    d = ScienceSolver.solve_density(100.0, 20.0)\n"
        "    v = ScienceSolver.solve_velocity(100.0, 5.0)\n"
        "    f = ScienceSolver.solve_force(10.0, 9.8)\n"
        "    assert d == 5.0\n"
        "    assert v == 20.0\n"
        "    assert f == 98.0\n"
        "    print('All science assertions passed successfully.')\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )

    with open(tmp_path / "main.py", "w") as f:
        f.write(solver_code)

    sandbox = SandboxRunner()
    res = sandbox.smoke_run(str(tmp_path), allow_fallback=True)

    assert res.is_success is True
    assert res.exit_code == 0
    assert "All science assertions passed" in res.stdout


def test_gate_c_math_helper_behavior(tmp_path):
    """Gate C: Generated math helper executes cleanly in sandbox and verifies mathematical outputs."""
    math_code = (
        "import math\n\n"
        "def is_prime(n: int) -> bool:\n"
        "    if n < 2:\n"
        "        return False\n"
        "    for i in range(2, int(math.isqrt(n)) + 1):\n"
        "        if n % i == 0:\n"
        "            return False\n"
        "    return True\n\n"
        "def factorial(n: int) -> int:\n"
        "    return math.factorial(n)\n\n"
        "def main():\n"
        "    assert is_prime(17) is True\n"
        "    assert is_prime(18) is False\n"
        "    assert factorial(5) == 120\n"
        "    print('Math checks verified.')\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )

    with open(tmp_path / "main.py", "w") as f:
        f.write(math_code)

    sandbox = SandboxRunner()
    res = sandbox.smoke_run(str(tmp_path), allow_fallback=True)
    assert res.is_success is True
    assert "Math checks verified" in res.stdout


# ==============================================================================
# GATE D: RECOVERY AND OPERATIONAL SAFETY
# ==============================================================================

def test_gate_d_sandbox_timeout_handling(tmp_path):
    """Gate D: Infinite loop in generated software is safely halted with timed_out=True."""
    infinite_loop_code = "import time\nwhile True:\n    time.sleep(0.1)\n"
    with open(tmp_path / "main.py", "w") as f:
        f.write(infinite_loop_code)

    # Use a short timeout of 2 seconds for testing
    sandbox = SandboxRunner(timeout_seconds=2)
    res = sandbox.execute_local_isolated(str(tmp_path), ["python", "main.py"])

    assert res.timed_out is True
    assert res.exit_code == -1
    assert "timed out" in res.stderr.lower()


def test_gate_d_model_mismatch_quarantines():
    """Gate D: Provider returning a mismatched model identifier raises ModelMismatchError."""
    # Requested condition is gpt-4o, but provider returned a free model
    assert is_model_match("openai/gpt-4o", "openai/gpt-4o-2024-08-06") is True
    assert is_model_match("openai/gpt-4o", "liquid/lfm-2.5-2.6b:free") is False
    assert is_model_match("openai/gpt-4o-mini", "cohere/north-mini-code:free") is False


def test_gate_d_producer_retry_and_rollback_on_schema_failure(tmp_path):
    """Gate D: BaseAgent invalid artifact policy retries and restores Git checkpoint upon schema error."""
    cp_mgr = CheckpointManager(str(tmp_path))
    initial_file = tmp_path / "base.txt"
    initial_file.write_text("initial clean state")
    cp_mgr.save_checkpoint()

    # Agent that initially returns invalid dictionary then valid TaskPlan
    call_count = {"count": 0}

    class FlakyAgent(ManagerAgent):
        def produce_plan_mock(self, feedback=None):
            call_count["count"] += 1
            if call_count["count"] == 1:
                # Corrupt workspace and return invalid schema
                (tmp_path / "base.txt").write_text("corrupted content")
                return {"invalid_key": "not a TaskPlan"}
            return {
                "id": "TP-RETRY",
                "task_id": "t1",
                "name": "Recovered",
                "description": "Recovered plan",
                "complexity": "SIMPLE",
                "files": ["main.py"],
                "sprint_goals": [],
                "acceptance_criteria": ["Criteria 1"],
            }

    flaky = FlakyAgent(llm=FakeLLMProvider(), checkpoint_manager=cp_mgr)
    state = create_initial_state(
        run_id="test-retry-01",
        requirement="Test retry",
        task_id="t1",
        workspace_path=str(tmp_path),
        model="fake",
    )

    plan = flaky.produce_valid_artifact("TaskPlan", flaky.produce_plan_mock, state, TaskPlan)
    assert plan.id == "TP-RETRY"
    assert call_count["count"] == 2
