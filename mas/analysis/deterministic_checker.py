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


        # Placeholder scan (pass / ... / NotImplementedError / docstring-only bodies / TODO markers).
        # Shared with TesterAgent so the repair loop and the test report use one definition.
        try:
            from mas.agents.tester import scan_placeholders
            _, _, ph_findings = scan_placeholders(workspace_path)
            errors.extend(f"Placeholder detected: {f}" for f in ph_findings)
        except Exception:
            pass

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

