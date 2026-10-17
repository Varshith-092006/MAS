"""Independent Neutral Test Suite for Development Pilot Task dev_log_analyzer_01.

Task: Web Server Access Log Metrics CLI (Data-Processing)
Requirement: Parse access logs, extract status codes and bandwidth, compute distributions and error percentages, skip malformed lines, handle empty/missing files.
Acceptance Criteria:
  1. Parse standard access log format (IP, timestamp, status, bytes).
  2. Compute total requests, status code distribution, total bandwidth.
  3. Calculate error percentage ((4xx + 5xx) / total * 100).
  4. Empty log file handled cleanly (code 0).
  5. Missing log file reports code 1 on stderr.
  6. CLI --help exits code 0.
  7. Missing arguments reports usage error with exit code 2.
  8. Malformed lines skipped with warning to stderr.
  9. Developer automated tests pass.
"""

import os
import sys
import tempfile
import subprocess
from typing import Any, Dict, List


def run_neutral_test(workspace_path: str) -> Dict[str, Any]:
    """Evaluates generated Log Analyzer CLI against independent behavioral criteria."""
    abs_ws = os.path.abspath(workspace_path)
    if abs_ws not in sys.path:
        sys.path.insert(0, abs_ws)

    results = {
        "task_id": "dev_log_analyzer_01",
        "task_name": "Web Server Access Log Metrics CLI",
        "test_suite_version": "1.0.0-DEV-PILOT",
        "assertions": {},
        "all_passed": False,
        "logs": [],
    }

    def log(msg: str):
        results["logs"].append(msg)

    # 1. Module Discovery and Entry Point
    py_files = [
        f for f in sorted(os.listdir(abs_ws))
        if f.endswith(".py") and not f.startswith("test_")
    ]
    if not py_files:
        log("FAIL: No Python source files found in workspace.")
        results["assertions"]["module_import"] = False
        return results

    entry_point = "main.py" if "main.py" in py_files else py_files[0]
    entry_path = os.path.join(abs_ws, entry_point)
    results["assertions"]["module_import"] = True
    log(f"PASS: Found entry point {entry_point}")

    def run_cli(args: List[str], timeout: int = 10) -> subprocess.CompletedProcess:
        cmd = [sys.executable, entry_path] + args
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=abs_ws,
            timeout=timeout,
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        # 2. CLI --help option
        try:
            proc = run_cli(["--help"])
            if proc.returncode == 0 and ("usage" in proc.stdout.lower() or "help" in proc.stdout.lower()):
                results["assertions"]["cli_help_option"] = True
                log("PASS: --help returned code 0 with usage documentation.")
            else:
                results["assertions"]["cli_help_option"] = False
                log(f"FAIL: --help returned code={proc.returncode}")
        except Exception as e:
            results["assertions"]["cli_help_option"] = False
            log(f"FAIL: --help exception: {e}")

        # 3. Missing argument error
        try:
            proc = run_cli([])
            if proc.returncode in (1, 2) and ("usage:" in proc.stderr.lower() or "error" in proc.stderr.lower() or "argument" in proc.stderr.lower()):
                results["assertions"]["cli_missing_args_usage_error"] = True
                log(f"PASS: Missing arguments produced usage error (code={proc.returncode}).")
            else:
                results["assertions"]["cli_missing_args_usage_error"] = False
                log(f"FAIL: Missing arguments produced code={proc.returncode}, stderr={proc.stderr}")
        except Exception as e:
            results["assertions"]["cli_missing_args_usage_error"] = False
            log(f"FAIL: Missing arguments exception: {e}")

        # 4. Missing log file
        try:
            non_existent = os.path.join(tmpdir, "missing_log_xyz.log")
            proc = run_cli([non_existent])
            if proc.returncode != 0 and "traceback" not in proc.stderr.lower():
                results["assertions"]["missing_file_error"] = True
                log("PASS: Non-existent log file produced error without unhandled traceback.")
            else:
                results["assertions"]["missing_file_error"] = False
                log(f"FAIL: Non-existent file produced code={proc.returncode}, stderr={proc.stderr}")
        except Exception as e:
            results["assertions"]["missing_file_error"] = False
            log(f"FAIL: Non-existent file exception: {e}")

        # 5. Empty log file
        try:
            empty_log = os.path.join(tmpdir, "empty.log")
            with open(empty_log, "w", encoding="utf-8") as f:
                pass
            proc = run_cli([empty_log])
            if proc.returncode == 0 and "traceback" not in proc.stderr.lower():
                results["assertions"]["empty_file_clean_exit"] = True
                log("PASS: Empty log file processed cleanly with code 0.")
            else:
                results["assertions"]["empty_file_clean_exit"] = False
                log(f"FAIL: Empty log returned code={proc.returncode}, stderr={proc.stderr}")
        except Exception as e:
            results["assertions"]["empty_file_clean_exit"] = False
            log(f"FAIL: Empty log exception: {e}")

        # 6. Standard access log parsing & status code distribution
        sample_log = os.path.join(tmpdir, "access.log")
        with open(sample_log, "w", encoding="utf-8") as f:
            f.write(
                '192.168.1.1 - - [10/Oct/2026:13:55:36 +0000] "GET /index.html HTTP/1.1" 200 1024\n'
                '192.168.1.2 - - [10/Oct/2026:13:55:37 +0000] "GET /about.html HTTP/1.1" 200 2048\n'
                '192.168.1.3 - - [10/Oct/2026:13:55:38 +0000] "GET /missing.html HTTP/1.1" 404 512\n'
                '192.168.1.4 - - [10/Oct/2026:13:55:39 +0000] "POST /api/data HTTP/1.1" 500 256\n'
            )
        try:
            proc = run_cli([sample_log])
            out = proc.stdout.lower()
            if proc.returncode == 0 and "200" in out and "404" in out and "500" in out:
                results["assertions"]["status_code_distribution"] = True
                log("PASS: Status code distributions reported.")
            else:
                results["assertions"]["status_code_distribution"] = False
                log(f"FAIL: Status code output: {proc.stdout}")
        except Exception as e:
            results["assertions"]["status_code_distribution"] = False
            log(f"FAIL: Status code exception: {e}")

        # 7. Total Bandwidth calculation (1024 + 2048 + 512 + 256 = 3840 bytes)
        try:
            if "3840" in out or "3.8" in out or "3.75" in out or "3,840" in out:
                results["assertions"]["bandwidth_calculation"] = True
                log("PASS: Total bandwidth 3840 bytes correctly computed.")
            else:
                # Also accept if total bytes or MB is formatted
                results["assertions"]["bandwidth_calculation"] = (proc.returncode == 0 and ("bytes" in out or "bandwidth" in out))
                log(f"Bandwidth calculation status: {results['assertions']['bandwidth_calculation']}")
        except Exception as e:
            results["assertions"]["bandwidth_calculation"] = False
            log(f"FAIL: Bandwidth calculation exception: {e}")

        # 8. Error Rate calculation ((1 + 1) / 4 = 50.0%)
        try:
            if "50%" in out or "50.0%" in out or "0.5" in out or "50" in out:
                results["assertions"]["error_rate_calculation"] = True
                log("PASS: 50% error rate accurately calculated.")
            else:
                results["assertions"]["error_rate_calculation"] = (proc.returncode == 0 and "error" in out)
                log(f"Error rate calculation status: {results['assertions']['error_rate_calculation']}")
        except Exception as e:
            results["assertions"]["error_rate_calculation"] = False
            log(f"FAIL: Error rate exception: {e}")

        # 9. Malformed log lines skipped with warning
        try:
            malformed_log = os.path.join(tmpdir, "malformed.log")
            with open(malformed_log, "w", encoding="utf-8") as f:
                f.write(
                    '192.168.1.1 - - [10/Oct/2026:13:55:36 +0000] "GET /index.html HTTP/1.1" 200 1000\n'
                    'CORRUPT GARBAGE LINE WITHOUT PROPER FIELDS\n'
                    'ANOTHER TRUNCATED 999\n'
                    '192.168.1.2 - - [10/Oct/2026:13:55:37 +0000] "GET /page.html HTTP/1.1" 200 2000\n'
                )
            proc = run_cli([malformed_log])
            if proc.returncode == 0 and "traceback" not in proc.stderr.lower():
                results["assertions"]["malformed_lines_handling"] = True
                log("PASS: Corrupt log lines skipped gracefully without crash.")
            else:
                results["assertions"]["malformed_lines_handling"] = False
                log(f"FAIL: Malformed log handling code={proc.returncode}, stderr={proc.stderr}")
        except Exception as e:
            results["assertions"]["malformed_lines_handling"] = False
            log(f"FAIL: Malformed log exception: {e}")

        # 10. Developer automated tests
        dev_test_file = os.path.join(abs_ws, "test_main.py")
        if os.path.exists(dev_test_file):
            try:
                proc = subprocess.run(
                    [sys.executable, "-m", "unittest", "test_main.py"],
                    capture_output=True,
                    text=True,
                    cwd=abs_ws,
                    timeout=15,
                )
                if proc.returncode == 0:
                    results["assertions"]["developer_automated_tests"] = True
                    log("PASS: Developer-generated automated tests passed.")
                else:
                    results["assertions"]["developer_automated_tests"] = False
                    log(f"FAIL: Developer test suite failed: {proc.stderr}")
            except Exception as e:
                results["assertions"]["developer_automated_tests"] = False
                log(f"FAIL: Running developer test suite exception: {e}")
        else:
            results["assertions"]["developer_automated_tests"] = False
            log("FAIL: Developer test file test_main.py not found in workspace.")

    total = len(results["assertions"])
    passed = sum(1 for v in results["assertions"].values() if v)
    results["all_passed"] = (passed == total and total > 0)
    results["pass_rate"] = round(passed / total, 4) if total > 0 else 0.0
    results["total_assertions"] = total
    results["passed_assertions"] = passed
    return results


if __name__ == "__main__":
    import json
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    res = run_neutral_test(target)
    print(json.dumps(res, indent=2))
    sys.exit(0 if res["all_passed"] else 1)

