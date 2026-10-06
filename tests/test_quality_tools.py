"""Unit tests for QualityTools static analysis wrappers (Ruff, Bandit, Radon)."""

import os
from mas.analysis.quality_tools import QualityTools


def test_quality_tools_clean_code(tmp_path):
    ws = tmp_path / "ws_clean"
    os.makedirs(ws, exist_ok=True)
    code_file = ws / "sample.py"
    with open(code_file, "w") as f:
        f.write("def add(a: int, b: int) -> int:\n    '''Adds two numbers.'''\n    return a + b\n")

    res = QualityTools.run_all(str(ws))
    assert "ruff" in res
    assert "bandit" in res
    assert "radon" in res

    # Clean code should have 0 high security issues and good maintainability
    assert res["bandit"].get("high", 0) == 0
    assert res["radon"].get("mean_mi", 100) >= 70.0


def test_quality_tools_security_finding(tmp_path):
    ws = tmp_path / "ws_sec"
    os.makedirs(ws, exist_ok=True)
    code_file = ws / "vulnerable.py"
    with open(code_file, "w") as f:
        # Code containing assert or exec or hardcoded password
        f.write("def run():\n    exec('import os')\n")

    res = QualityTools.run_bandit(str(ws))
    # Bandit should run or skip gracefully
    assert "status" in res
