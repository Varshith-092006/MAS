"""Unit tests for ContextSlicer."""

from mas.core.context import ContextSlicer
from mas.core.state import create_initial_state


def test_context_slicer_iteration_1():
    slicer = ContextSlicer()
    state = create_initial_state(run_id="run-ctx-1", requirement="simple task")
    state["iteration"] = 1
    state["artifacts"]["TaskPlan"] = {"files": ["main.py"]}

    workspace_files = {
        "main.py": "print('main')",
        "unused.py": "print('unused')",
    }
    graph = {"main": set(), "unused": set()}

    ctx = slicer.build_context(state, workspace_files, graph)
    assert "main.py" in ctx["files"]
    assert "unused.py" not in ctx["files"]


def test_context_slicer_iteration_2_ast_impact():
    slicer = ContextSlicer()
    state = create_initial_state(run_id="run-ctx-2", requirement="simple task")
    state["iteration"] = 2
    state["changed_files"] = ["models.py"]

    workspace_files = {
        "app.py": "import service",
        "service.py": "import models",
        "models.py": "class User: pass",
        "independent.py": "x = 10",
    }
    # Dependency graph: app -> service -> models
    graph = {
        "app": {"service"},
        "service": {"models"},
        "models": set(),
        "independent": set(),
    }

    ctx = slicer.build_context(state, workspace_files, graph)
    # Changed models.py transitively impacts service.py and app.py
    assert "models.py" in ctx["files"]
    assert "service.py" in ctx["files"]
    assert "app.py" in ctx["files"]
    assert "independent.py" not in ctx["files"]
