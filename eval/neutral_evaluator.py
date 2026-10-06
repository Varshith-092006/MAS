"""Hidden Neutral Evaluator: Evaluates generated software independently from MAS and ChatDev."""

import hashlib
import os
from typing import Any, Dict, Optional

from eval.scorers.icoder_metrics import (
    calculate_completeness,
    calculate_executability,
    calculate_consistency,
    calculate_quality,
)
from eval.scorers.shared_test import SharedTestHarness
from mas.analysis.quality_tools import QualityTools
from mas.analysis.sandbox import SandboxRunner
from mas.db.models import Metric, ConfigSnapshot
from mas.db.session import get_session


def compute_checks_file_hash(checks_path: str = "eval/checks/level2_checks.json") -> str:
    """Computes SHA-256 hash of the neutral evaluator checks file."""
    if not os.path.exists(checks_path):
        return "0" * 64
    with open(checks_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class NeutralEvaluator:
    """Independent Neutral Evaluator executing outside the MAS generation loop."""

    def __init__(
        self,
        checks_path: str = "eval/checks/level2_checks.json",
        sandbox_runner: Optional[SandboxRunner] = None,
    ):
        self.checks_path = checks_path
        self.sandbox = sandbox_runner or SandboxRunner()
        self.shared_harness = SharedTestHarness(checks_path=checks_path, sandbox_runner=self.sandbox)
        self.checks_hash = compute_checks_file_hash(checks_path)

    def evaluate_project(
        self,
        workspace_path: str,
        requirement: str,
        task_id: str = "custom",
        run_id: Optional[str] = None,
        persist_to_db: bool = True,
    ) -> Dict[str, Any]:
        """Runs the standardized neutral evaluation battery on the generated project."""
        abs_workspace = os.path.abspath(workspace_path)

        # 1. Read aggregate code text for embedding consistency
        code_snippets = []
        for root, _, files in os.walk(abs_workspace):
            if any(skip in root for skip in [".git", "__pycache__", ".mas_snapshots"]):
                continue
            for f in files:
                if f.endswith(".py"):
                    try:
                        with open(os.path.join(root, f), "r", encoding="utf-8") as fh:
                            code_snippets.append(fh.read())
                    except Exception:
                        pass
        full_code = "\n\n".join(code_snippets)

        # 2. iCoder-style metrics
        completeness = calculate_completeness(abs_workspace)
        executability = calculate_executability(abs_workspace, self.sandbox)
        consistency = calculate_consistency(requirement, full_code)
        quality = calculate_quality(completeness, executability, consistency)

        # 3. Shared fixed tests (Level 1 + Level 2)
        shared_test_res = self.shared_harness.evaluate(abs_workspace, task_id=task_id)

        # 4. Neutral static analysis tools
        tools_res = QualityTools.run_all(abs_workspace)
        ruff_violations = tools_res["ruff"].get("violations", 0)
        bandit_high = tools_res["bandit"].get("high", 0)
        radon_mi = tools_res["radon"].get("mean_mi", 100.0)

        results = {
            "completeness": completeness,
            "executability": executability,
            "consistency": consistency,
            "quality": quality,
            "shared_test": shared_test_res["score"],
            "ruff_violations": ruff_violations,
            "bandit_high": bandit_high,
            "radon_mi": radon_mi,
            "checks_file_hash": self.checks_hash,
        }

        # 5. Persist to database with scope = 'neutral'
        if persist_to_db and run_id:
            try:
                with get_session() as session:
                    metric_rows = [
                        Metric(run_id=run_id, metric_name="completeness", metric_value=completeness, scope="neutral"),
                        Metric(run_id=run_id, metric_name="executability", metric_value=executability, scope="neutral"),
                        Metric(run_id=run_id, metric_name="consistency", metric_value=consistency, scope="neutral"),
                        Metric(run_id=run_id, metric_name="quality", metric_value=quality, scope="neutral"),
                        Metric(run_id=run_id, metric_name="shared_test", metric_value=shared_test_res["score"], scope="neutral"),
                        Metric(run_id=run_id, metric_name="ruff", metric_value=float(ruff_violations), scope="neutral"),
                        Metric(run_id=run_id, metric_name="bandit", metric_value=float(bandit_high), scope="neutral"),
                        Metric(run_id=run_id, metric_name="radon", metric_value=float(radon_mi), scope="neutral"),
                    ]
                    session.add_all(metric_rows)

                    # Update config snapshot with checks file hash
                    snap = session.query(ConfigSnapshot).filter(ConfigSnapshot.run_id == run_id).first()
                    if snap:
                        snap.checks_file_hash = self.checks_hash
                    session.commit()
            except Exception:
                pass

        return results
