"""Unit tests for AST dependency analysis, cycle detection, and impact sets."""

from mas.analysis.ast_analyzer import ASTAnalyzer


def test_synthetic_circular_dependency():
    """Verify that synthetic circular dependency A -> B -> C -> A is detected."""
    analyzer = ASTAnalyzer()

    files = {
        "A.py": "import B\ndef func_a(): return B.func_b()",
        "B.py": "import C\ndef func_b(): return C.func_c()",
        "C.py": "import A\ndef func_c(): return A.func_a()",
    }

    graph, unresolved = analyzer.build_dependency_graph(files)
    assert "B" in graph["A"]
    assert "C" in graph["B"]
    assert "A" in graph["C"]

    cycles = analyzer.find_cycles(graph)
    assert len(cycles) > 0, "Circular dependency must be detected"

    cycle = cycles[0]
    # Check that cycle loops back to origin
    assert cycle[0] == cycle[-1]
    assert set(cycle) == {"A", "B", "C"}


def test_unresolved_imports_detection():
    analyzer = ASTAnalyzer()
    files = {
        "module1.py": "import non_existent_pkg\nfrom external_module import foo\ndef bar(): pass",
    }
    graph, unresolved = analyzer.build_dependency_graph(files)
    assert "module1" in unresolved
    unresolved_list = unresolved["module1"]
    assert any("non_existent_pkg" in u or "external_module" in u for u in unresolved_list)


def test_impact_analysis_transitive():
    analyzer = ASTAnalyzer()
    # Chain: A imports B, B imports C
    # Changing C should transitively impact B and A
    files = {
        "A.py": "import B",
        "B.py": "import C",
        "C.py": "x = 42",
        "D.py": "y = 100",  # independent
    }
    graph, _ = analyzer.build_dependency_graph(files)
    impacted = analyzer.compute_impact_set(graph, ["C"])

    assert "B" in impacted
    assert "A" in impacted
    assert "D" not in impacted
