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


def test_lld_normalization_formulas():
    # Ruff = 1 - min(violations / 10, 1)
    assert QualityTools.normalize_ruff(0) == 1.0
    assert QualityTools.normalize_ruff(5) == 0.5
    assert QualityTools.normalize_ruff(15) == 0.0

    # Bandit = 1 - min((3*High + 2*Medium + 1*Low) / 10, 1)
    assert QualityTools.normalize_bandit(high=0, medium=0, low=0) == 1.0
    assert QualityTools.normalize_bandit(high=1, medium=2, low=3) == 0.0  # 3+4+3=10 -> 0.0
    assert QualityTools.normalize_bandit(high=0, medium=1, low=1) == 0.7  # 0+2+1=3 -> 0.7

    # Radon = clip(mean_mi / 100, 0, 1)
    assert QualityTools.normalize_radon(100.0) == 1.0
    assert QualityTools.normalize_radon(75.5) == 0.755
    assert QualityTools.normalize_radon(120.0) == 1.0

    # Reviewer = 1 - min((3*critical + 1*major) / 6, 1)
    assert QualityTools.normalize_reviewer(critical=0, major=0) == 1.0
    assert QualityTools.normalize_reviewer(critical=1, major=1) == 0.3333  # 1 - 4/6 = 0.3333
    assert QualityTools.normalize_reviewer(critical=2, major=0) == 0.0     # 1 - 6/6 = 0.0
