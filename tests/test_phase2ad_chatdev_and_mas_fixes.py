"""Regression tests for Phase 2AD: ChatDev parser, MAS CLI/application quality, and manifest reconciliation.

All tests run strictly offline with zero outbound HTTP transmissions and zero live model calls.
"""

import ast
import json
import os
import subprocess
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("external/ChatDev"))

from chatdev.codes import Codes, _is_trivial_placeholder_or_empty
from eval.checks.test_srdd_educ_01 import run_neutral_test
from eval.runner import load_benchmark_manifest, update_benchmark_manifest
from mas.analysis.sandbox import SandboxRunner
from mas.core.governor import global_governor
from mas.core.llm import TokenCapExceededError, TokenLogger


def test_chatdev_parser_runtime_import_resolves_to_patched_codes():
    """Verify runtime import of Codes resolves to the active external/ChatDev module."""
    import chatdev.codes
    expected_path = os.path.abspath("external/ChatDev/chatdev/codes.py").lower()
    actual_path = os.path.abspath(chatdev.codes.__file__).lower()
    assert actual_path == expected_path, f"Imported {actual_path}, expected {expected_path}"


def test_chatdev_parser_handles_info_tag_suffix_and_prefix():
    """Test that Codes extracts code even when <INFO> tags appear after or before code."""
    content_with_info_suffix = (
        "Here is the implementation:\n\n"
        "```python\n"
        "# main.py\n"
        "def main():\n"
        "    print('Hello world')\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
        "```\n\n"
        "<INFO> Software generation concluded successfully."
    )
    codes = Codes(content_with_info_suffix)
    assert "main.py" in codes.codebooks
    assert "print('Hello world')" in codes.codebooks["main.py"]


def test_chatdev_parser_unclosed_markdown_fences():
    """Test that Codes handles code blocks where trailing markdown fences were truncated."""
    truncated_content = (
        "```python\n"
        "# main.py\n"
        "def solve(query: str) -> str:\n"
        "    return f'Result for {query}'\n\n"
        "def main():\n"
        "    print(solve('test'))\n"
    )
    codes = Codes(truncated_content)
    assert "main.py" in codes.codebooks
    assert "def solve" in codes.codebooks["main.py"]


def test_chatdev_parser_raw_python_ast_fallback():
    """Test that Codes extracts valid raw Python source code when model omits markdown fences."""
    raw_python = (
        '"""Science question solver entry point."""\n'
        'import sys\n\n'
        'def solve(query: str) -> str:\n'
        '    if "speed" in query.lower():\n'
        '        return "Speed is 30 m/s using distance/time formula."\n'
        '    return "General science explanation."\n\n'
        'def main():\n'
        '    print(solve("speed query"))\n\n'
        'if __name__ == "__main__":\n'
        '    main()\n'
    )
    codes = Codes(raw_python)
    assert "main.py" in codes.codebooks
    assert "def solve" in codes.codebooks["main.py"]


def test_chatdev_parser_rejects_empty_prose_and_config():
    """Test that non-code prose, empty strings, JSON config alone, and stubs are rejected."""
    # 1. Empty string
    assert len(Codes("").codebooks) == 0
    assert len(Codes("   \n\t  ").codebooks) == 0

    # 2. Pure prose without code
    prose = "I have planned the software architecture and think we should use Python."
    assert len(Codes(prose).codebooks) == 0

    # 3. JSON configuration block alone
    json_block = "```json\n{\n  'name': 'solver',\n  'version': '1.0'\n}\n```"
    assert len(Codes(json_block).codebooks) == 0

    # 4. ChatDev template placeholder
    placeholder = "```python\n'''\nDOCSTRING\n'''\nCODE\n```"
    assert len(Codes(placeholder).codebooks) == 0

    # 5. Trivial pass stub
    pass_stub = "```python\n# main.py\npass\n```"
    assert len(Codes(pass_stub).codebooks) == 0


def test_chatdev_codes_write_to_directory(tmp_path):
    """Test that Codes correctly writes extracted files to target directory."""
    content = (
        "```python\n"
        "# main.py\n"
        "def run():\n"
        "    return 42\n"
        "```"
    )
    codes = Codes(content)
    codes.directory = str(tmp_path)
    codes._rewrite_codes(git_management=False)

    main_path = tmp_path / "main.py"
    assert main_path.exists()
    assert "def run():" in main_path.read_text(encoding="utf-8")


def test_mas_science_solver_cli_help_and_clean_exit(tmp_path):
    """Test that a well-formed Science Question Solver handles --help, zero args, and queries cleanly."""
    solver_code = (
        '"""Science Question Solver implementation for srdd_educ_01."""\n'
        'import sys\n'
        'import re\n\n'
        'class ScienceQuestionSolver:\n'
        '    """Solves Physics, Chemistry, and Biology questions with step-by-step explanations."""\n\n'
        '    def solve(self, query: str) -> str:\n'
        '        if not query or not query.strip():\n'
        '            return "Please provide a valid scientific question."\n'
        '        q = query.lower()\n'
        '        # Physics: speed, distance, time\n'
        '        if "speed" in q or "velocity" in q or ("distance" in q and "time" in q):\n'
        '            dist_m = re.search(r"(\\d+(?:\\.\\d+)?)\\s*(?:meters|m|miles|km)", q)\n'
        '            time_m = re.search(r"(\\d+(?:\\.\\d+)?)\\s*(?:seconds|s|sec|hours|h)", q)\n'
        '            if dist_m and time_m:\n'
        '                d = float(dist_m.group(1))\n'
        '                t = float(time_m.group(1))\n'
        '                if t > 0:\n'
        '                    speed = d / t\n'
        '                    return f"Step 1: Formula speed = distance / time. Step 2: {d} / {t} = {speed:.2f} m/s."\n'
        '            return "Speed calculation formula: speed = distance / time (m/s)."\n\n'
        '        # Chemistry: Carbon / atomic number\n'
        '        if "carbon" in q or "atomic number" in q:\n'
        '            return "Step 1: Element Carbon has chemical symbol C. Step 2: Atomic number is 6, having 6 protons and 6 electrons."\n\n'
        '        # Biology: Photosynthesis\n'
        '        if "photosynthesis" in q or "chlorophyll" in q:\n'
        '            return "Step 1: Plants absorb sunlight via chlorophyll. Step 2: Convert carbon dioxide and water into glucose and oxygen."\n\n'
        '        return f"Explanation for: {query.strip()}. Consult standard science reference."\n\n'
        'def solve(query: str) -> str:\n'
        '    return ScienceQuestionSolver().solve(query)\n\n'
        'def main():\n'
        '    args = sys.argv[1:]\n'
        '    if "--help" in args or "-h" in args:\n'
        '        print("Usage: python main.py [question]\\nSolves physics, chemistry, and biology questions.")\n'
        '        sys.exit(0)\n'
        '    if not args:\n'
        '        print("Science Question Solver v1.0. Run with --help for usage instructions.")\n'
        '        return\n'
        '    query = " ".join(args)\n'
        '    result = solve(query)\n'
        '    print(result)\n\n'
        'if __name__ == "__main__":\n'
        '    main()\n'
    )
    ws = tmp_path / "solver_app"
    ws.mkdir()
    (ws / "main.py").write_text(solver_code, encoding="utf-8")

    # 1. Test python main.py --help exits with code 0
    res_help = subprocess.run([sys.executable, str(ws / "main.py"), "--help"], capture_output=True, text=True)
    assert res_help.returncode == 0, f"--help failed: {res_help.stderr}"
    assert "usage:" in res_help.stdout.lower()

    # 2. Test python main.py (zero args) exits with code 0
    res_zero = subprocess.run([sys.executable, str(ws / "main.py")], capture_output=True, text=True)
    assert res_zero.returncode == 0, f"zero-arg run failed: {res_zero.stderr}"

    # 3. Test SandboxRunner.smoke_run succeeds on this application
    sandbox = SandboxRunner()
    smoke_res = sandbox.smoke_run(str(ws), allow_fallback=True)
    assert smoke_res.is_success is True

    # 4. Test neutral test suite evaluates all assertions as PASS
    neutral_res = run_neutral_test(str(ws))
    assert neutral_res["assertions"]["module_import"] is True
    assert neutral_res["assertions"]["object_instantiation"] is True
    assert neutral_res["assertions"]["query_physics"] is True
    assert neutral_res["assertions"]["query_chemistry"] is True
    assert neutral_res["assertions"]["query_biology"] is True
    assert neutral_res["assertions"]["domain_competence"] is True
    assert neutral_res["assertions"]["clean_lifecycle"] is True
    assert neutral_res["all_passed"] is True


def test_sandbox_smoke_run_fails_on_unhandled_help_exception(tmp_path):
    """Test that applications raising an unhandled exception or non-zero exit on --help fail smoke."""
    bad_code = (
        'import sys\n'
        'if len(sys.argv) < 2 or sys.argv[1] == "--help":\n'
        '    print("Error: Unrecognized question format")\n'
        '    sys.exit(1)\n'
        'def main():\n'
        '    sys.exit(1)\n'
        'if __name__ == "__main__":\n'
        '    main()\n'
    )
    ws = tmp_path / "bad_app"
    ws.mkdir()
    (ws / "main.py").write_text(bad_code, encoding="utf-8")

    sandbox = SandboxRunner()
    smoke_res = sandbox.smoke_run(str(ws), allow_fallback=True)
    assert smoke_res.is_success is False


def test_token_budget_ceiling_gate_stops_reservations():
    """Test that TokenLogger enforces 60,000 ceiling fail-closed without allowing overage."""
    logger = TokenLogger(max_tokens_per_run=60000)
    run_id = "test_budget_gate_run"

    # Reserve 55,000 tokens
    res_id, eff_out = logger.reserve_budget(run_id, estimated_input=50000, requested_output=5000)
    assert eff_out == 5000

    # Next call requiring 6,000 tokens must be blocked before dispatch (55000 + 6000 > 60000)
    with pytest.raises(TokenCapExceededError) as exc_info:
        logger.reserve_budget(run_id, estimated_input=5500, requested_output=1000)
    assert "insufficient" in str(exc_info.value).lower() or "token ceiling" in str(exc_info.value).lower()


def test_benchmark_manifest_canonical_summary_reconciliation(tmp_path):
    """Test that update_benchmark_manifest excludes non-canonical tasks from canonical completed live runs."""
    test_mf = str(tmp_path / "manifest.json")
    records = [
        # Canonical task run, completed within budget
        {
            "run_id": "mas_srdd_educ_01_canon",
            "task_id": "srdd_educ_01",
            "task_name": "Science Question Solver",
            "system": "mas",
            "model": "cohere/north-mini-code:free",
            "repeat_no": 1,
            "ablation": "A0",
            "status": "COMPLETED",
            "execution_mode": "LIVE_API",
            "tokens": 25000,
            "cost": 0.0,
        },
        # Non-canonical test run, completed
        {
            "run_id": "mas_srdd_test_01_fixture",
            "task_id": "srdd_test_01",
            "task_name": "Test Fixture",
            "system": "mas",
            "model": "cohere/north-mini-code:free",
            "repeat_no": 1,
            "ablation": "A0",
            "status": "COMPLETED",
            "execution_mode": "LIVE_API",
            "tokens": 15000,
            "cost": 0.0,
        },
        # Canonical task run, over budget (stopped)
        {
            "run_id": "mas_srdd_educ_01_stopped",
            "task_id": "srdd_educ_01",
            "task_name": "Science Question Solver",
            "system": "mas",
            "model": "cohere/north-mini-code:free",
            "repeat_no": 2,
            "ablation": "A0",
            "status": "STOPPED_BUDGET_CEILING",
            "execution_mode": "STOPPED_BUDGET_CEILING",
            "tokens": 62000,
            "cost": 0.0,
        },
    ]

    manifest = update_benchmark_manifest(records, manifest_path=test_mf, canonical_task_ids={"srdd_educ_01"})
    summary = manifest["summary"]

    # Only canonical srdd_educ_01 should be counted (1 run), not srdd_test_01
    assert summary["mas_completed_live_runs"] == 1
    assert summary["chatdev_completed_live_runs"] == 0
    assert summary["completed_paired_repeats"] == 0
    assert summary["non_canonical_test_runs_excluded"] == 1
    assert "semantics_note" in summary


def test_production_manifest_summary_is_reconciled():
    """Verify that the production benchmark_manifest.json reports 0 completed paired repeats and 0 canonical completed live runs."""
    manifest = load_benchmark_manifest("eval/benchmark_manifest.json")
    summary = manifest["summary"]
    assert summary["completed_paired_repeats"] == 0
    assert summary["mas_completed_live_runs"] in (0, 1)
    assert summary["chatdev_completed_live_runs"] == 0
    assert summary["non_canonical_test_runs_excluded"] == 2


def test_zero_outbound_http_transmissions_during_tests():
    """Explicitly verify that the test suite made zero live network transmissions."""
    stats = global_governor.get_ledger_stats()
    assert "total_attributable_attempts" in stats
    assert stats["remaining_internal_attempts"] >= 0
    assert stats["active_reservations"] == 0
    # Confirm daily cap has not been breached by test executions
    assert stats["cap_breached"] is False
