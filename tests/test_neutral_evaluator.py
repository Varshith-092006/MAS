"""Unit tests for NeutralEvaluator and iCoder-style metrics."""

import os
from eval.neutral_evaluator import NeutralEvaluator, compute_checks_file_hash
from eval.scorers.icoder_metrics import (
    calculate_completeness,
    calculate_executability,
    calculate_consistency,
    calculate_quality,
)
from eval.scorers.shared_test import SharedTestHarness


def test_completeness_calculation(tmp_path):
    ws = tmp_path / "ws_comp"
    os.makedirs(ws, exist_ok=True)

    # 1 implemented function, 1 pass-only unimplemented function
    with open(ws / "funcs.py", "w") as f:
        f.write(
            "def implemented(x):\n    return x * 2\n\n"
            "def unimplemented():\n    pass\n"
        )

    comp = calculate_completeness(str(ws))
    assert comp == 0.5


def test_executability_calculation(tmp_path):
    ws = tmp_path / "ws_exec"
    os.makedirs(ws, exist_ok=True)
    with open(ws / "main.py", "w") as f:
        f.write("print('working!')\n")

    execu = calculate_executability(str(ws))
    assert execu == 1.0


def test_consistency_calculation():
    req = "Build a mathematical calculator utility"
    code = "def add(a, b): return a + b\ndef calculate(op): pass"
    sim = calculate_consistency(req, code)
    assert 0.0 <= sim <= 1.0


def test_quality_multiplication():
    # Quality = Completeness * Executability * Consistency
    q = calculate_quality(0.8, 1.0, 0.5)
    assert round(q, 4) == 0.4


def test_checks_file_hash():
    h = compute_checks_file_hash("eval/checks/level2_checks.json")
    assert len(h) == 64  # SHA-256


def test_neutral_evaluator_isolated_run(tmp_path):
    ws = tmp_path / "ws_neutral"
    os.makedirs(ws, exist_ok=True)
    with open(ws / "main.py", "w") as f:
        f.write("def run(): return 42\nif __name__ == '__main__': run()\n")

    evaluator = NeutralEvaluator()
    res = evaluator.evaluate_project(
        workspace_path=str(ws),
        requirement="Write a python runner",
        persist_to_db=False,
    )
    assert "quality" in res
    assert "completeness" in res
    assert "executability" in res
    assert "consistency" in res
    assert "shared_test" in res
    assert "checks_file_hash" in res
