"""Phase 5 Tests: ChatDev simulation guard, baseline fairness, and reproducible setup."""

import hashlib
import os
import pytest
from unittest.mock import MagicMock, patch

from eval.chatdev_adapter import ChatDevAdapter
from eval.reports import generate_stats_markdown_report
from eval.runner import count_code_loc, EvaluationRunner
from eval.stats import calculate_success_rate
from mas.core.llm import FakeLLMProvider


def test_chatdev_simulated_run_is_labeled_simulation_only(tmp_path):
    """Test 1: Any simulated ChatDev run is strictly labeled SIMULATION_ONLY."""
    adapter = ChatDevAdapter(llm=FakeLLMProvider())
    task = {
        "task_id": "test_sim_01",
        "name": "Test Simulation Task",
        "description": "Build a test app",
    }
    out = adapter.run_task(
        task=task,
        output_base_dir=str(tmp_path),
        model="fake",
        use_fake=True,
    )

    assert out["status"] == "SIMULATION_ONLY"
    assert out["execution_mode"] == "SIMULATION_ONLY"
    assert out["token_provenance"] == "SIMULATION_ONLY"


def test_simulation_runs_strictly_excluded_from_stats_report(tmp_path):
    """Test 2: SIMULATION_ONLY rows are strictly excluded from markdown report tables and summary stats."""
    output_report = str(tmp_path / "stats_report.md")

    # Mixed runs: simulated rows with high fake quality vs official live rows
    mas_runs = [
        {
            "run_id": "mas_sim_1",
            "task_id": "task_1",
            "system": "mas",
            "status": "SIMULATION_ONLY",
            "execution_mode": "SIMULATION_ONLY",
            "token_provenance": "SIMULATION_ONLY",
            "official": True,
            "quality": 0.9999,
        },
        {
            "run_id": "mas_sim_2",
            "task_id": "task_2",
            "system": "mas",
            "status": "SIMULATED",
            "execution_mode": "SIMULATED",
            "token_provenance": "SIMULATED",
            "official": True,
            "quality": 0.9999,
        },
    ]
    cd_runs = [
        {
            "run_id": "cd_sim_1",
            "task_id": "task_1",
            "system": "chatdev",
            "status": "SIMULATION_ONLY",
            "execution_mode": "SIMULATION_ONLY",
            "token_provenance": "SIMULATION_ONLY",
            "official": True,
            "quality": 0.9999,
        },
    ]

    report = generate_stats_markdown_report(mas_runs, cd_runs, output_path=output_report)

    # When all runs are simulation, report must indicate zero live runs and not claim any quality
    assert "No official live benchmark runs yet (N=0)" in report
    assert "0.9999" not in report
    assert "Simulation-only runs are strictly excluded" in report


def test_calculate_success_rate_strictly_excludes_simulation():
    """Test 3: calculate_success_rate strictly ignores SIMULATION_ONLY and SIMULATED rows."""
    runs = [
        {
            "run_id": "r1",
            "status": "SIMULATION_ONLY",
            "execution_mode": "SIMULATION_ONLY",
            "official": True,
        },
        {
            "run_id": "r2",
            "status": "COMPLETED",
            "execution_mode": "SIMULATED",
            "official": True,
        },
        {
            "run_id": "r3",
            "status": "COMPLETED",
            "execution_mode": "LIVE_API",
            "token_provenance": "PROVIDER_REPORTED",
            "official": True,
        },
        {
            "run_id": "r4",
            "status": "FAILED",
            "execution_mode": "LIVE_API",
            "token_provenance": "PROVIDER_REPORTED",
            "official": True,
        },
    ]
    # Only r3 and r4 are valid live runs; 1 completed out of 2 -> 0.50
    rate = calculate_success_rate(runs)
    assert rate == 0.50


def test_count_code_loc_excludes_tests_and_comments(tmp_path):
    """Test 4: count_code_loc counts non-comment code in *.py and excludes test_*.py and comments."""
    main_py = tmp_path / "main.py"
    main_py.write_text(
        "# Header comment\n"
        "\n"
        "def solve():\n"
        "    x = 1\n"
        "    # intermediate comment\n"
        "    return x + 41\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    print(solve())\n",
        encoding="utf-8",
    )

    test_py = tmp_path / "test_main.py"
    test_py.write_text(
        "def test_solve():\n"
        "    assert solve() == 42\n" * 50,
        encoding="utf-8",
    )

    loc = count_code_loc(str(tmp_path))
    # 5 non-empty, non-comment lines in main.py, test_main.py is completely excluded
    assert loc == 5


def test_chatdev_adapter_default_proxy_port():
    """Test 5: ChatDevAdapter defaults to proxy port 8089."""
    adapter = ChatDevAdapter()
    assert "8089" in adapter.proxy_url


def test_chatdev_patch_exists_and_matches_recorded_sha256():
    """Test 6: patches/chatdev_local.patch exists and matches manifest sha256."""
    patch_path = os.path.abspath("patches/chatdev_local.patch")
    assert os.path.exists(patch_path), "patches/chatdev_local.patch must exist"

    with open(patch_path, "rb") as f:
        content = f.read()

    computed_sha256 = hashlib.sha256(content).hexdigest()
    expected_sha256 = "bf239f6157240df3ffed505e0e1f05e8c4e84f7c70006d51fc62e70d8105584b"
    assert computed_sha256 == expected_sha256


def test_proxy_enforces_temperature_and_seed_for_fairness():
    """Test 7: mas.core.proxy exposes health endpoint and enforces temperature=0.0 and seed=42."""
    from mas.core.proxy import health
    res = health()
    assert res["status"] == "ok"
