"""Unit and contract tests for Level 1 Evaluator Protocol (v1.2 vs v1.3).

Verifies:
  1. Generic Level 1 smoke check handles supported application types cleanly.
  2. Argparse CLI startup is confirmed via --help and temporary fixture.
  3. Legacy v1.2 evaluation is preserved without modification (returns E=0.0 on CLI usage exit).
  4. True-negative outcomes are strictly preserved on deliberate failure fixtures:
     - Syntax errors
     - Missing imports / dependencies
     - Unhandled startup exceptions
     - Broken CLI grammar / crashing --help
"""

import os
import pytest
from eval.neutral_evaluator import NeutralEvaluator
from eval.scorers.icoder_metrics import (
    calculate_executability_v1_2,
    calculate_executability_v1_3,
    calculate_executability,
)


def test_normal_script_executability(tmp_path):
    ws = tmp_path / "normal_script"
    ws.mkdir()
    (ws / "main.py").write_text("def run(): return 42\nif __name__ == '__main__': run()\n", encoding="utf-8")

    assert calculate_executability_v1_2(str(ws)) == 1.0
    assert calculate_executability_v1_3(str(ws)) == 1.0
    assert calculate_executability(str(ws), version="v1.2") == 1.0
    assert calculate_executability(str(ws), version="v1.3") == 1.0


def test_argparse_cli_requires_file_argument(tmp_path):
    ws = tmp_path / "argparse_cli"
    ws.mkdir()
    code = (
        "import sys, argparse\n"
        "parser = argparse.ArgumentParser(description='File processor')\n"
        "parser.add_argument('input_file', help='Path to file')\n"
        "def main():\n"
        "    args = parser.parse_args()\n"
        "    print('Processing', args.input_file)\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )
    (ws / "main.py").write_text(code, encoding="utf-8")

    # Legacy v1.2 assigns 0.0 because zero-arg invocation exits with SystemExit(2)
    assert calculate_executability_v1_2(str(ws)) == 0.0
    assert calculate_executability(str(ws), version="v1.2") == 0.0

    # Protocol v1.3 verifies --help and temporary fixture, confirming startup (E=1.0)
    assert calculate_executability_v1_3(str(ws)) == 1.0
    assert calculate_executability(str(ws), version="v1.3") == 1.0


def test_failure_fixture_syntax_error(tmp_path):
    ws = tmp_path / "fail_syntax"
    ws.mkdir()
    (ws / "main.py").write_text("def broken(\n  syntax error here\n", encoding="utf-8")

    # True negative: must fail in both versions
    assert calculate_executability_v1_2(str(ws)) == 0.0
    assert calculate_executability_v1_3(str(ws)) == 0.0


def test_failure_fixture_missing_import(tmp_path):
    ws = tmp_path / "fail_import"
    ws.mkdir()
    (ws / "main.py").write_text("import definitely_non_existent_package_xyz_999\n", encoding="utf-8")

    # True negative: must fail in both versions
    assert calculate_executability_v1_2(str(ws)) == 0.0
    assert calculate_executability_v1_3(str(ws)) == 0.0


def test_failure_fixture_startup_crash(tmp_path):
    ws = tmp_path / "fail_crash"
    ws.mkdir()
    code = (
        "def main():\n"
        "    raise RuntimeError('Catastrophic initialization failure!')\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )
    (ws / "main.py").write_text(code, encoding="utf-8")

    # True negative: unhandled exception causes traceback
    assert calculate_executability_v1_2(str(ws)) == 0.0
    assert calculate_executability_v1_3(str(ws)) == 0.0


def test_failure_fixture_crashing_help(tmp_path):
    ws = tmp_path / "fail_help"
    ws.mkdir()
    code = (
        "import sys, argparse\n"
        "class CrashingParser(argparse.ArgumentParser):\n"
        "    def print_help(self, file=None):\n"
        "        raise ValueError('Corrupted help generator')\n"
        "parser = CrashingParser()\n"
        "parser.add_argument('file')\n"
        "def main():\n"
        "    parser.parse_args()\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )
    (ws / "main.py").write_text(code, encoding="utf-8")

    # True negative: crashing on --help must result in E=0.0
    assert calculate_executability_v1_3(str(ws)) == 0.0


def test_evaluator_version_preservation_and_reporting(tmp_path):
    ws = tmp_path / "ws_eval"
    ws.mkdir()
    (ws / "main.py").write_text("print('hello')\n", encoding="utf-8")

    ev_v12 = NeutralEvaluator(version="v1.2")
    assert ev_v12.version == "v1.2"
    res_v12 = ev_v12.evaluate_project(str(ws), "greeting script", persist_to_db=False)
    assert res_v12["evaluator_version"] == "v1.2"

    ev_v13 = NeutralEvaluator(version="v1.3")
    assert ev_v13.version == "v1.3"
    res_v13 = ev_v13.evaluate_project(str(ws), "greeting script", persist_to_db=False)
    assert res_v13["evaluator_version"] == "v1.3"
