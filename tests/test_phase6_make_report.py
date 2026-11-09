"""Phase 6 Tests: Unified benchmark report generation and LaTeX export."""

import csv
import os
import subprocess
import sys
import pytest


def test_make_report_renders_tables_and_valid_latex(tmp_path):
    """Test 1: Feeds scripts/make_report.py a fixture results.csv with 4 rows (2 MAS, 2 ChatDev) and verifies all tables and valid LaTeX."""
    csv_file = tmp_path / "test_results.csv"
    out_dir = tmp_path / "reports"

    # 4 rows: 2 MAS, 2 ChatDev
    rows = [
        {
            "run_id": "mas_task1_r1",
            "task_id": "srdd_educ_01",
            "system": "mas",
            "provider": "openrouter",
            "model": "cohere/north-mini-code:free",
            "repeat_no": 1,
            "ablation": "A0",
            "official": "true",
            "retry_reason": "",
            "quality": 0.8500,
            "completeness": 1.0,
            "executability": 1.0,
            "consistency": 0.8500,
            "shared_test": 0.9000,
            "tokens": 42000,
            "cost": 0.0,
            "llm_calls": 3,
            "wall_clock_seconds": 45.2,
            "loc": 120,
            "status": "COMPLETED",
            "execution_mode": "LIVE_API",
            "token_provenance": "PROVIDER_REPORTED",
        },
        {
            "run_id": "mas_task2_r1",
            "task_id": "srdd_work_01",
            "system": "mas",
            "provider": "openrouter",
            "model": "cohere/north-mini-code:free",
            "repeat_no": 1,
            "ablation": "A0",
            "official": "true",
            "retry_reason": "",
            "quality": 0.7200,
            "completeness": 0.90,
            "executability": 1.0,
            "consistency": 0.8000,
            "shared_test": 0.8500,
            "tokens": 48000,
            "cost": 0.0,
            "llm_calls": 4,
            "wall_clock_seconds": 52.1,
            "loc": 140,
            "status": "COMPLETED",
            "execution_mode": "LIVE_API",
            "token_provenance": "PROVIDER_REPORTED",
        },
        {
            "run_id": "cd_task1_r1",
            "task_id": "srdd_educ_01",
            "system": "chatdev",
            "provider": "openrouter",
            "model": "cohere/north-mini-code:free",
            "repeat_no": 1,
            "ablation": "A0",
            "official": "true",
            "retry_reason": "",
            "quality": 0.6500,
            "completeness": 0.85,
            "executability": 1.0,
            "consistency": 0.7647,
            "shared_test": 0.7000,
            "tokens": 28000,
            "cost": 0.0,
            "llm_calls": 6,
            "wall_clock_seconds": 65.4,
            "loc": 95,
            "status": "COMPLETED",
            "execution_mode": "LIVE_API",
            "token_provenance": "PROVIDER_REPORTED",
        },
        {
            "run_id": "cd_task2_r1",
            "task_id": "srdd_work_01",
            "system": "chatdev",
            "provider": "openrouter",
            "model": "cohere/north-mini-code:free",
            "repeat_no": 1,
            "ablation": "A0",
            "official": "true",
            "retry_reason": "",
            "quality": 0.5800,
            "completeness": 0.80,
            "executability": 1.0,
            "consistency": 0.7250,
            "shared_test": 0.6500,
            "tokens": 31000,
            "cost": 0.0,
            "llm_calls": 7,
            "wall_clock_seconds": 72.8,
            "loc": 110,
            "status": "COMPLETED",
            "execution_mode": "LIVE_API",
            "token_provenance": "PROVIDER_REPORTED",
        },
    ]

    fieldnames = list(rows[0].keys())
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    script_path = os.path.abspath("scripts/make_report.py")
    res = subprocess.run(
        [sys.executable, script_path, "--results", str(csv_file), "--output-dir", str(out_dir)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert res.returncode == 0, f"make_report.py failed: {res.stderr}"

    stdout = res.stdout
    # Verify Table 1 to Table 6 are all present
    assert "Table 1:" in stdout
    assert "Table 2:" in stdout
    assert "Table 3:" in stdout
    assert "Table 4:" in stdout
    assert "Table 5:" in stdout
    assert "Table 6:" in stdout

    # Verify generated files
    md_report = out_dir / "benchmark_report.md"
    tex_report = out_dir / "tables.tex"
    csv_summary = out_dir / "summary.csv"

    assert md_report.exists()
    assert tex_report.exists()
    assert csv_summary.exists()

    # Validate LaTeX syntax: proper table environments, no unescaped underscores in text
    tex_content = tex_report.read_text(encoding="utf-8")
    assert "\\begin{table}" in tex_content
    assert "\\end{table}" in tex_content
    assert "\\begin{tabular}" in tex_content
    assert "\\end{tabular}" in tex_content

    # Check for unescaped underscores outside math mode
    # In valid latex output, variable names like 'task_1' or 'gpt-3.5_turbo' should be escaped as 'task\_1'
    for line in tex_content.splitlines():
        clean_line = line.strip()
        if clean_line.startswith("%"):
            continue
        # Replace escaped underscores
        remaining = clean_line.replace("\\_", "")
        # If there's an underscore left, it should only be in math mode ($...$)
        if "_" in remaining:
            # Check if within math delimiters
            parts = remaining.split("$")
            # Even indexed parts (0, 2, ...) are outside math mode
            for i in range(0, len(parts), 2):
                assert "_" not in parts[i], f"Unescaped underscore found outside math mode in LaTeX: {line}"


def test_make_report_empty_results_prints_not_run(tmp_path):
    """Test 2: When no official runs exist, make_report outputs NOT RUN in table cells."""
    empty_csv = tmp_path / "empty_results.csv"
    out_dir = tmp_path / "empty_reports"

    # Write CSV with header only
    with open(empty_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["run_id", "task_id", "system", "quality", "official"])

    script_path = os.path.abspath("scripts/make_report.py")
    res = subprocess.run(
        [sys.executable, script_path, "--results", str(empty_csv), "--output-dir", str(out_dir)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert res.returncode == 0
    assert "NOT RUN" in res.stdout
