"""Neutral shared fixed test runner (Level 1 smoke test + Level 2 fixed checks)."""

import json
import os
import sys
from typing import Any, Dict, List, Tuple
from mas.analysis.sandbox import SandboxRunner


class SharedTestHarness:
    """Neutral black-box evaluator.

    NEVER uses MAS-generated pytest or ChatDev-generated tests.
    """

    def __init__(self, checks_path: str = "eval/checks/level2_checks.json", sandbox_runner: SandboxRunner = None):
        self.checks_path = checks_path
        self.sandbox = sandbox_runner or SandboxRunner()
        self._checks_cache = None

    def _load_checks(self) -> List[Dict[str, Any]]:
        if self._checks_cache is None:
            if os.path.exists(self.checks_path):
                try:
                    with open(self.checks_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self._checks_cache = data.get("checks", [])
                except Exception:
                    self._checks_cache = []
            else:
                self._checks_cache = []
        return self._checks_cache

    def run_level1_smoke(self, workspace_path: str) -> float:
        """Level 1: Verifies generated python project can be parsed and executed without crash."""
        entry_points = ["main.py", "app.py", "calculator.py"]
        chosen = None
        for ep in entry_points:
            if os.path.exists(os.path.join(workspace_path, ep)):
                chosen = ep
                break
        if not chosen:
            for f in os.listdir(workspace_path):
                if f.endswith(".py") and not f.startswith("test_"):
                    chosen = f
                    break
        if not chosen:
            # Check for neutral web entry point if present
            if os.path.exists(os.path.join(workspace_path, "index.html")):
                return 1.0
            return 0.0

        res = self.sandbox.smoke_run(workspace_path, entry_point=chosen, allow_fallback=True)
        return 1.0 if res.is_success else 0.0

    def run_level2_checks(self, workspace_path: str, task_id: str) -> Tuple[float, int, int]:
        """Level 2: Runs fixed predetermined black-box checks for task_id."""
        checks = self._load_checks()
        task_checks = [c for c in checks if c.get("task_id") == task_id]
        if not task_checks:
            return 1.0, 0, 0  # No Level 2 checks defined -> defaults to Level 1

        passed = 0
        for chk in task_checks:
            expected_code = chk.get("expected_exit_code", 0)
            if "test_script" in chk:
                script_path = os.path.abspath(chk["test_script"])
                cmd = [sys.executable, script_path, os.path.abspath(workspace_path)]
            else:
                cmd = chk.get("command", ["python", "main.py"])

            res = self.sandbox.execute(workspace_path, cmd, allow_fallback=True)
            if res.exit_code == expected_code:
                # Check stdout keywords if required
                expected_keywords = chk.get("expected_stdout_contains", [])
                if not expected_keywords or all(kw in res.stdout for kw in expected_keywords):
                    passed += 1

        fraction = passed / len(task_checks)
        return round(fraction, 4), passed, len(task_checks)

    def evaluate(self, workspace_path: str, task_id: str = "custom") -> Dict[str, Any]:
        """SharedTest = 0.5 * Level1 + 0.5 * Level2 (or Level1 if no Level2 checks exist)."""
        l1_score = self.run_level1_smoke(workspace_path)
        l2_score, passed, total = self.run_level2_checks(workspace_path, task_id)

        if total > 0:
            final_score = round(0.5 * l1_score + 0.5 * l2_score, 4)
        else:
            final_score = l1_score

        return {
            "score": final_score,
            "level1_score": l1_score,
            "level2_score": l2_score,
            "level2_passed": passed,
            "level2_total": total,
        }
