"""Deterministic AST dependency analyzer, cycle detector, and impact set calculator."""

import ast
import os
from typing import Dict, List, Set, Tuple


class ASTAnalyzer:
    """Performs deterministic structural code analysis using Python's ast module."""

    def __init__(self, workspace_path: str = "."):
        self.workspace_path = os.path.abspath(workspace_path)

    def extract_imports(self, code: str, filepath: str = "") -> Tuple[Set[str], Set[str]]:
        """Extracts imported module names and detects syntax errors or unresolved imports.

        Returns (all_imports, unresolved_or_syntax_errors).
        """
        imports = set()
        errors = set()

        try:
            tree = ast.parse(code, filename=filepath)
        except SyntaxError as e:
            errors.add(f"SyntaxError in {filepath}: {e.msg} (line {e.lineno})")
            return imports, errors

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])
                elif node.level > 0:
                    # Relative import e.g. from . import foo
                    imports.add(f"relative_level_{node.level}")

        return imports, errors

    def build_dependency_graph(
        self, files: Dict[str, str]
    ) -> Tuple[Dict[str, Set[str]], Dict[str, List[str]]]:
        """Builds directed dependency graph: module -> set of internal modules it imports.

        Also records unresolved/external imports per module.
        """
        graph: Dict[str, Set[str]] = {}
        unresolved: Dict[str, List[str]] = {}

        # Known local module names from provided files (e.g. 'calc.py' -> 'calc')
        local_modules = {
            os.path.splitext(os.path.basename(f))[0]: f for f in files.keys()
        }

        for fname, code in files.items():
            mod_name = os.path.splitext(os.path.basename(fname))[0]
            graph[mod_name] = set()
            unresolved[mod_name] = []

            imported_names, parse_errors = self.extract_imports(code, fname)
            if parse_errors:
                unresolved[mod_name].extend(parse_errors)

            for imp in imported_names:
                if imp in local_modules and imp != mod_name:
                    graph[mod_name].add(imp)
                elif not imp.startswith("relative_level_"):
                    # Record external or unresolvable module
                    unresolved[mod_name].append(imp)

        return graph, unresolved

    def find_cycles(self, graph: Dict[str, Set[str]]) -> List[List[str]]:
        """Three-color DFS algorithm to detect directed dependency cycles."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {v: WHITE for v in graph}
        stack: List[str] = []
        cycles: List[List[str]] = []

        def dfs(u: str):
            color[u] = GRAY
            stack.append(u)

            for v in graph.get(u, set()):
                if color.get(v, WHITE) == WHITE:
                    dfs(v)
                elif color.get(v, WHITE) == GRAY:
                    # Detected cycle: slice from first occurrence of v in stack
                    idx = stack.index(v)
                    cycle_path = stack[idx:] + [v]
                    cycles.append(cycle_path)

            stack.pop()
            color[u] = BLACK

        for node in list(graph.keys()):
            if color[node] == WHITE:
                dfs(node)

        return cycles

    def compute_impact_set(
        self, graph: Dict[str, Set[str]], changed_modules: List[str]
    ) -> Set[str]:
        """Calculates transitive impact set: all modules that depend directly or

        indirectly on changed_modules (transitive closure on reverse dependency graph).
        """
        # Build reverse graph: who imports mod?
        reverse_graph: Dict[str, Set[str]] = {m: set() for m in graph}
        for u, neighbors in graph.items():
            for v in neighbors:
                if v not in reverse_graph:
                    reverse_graph[v] = set()
                reverse_graph[v].add(u)

        impacted: Set[str] = set()
        queue = list(changed_modules)
        visited = set(changed_modules)

        while queue:
            curr = queue.pop(0)
            for dependent in reverse_graph.get(curr, set()):
                if dependent not in visited:
                    visited.add(dependent)
                    impacted.add(dependent)
                    queue.append(dependent)

        return impacted

    def analyze_workspace(self, workspace_path: str) -> Dict[str, any]:
        """Scans workspace directory, builds graph, finds cycles and unresolved imports."""
        py_files: Dict[str, str] = {}
        for root, _, filenames in os.walk(workspace_path):
            if any(skip in root for skip in [".git", "__pycache__", ".mas_snapshots"]):
                continue
            for f in filenames:
                if f.endswith(".py"):
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, workspace_path)
                    try:
                        with open(full_p, "r", encoding="utf-8") as fh:
                            py_files[rel_p] = fh.read()
                    except Exception:
                        pass

        graph, unresolved = self.build_dependency_graph(py_files)
        cycles = self.find_cycles(graph)

        return {
            "module_count": len(graph),
            "dependency_graph": {k: list(v) for k, v in graph.items()},
            "unresolved_imports": unresolved,
            "cycles": cycles,
            "has_cycles": len(cycles) > 0,
            "summary": f"{len(graph)} modules, {len(cycles)} cycles detected",
        }
