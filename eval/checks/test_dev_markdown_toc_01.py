"""Independent Neutral Test Suite for Development Pilot Task dev_markdown_toc_01.

Task: Markdown Table of Contents Generator CLI
Requirement: Parse markdown file, extract headings, generate bulleted TOC with anchor links, ignore code blocks, handle malformed/empty files.
Acceptance Criteria:
  1. Extract level 1 to level 3 headings (#, ##, ###).
  2. Generate formatted markdown list with properly indented anchor links.
  3. Properly ignore headings inside fenced code blocks.
  4. Handle empty input files gracefully (code 0).
  5. Handle non-existent input files cleanly (code 1, error on stderr).
  6. CLI --help option exits code 0.
  7. Missing arguments reports usage error with exit code 2.
  8. Developer automated tests pass.
"""

import os
import re
import sys
import tempfile
import subprocess
from typing import Any, Dict, List


def run_neutral_test(workspace_path: str) -> Dict[str, Any]:
    """Evaluates generated Markdown TOC CLI against independent behavioral criteria."""
    abs_ws = os.path.abspath(workspace_path)
    if abs_ws not in sys.path:
        sys.path.insert(0, abs_ws)

    results = {
        "task_id": "dev_markdown_toc_01",
        "task_name": "Markdown Table of Contents Generator CLI",
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
                log(f"PASS: Invocation with missing arguments produced expected usage error (code={proc.returncode}).")
            else:
                results["assertions"]["cli_missing_args_usage_error"] = False
                log(f"FAIL: Missing arguments produced code={proc.returncode}, stderr={proc.stderr}")
        except Exception as e:
            results["assertions"]["cli_missing_args_usage_error"] = False
            log(f"FAIL: Missing arguments exception: {e}")

        # 4. Missing input file handling
        try:
            non_existent = os.path.join(tmpdir, "missing_file_xyz123.md")
            proc = run_cli([non_existent])
            if proc.returncode == 1 and len(proc.stderr.strip()) > 0 and "traceback" not in proc.stderr.lower():
                results["assertions"]["missing_file_error"] = True
                log("PASS: Non-existent file handled cleanly with code 1 and stderr message.")
            elif proc.returncode != 0 and "traceback" not in proc.stderr.lower():
                results["assertions"]["missing_file_error"] = True
                log(f"PASS: Non-existent file returned non-zero code {proc.returncode} without crash.")
            else:
                results["assertions"]["missing_file_error"] = False
                log(f"FAIL: Non-existent file code={proc.returncode}, stderr={proc.stderr}")
        except Exception as e:
            results["assertions"]["missing_file_error"] = False
            log(f"FAIL: Non-existent file exception: {e}")

        # 5. Empty input file handling
        try:
            empty_file = os.path.join(tmpdir, "empty.md")
            with open(empty_file, "w", encoding="utf-8") as f:
                pass
            proc = run_cli([empty_file])
            if proc.returncode == 0 and "traceback" not in proc.stderr.lower():
                results["assertions"]["empty_file_clean_exit"] = True
                log("PASS: Empty file produced code 0 without traceback.")
            else:
                results["assertions"]["empty_file_clean_exit"] = False
                log(f"FAIL: Empty file returned code={proc.returncode}, stderr={proc.stderr}")
        except Exception as e:
            results["assertions"]["empty_file_clean_exit"] = False
            log(f"FAIL: Empty file exception: {e}")

        # 6. Single heading parsing
        try:
            single_file = os.path.join(tmpdir, "single.md")
            with open(single_file, "w", encoding="utf-8") as f:
                f.write("# Introduction\n\nSome introductory content here.\n")
            proc = run_cli([single_file])
            output = proc.stdout.lower()
            if proc.returncode == 0 and "introduction" in output and "#introduction" in output:
                results["assertions"]["single_heading_toc"] = True
                log("PASS: Single heading correctly parsed with anchor link.")
            else:
                results["assertions"]["single_heading_toc"] = False
                log(f"FAIL: Single heading output: {proc.stdout}")
        except Exception as e:
            results["assertions"]["single_heading_toc"] = False
            log(f"FAIL: Single heading exception: {e}")

        # 7. Nested headings indentation
        try:
            nested_file = os.path.join(tmpdir, "nested.md")
            with open(nested_file, "w", encoding="utf-8") as f:
                f.write("# Main Chapter\n\n## Sub Section\n\n### Deep Topic\n")
            proc = run_cli([nested_file])
            lines = [l for l in proc.stdout.splitlines() if "-" in l or "*" in l]
            has_h1 = any("main chapter" in l.lower() for l in lines)
            has_h2 = any("sub section" in l.lower() for l in lines)
            has_h3 = any("deep topic" in l.lower() for l in lines)
            has_indent = any(l.startswith("  ") or l.startswith("    ") or l.startswith("\t") for l in lines)
            if proc.returncode == 0 and has_h1 and has_h2 and has_h3 and has_indent:
                results["assertions"]["nested_headings_indentation"] = True
                log("PASS: Nested headings generated with proper indentation.")
            else:
                results["assertions"]["nested_headings_indentation"] = False
                log(f"FAIL: Nested headings output: {proc.stdout}")
        except Exception as e:
            results["assertions"]["nested_headings_indentation"] = False
            log(f"FAIL: Nested headings exception: {e}")

        # 8. Ignore headings in code blocks
        try:
            code_file = os.path.join(tmpdir, "code.md")
            with open(code_file, "w", encoding="utf-8") as f:
                f.write("# Real Title\n\n```python\n# This is a python comment, not a heading\nprint('hello')\n```\n\n## Real Subtitle\n")
            proc = run_cli([code_file])
            out = proc.stdout.lower()
            if proc.returncode == 0 and "real title" in out and "real subtitle" in out and "comment" not in out:
                results["assertions"]["fenced_code_block_ignored"] = True
                log("PASS: Comments inside code blocks correctly ignored in TOC.")
            else:
                results["assertions"]["fenced_code_block_ignored"] = False
                log(f"FAIL: Code block heading filtering failed: {proc.stdout}")
        except Exception as e:
            results["assertions"]["fenced_code_block_ignored"] = False
            log(f"FAIL: Code block heading exception: {e}")

        # 9. Slug handling for punctuation / spaces
        try:
            punct_file = os.path.join(tmpdir, "punct.md")
            with open(punct_file, "w", encoding="utf-8") as f:
                f.write("# Hello, World: 2026 Edition!\n")
            proc = run_cli([punct_file])
            out = proc.stdout.lower()
            # Expect anchor without comma or exclamation mark: e.g. #hello-world-2026-edition
            has_clean_anchor = re.search(r"\(#hello.*world.*2026.*edition\)", out) is not None
            if proc.returncode == 0 and has_clean_anchor and "!" not in out.split("(")[-1]:
                results["assertions"]["slug_punctuation_handling"] = True
                log("PASS: Punctuation stripped in anchor slug.")
            else:
                results["assertions"]["slug_punctuation_handling"] = False
                log(f"FAIL: Anchor slug handling output: {proc.stdout}")
        except Exception as e:
            results["assertions"]["slug_punctuation_handling"] = False
            log(f"FAIL: Anchor slug exception: {e}")

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

