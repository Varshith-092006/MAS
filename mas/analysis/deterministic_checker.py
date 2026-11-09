"""Deterministic code and workspace verification module.

Performs cheap local AST, placeholder, entry-point, and smoke run checks
before making expensive LLM calls.
"""

import ast
import os
from typing import Dict, List, Optional


class DeterministicRepairChecker:
    """Performs deterministic offline checks on workspace code."""

    @staticmethod
    def run_checks(workspace_path: str, run_smoke: bool = True) -> List[str]:
        """Runs fast offline structural and execution checks on workspace.

        Returns a list of human-readable defect descriptions, or [] if clean.
        """
        errors: List[str] = []
        if not workspace_path or not os.path.exists(workspace_path):
            return ["Workspace path does not exist."]

        py_files: Dict[str, str] = {}
        for root, _, files in os.walk(workspace_path):
            if any(x in root for x in [".git", "__pycache__", ".mas_snapshots"]):
                continue
            for f in files:
                if f.endswith(".py"):
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, workspace_path).replace("\\", "/")
                    try:
                        with open(full_p, "r", encoding="utf-8") as fh:
                            py_files[rel_p] = fh.read()
                    except Exception as e:
                        errors.append(f"Cannot read file {rel_p}: {e}")

        # Check 1: Missing main.py entry point
        has_main = ("main.py" in py_files) or any(f.endswith("main.py") for f in py_files)
        if not has_main:
            errors.append("Missing required entry point: main.py is required.")

        # Check 2: AST syntax parse & placeholder detection
        for fname, content in py_files.items():
            try:
                tree = ast.parse(content, filename=fname)
            except SyntaxError as se:
                errors.append(f"SyntaxError in {fname} line {se.lineno}: {se.msg}")
                continue

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Check empty 'pass' body
                    if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                        errors.append(f"Placeholder detected in {fname}: function '{node.name}' has empty 'pass' body.")
                    # Check ellipsis '...' body
                    elif (
                        len(node.body) == 1
                        and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)
                        and node.body[0].value.value is Ellipsis
                    ):
                        errors.append(f"Placeholder detected in {fname}: function '{node.name}' has ellipsis '...' body.")
                    # Check NotImplementedError body
                    elif len(node.body) == 1 and isinstance(node.body[0], ast.Raise):
                        exc = node.body[0].exc
                        exc_id = getattr(exc, "id", "") or getattr(getattr(exc, "func", None), "id", "")
                        if "NotImplemented" in str(exc_id):
                            errors.append(f"Placeholder detected in {fname}: function '{node.name}' raises NotImplementedError.")

        # Check 3: Fast sandbox smoke run
        if run_smoke and has_main and not any("SyntaxError" in e for e in errors):
            try:
                from mas.analysis.sandbox import SandboxRunner
                sandbox = SandboxRunner()
                smoke_res = sandbox.smoke_run(workspace_path, allow_fallback=True)
                if not smoke_res.is_success and smoke_res.exit_code != 0:
                    err_snippet = (smoke_res.stderr or smoke_res.stdout or "Non-zero exit code").strip()
                    if "Traceback" in err_snippet or "Error:" in err_snippet or smoke_res.exit_code != 0:
                        errors.append(f"Smoke run execution failed (exit code {smoke_res.exit_code}): {err_snippet[:300]}")
            except Exception:
                pass

        return errors

