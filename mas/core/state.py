"""Shared LangGraph state definition for MAS workflow."""

from typing import Any, Dict, List, Optional, TypedDict


class MASState(TypedDict, total=False):
    run_id: str
    task_id: str
    requirement: str
    complexity: str  # "SIMPLE" or "STRUCTURED"
    complexity_score: int
    router_features: Dict[str, Any]
    architecture: Optional[Dict[str, Any]]
    sprint_plan: Optional[Dict[str, Any]]
    repo_snapshot: str
    workspace_path: str
    changed_files: List[str]
    relevant_uml: List[str]
    artifacts: Dict[str, Any]
    validation_errors: List[str]
    ast_report: Dict[str, Any]
    shared_test_report: Dict[str, Any]
    mas_pytest_report: Dict[str, Any]
    quality_report: Dict[str, Any]
    review_report: Dict[str, Any]
    iteration: int
    previous_adaptive_score: float
    marginal_gain: float
    stop_reason: Optional[str]
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: float
    status: str  # CREATED, RUNNING, COMPLETED, FAILED, CANCELLED


def create_initial_state(
    run_id: str,
    requirement: str,
    task_id: str = "custom",
    workspace_path: str = "./workspace",
    model: str = "gpt-4o",
) -> MASState:
    """Creates a blank, initialized MASState."""
    return MASState(
        run_id=run_id,
        task_id=task_id,
        requirement=requirement,
        model=model,
        complexity="SIMPLE",
        complexity_score=0,
        router_features={},
        architecture=None,
        sprint_plan=None,
        repo_snapshot="",
        workspace_path=workspace_path,
        changed_files=[],
        relevant_uml=[],
        artifacts={},
        validation_errors=[],
        ast_report={},
        shared_test_report={},
        mas_pytest_report={},
        quality_report={},
        review_report={},
        iteration=1,
        previous_adaptive_score=0.0,
        marginal_gain=0.0,
        stop_reason=None,
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        estimated_cost=0.0,
        status="RUNNING",
    )
