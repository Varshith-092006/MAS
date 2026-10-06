"""Static analysis tools runner: Ruff, Bandit, and Radon."""

import json
import os
import shutil
import subprocess
from typing import Any, Dict


class QualityTools:
    """Wraps static code quality tools for execution."""

    @staticmethod
    def run_ruff(target_dir: str) -> Dict[str, Any]:
        """Runs ruff linter and returns violation counts."""
        if not shutil.which("ruff"):
            return {"violations": 0, "status": "skipped", "details": []}

        try:
            res = subprocess.run(
                ["ruff", "check", target_dir, "--output-format=json"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            data = json.loads(res.stdout) if res.stdout else []
            return {
                "violations": len(data),
                "status": "success",
                "details": data[:10],
            }
        except Exception as e:
            return {"violations": 0, "status": "error", "error": str(e)}

    @staticmethod
    def run_bandit(target_dir: str) -> Dict[str, Any]:
        """Runs bandit security analyzer and returns severity counts."""
        if not shutil.which("bandit"):
            return {"high": 0, "medium": 0, "low": 0, "status": "skipped"}

        try:
            res = subprocess.run(
                ["bandit", "-r", target_dir, "-f", "json", "-q"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            data = json.loads(res.stdout) if res.stdout else {}
            results = data.get("results", [])
            high = sum(1 for r in results if r.get("issue_severity") == "HIGH")
            med = sum(1 for r in results if r.get("issue_severity") == "MEDIUM")
            low = sum(1 for r in results if r.get("issue_severity") == "LOW")
            return {
                "high": high,
                "medium": med,
                "low": low,
                "status": "success",
                "results_count": len(results),
            }
        except Exception as e:
            return {"high": 0, "medium": 0, "low": 0, "status": "error", "error": str(e)}

    @staticmethod
    def run_radon(target_dir: str) -> Dict[str, Any]:
        """Runs radon maintainability index calculation."""
        if not shutil.which("radon"):
            return {"mean_mi": 100.0, "status": "skipped"}

        try:
            res = subprocess.run(
                ["radon", "mi", target_dir, "-j"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            data = json.loads(res.stdout) if res.stdout else {}
            mi_values = [v.get("mi", 100.0) for v in data.values() if isinstance(v, dict)]
            mean_mi = sum(mi_values) / len(mi_values) if mi_values else 100.0
            return {
                "mean_mi": round(mean_mi, 2),
                "status": "success",
                "file_scores": data,
            }
        except Exception as e:
            return {"mean_mi": 100.0, "status": "error", "error": str(e)}

    @classmethod
    def run_all(cls, target_dir: str) -> Dict[str, Any]:
        return {
            "ruff": cls.run_ruff(target_dir),
            "bandit": cls.run_bandit(target_dir),
            "radon": cls.run_radon(target_dir),
        }

    @staticmethod
    def normalize_ruff(violations: int) -> float:
        """LLD Sec. 7.4: Ruff = 1 - min(violations / 10, 1)."""
        return round(max(0.0, 1.0 - min(violations / 10.0, 1.0)), 4)

    @staticmethod
    def normalize_bandit(high: int, medium: int = 0, low: int = 0) -> float:
        """LLD Sec. 7.4: Bandit = 1 - min((3*High + 2*Medium + 1*Low) / 10, 1)."""
        weighted = 3.0 * high + 2.0 * medium + 1.0 * low
        return round(max(0.0, 1.0 - min(weighted / 10.0, 1.0)), 4)

    @staticmethod
    def normalize_radon(mean_mi: float) -> float:
        """LLD Sec. 7.4: Radon = clip(mean_mi / 100, 0, 1)."""
        return round(max(0.0, min(mean_mi / 100.0, 1.0)), 4)

    @staticmethod
    def normalize_reviewer(critical: int, major: int = 0) -> float:
        """LLD Sec. 7.4: Reviewer = 1 - min((3*critical + 1*major) / 6, 1)."""
        weighted = 3.0 * critical + 1.0 * major
        return round(max(0.0, 1.0 - min(weighted / 6.0, 1.0)), 4)
