"""Independent Neutral Test Suite for Development Pilot Task dev_csv_sales_01.

Task: CSV Sales Summary CLI
Requirement: Read CSV with product, quantity, unit_price; compute per-product & total revenue; handle empty/malformed files; provide CLI entry point.
Acceptance Criteria:
  1. Read a CSV containing product name, quantity, and unit price columns.
  2. Validate required columns and numeric inputs (quantity >= 0, unit_price >= 0.0).
  3. Compute per-product revenue (quantity * unit_price) and total revenue correctly.
  4. Handle an empty CSV file cleanly without unhandled exceptions.
  5. Handle malformed rows without silently inventing data.
  6. Provide a usable command-line entry point executable via main.py.
  7. Include automated behavioral tests for normal and failure cases.
  8. Use the Python standard library.

Runs independently outside the generation loop to measure Level 2 behavioral correctness.
Preserves the locked confirmatory research tasks and operates strictly on development pilot tasks.
"""

import os
import sys
import csv
import tempfile
import subprocess
from typing import Any, Dict, List


def run_neutral_test(workspace_path: str) -> Dict[str, Any]:
    """Evaluates generated CSV Sales Summary CLI against behavioral acceptance criteria."""
    abs_ws = os.path.abspath(workspace_path)
    if abs_ws not in sys.path:
        sys.path.insert(0, abs_ws)

    results = {
        "task_id": "dev_csv_sales_01",
        "task_name": "CSV Sales Summary CLI",
        "test_suite_version": "2.0.0-DEV-PILOT-EXPANDED",
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
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=abs_ws)

    with tempfile.TemporaryDirectory() as tmp_dir:
        # 2. Correct per-product and total revenue using several rows
        multi_csv = os.path.join(tmp_dir, "multi_sales.csv")
        with open(multi_csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["product_name", "quantity", "unit_price"])
            writer.writerow(["Widget_Alpha", "10", "5.50"])   # 55.00
            writer.writerow(["Widget_Beta", "4", "12.25"])    # 49.00
            writer.writerow(["Widget_Gamma", "2", "30.00"])   # 60.00
            writer.writerow(["Widget_Alpha", "5", "5.50"])    # 27.50 (cumulative Widget_Alpha = 82.50)
        # Total = 55.00 + 49.00 + 60.00 + 27.50 = 191.50
        try:
            proc = run_cli([multi_csv])
            if proc.returncode == 0:
                out = proc.stdout.lower()
                has_total = "191.5" in out or "191.50" in out
                has_gamma = "60.0" in out or "60.00" in out
                if has_total and has_gamma:
                    results["assertions"]["normal_calculation_multiple_rows"] = True
                    log("PASS: Multi-row calculations verified with exact per-product and total revenue.")
                else:
                    results["assertions"]["normal_calculation_multiple_rows"] = False
                    log(f"FAIL: Revenue mismatch in multi-row output: {proc.stdout}")
            else:
                results["assertions"]["normal_calculation_multiple_rows"] = False
                log(f"FAIL: Multi-row execution exited with code {proc.returncode}: {proc.stderr}")
        except Exception as e:
            results["assertions"]["normal_calculation_multiple_rows"] = False
            log(f"FAIL: Multi-row test exception: {e}")

        # 3. Products with spaces
        spaces_csv = os.path.join(tmp_dir, "spaces_sales.csv")
        with open(spaces_csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["product_name", "quantity", "unit_price"])
            writer.writerow(["Ergonomic Office Chair Deluxe", "2", "150.00"])
            writer.writerow(["Wireless Mechanical Keyboard Pro", "3", "80.00"])
        # Total = 300.00 + 240.00 = 540.00
        try:
            proc = run_cli([spaces_csv])
            if proc.returncode == 0:
                out = proc.stdout.lower()
                has_chair = "ergonomic office chair deluxe" in out
                has_kb = "wireless mechanical keyboard pro" in out
                has_total = "540.0" in out or "540.00" in out
                if has_chair and has_kb and has_total:
                    results["assertions"]["products_with_spaces"] = True
                    log("PASS: Products with spaces preserved and calculated correctly.")
                else:
                    results["assertions"]["products_with_spaces"] = False
                    log(f"FAIL: Products with spaces output missing expected labels: {proc.stdout}")
            else:
                results["assertions"]["products_with_spaces"] = False
                log(f"FAIL: Products with spaces run exited with code {proc.returncode}")
        except Exception as e:
            results["assertions"]["products_with_spaces"] = False
            log(f"FAIL: Products with spaces exception: {e}")

        # 4. Alternate supported header names (variations: 'product', 'qty', 'price' / 'item', 'count', 'rate')
        alt_headers_csv = os.path.join(tmp_dir, "alt_headers.csv")
        with open(alt_headers_csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["Product", "Qty", "Price"])
            writer.writerow(["Gadget_X", "5", "20.00"])
        try:
            proc = run_cli([alt_headers_csv])
            if proc.returncode == 0 and ("100.0" in proc.stdout or "100.00" in proc.stdout):
                results["assertions"]["alternate_supported_headers"] = True
                log("PASS: Alternate header variants ('Product', 'Qty', 'Price') recognized.")
            else:
                results["assertions"]["alternate_supported_headers"] = False
                log(f"FAIL: Alternate headers failed: {proc.stdout} | stderr: {proc.stderr}")
        except Exception as e:
            results["assertions"]["alternate_supported_headers"] = False
            log(f"FAIL: Alternate headers exception: {e}")

        # 5. Empty file (0 bytes)
        empty_csv = os.path.join(tmp_dir, "zero_bytes.csv")
        with open(empty_csv, "w", encoding="utf-8") as fh:
            pass
        try:
            proc = run_cli([empty_csv])
            if proc.returncode == 0 and "traceback" not in proc.stderr.lower():
                results["assertions"]["empty_file_handling"] = True
                log("PASS: 0-byte empty file handled cleanly with exit code 0.")
            else:
                results["assertions"]["empty_file_handling"] = False
                log(f"FAIL: Empty file returned code {proc.returncode}: {proc.stderr}")
        except Exception as e:
            results["assertions"]["empty_file_handling"] = False
            log(f"FAIL: Empty file exception: {e}")

        # 6. Header-only file (valid columns but no data rows)
        header_only_csv = os.path.join(tmp_dir, "header_only.csv")
        with open(header_only_csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["product_name", "quantity", "unit_price"])
        try:
            proc = run_cli([header_only_csv])
            if proc.returncode == 0 and "traceback" not in proc.stderr.lower():
                results["assertions"]["header_only_file"] = True
                log("PASS: Header-only file handled cleanly with exit code 0.")
            else:
                results["assertions"]["header_only_file"] = False
                log(f"FAIL: Header-only file returned code {proc.returncode}: {proc.stderr}")
        except Exception as e:
            results["assertions"]["header_only_file"] = False
            log(f"FAIL: Header-only file exception: {e}")

        # 7. Missing required columns (e.g. quantity column missing)
        missing_col_csv = os.path.join(tmp_dir, "missing_col.csv")
        with open(missing_col_csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["product_name", "unit_price"])
            writer.writerow(["Widget_Z", "15.00"])
        try:
            proc = run_cli([missing_col_csv])
            if proc.returncode == 1 and ("missing" in proc.stderr.lower() or "error" in proc.stderr.lower()):
                results["assertions"]["missing_required_columns"] = True
                log("PASS: Missing required column rejected with exit code 1 and error on stderr.")
            else:
                results["assertions"]["missing_required_columns"] = False
                log(f"FAIL: Missing column did not produce code 1/stderr: code={proc.returncode}, stderr={proc.stderr}")
        except Exception as e:
            results["assertions"]["missing_required_columns"] = False
            log(f"FAIL: Missing column exception: {e}")

        # 8. Nonnumeric quantities and prices
        nonnumeric_csv = os.path.join(tmp_dir, "nonnumeric.csv")
        with open(nonnumeric_csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["product_name", "quantity", "unit_price"])
            writer.writerow(["ValidOne", "2", "50.00"])      # 100.00
            writer.writerow(["CorruptQty", "NaN", "10.00"])
            writer.writerow(["CorruptPrice", "5", "free"])
            writer.writerow(["ValidTwo", "1", "25.00"])      # 25.00
        # Total should be 125.00
        try:
            proc = run_cli([nonnumeric_csv])
            if proc.returncode == 0 and ("125.0" in proc.stdout or "125.00" in proc.stdout) and len(proc.stderr.strip()) > 0:
                results["assertions"]["nonnumeric_values_handling"] = True
                log("PASS: Nonnumeric quantities/prices warned to stderr and valid rows computed.")
            else:
                results["assertions"]["nonnumeric_values_handling"] = False
                log(f"FAIL: Nonnumeric values handling failed: out={proc.stdout}, err={proc.stderr}")
        except Exception as e:
            results["assertions"]["nonnumeric_values_handling"] = False
            log(f"FAIL: Nonnumeric test exception: {e}")

        # 9. Negative quantities and prices
        negative_csv = os.path.join(tmp_dir, "negative.csv")
        with open(negative_csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["product_name", "quantity", "unit_price"])
            writer.writerow(["ValidPositive", "3", "10.00"])   # 30.00
            writer.writerow(["NegativeQty", "-5", "10.00"])
            writer.writerow(["NegativePrice", "2", "-25.00"])
        # Total should remain 30.00
        try:
            proc = run_cli([negative_csv])
            if proc.returncode == 0 and ("30.0" in proc.stdout or "30.00" in proc.stdout) and "invalid negative" in proc.stderr.lower():
                results["assertions"]["negative_values_handling"] = True
                log("PASS: Negative quantities/prices warned to stderr and rejected from total revenue.")
            else:
                results["assertions"]["negative_values_handling"] = False
                log(f"FAIL: Negative values handling failed: out={proc.stdout}, err={proc.stderr}")
        except Exception as e:
            results["assertions"]["negative_values_handling"] = False
            log(f"FAIL: Negative test exception: {e}")

        # 10. Zero quantities and prices
        zero_csv = os.path.join(tmp_dir, "zeroes.csv")
        with open(zero_csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["product_name", "quantity", "unit_price"])
            writer.writerow(["ZeroQtyWidget", "0", "15.00"])   # 0.00
            writer.writerow(["FreePromoWidget", "10", "0.00"])  # 0.00
            writer.writerow(["StandardWidget", "2", "10.00"])  # 20.00
        # Total = 20.00
        try:
            proc = run_cli([zero_csv])
            if proc.returncode == 0 and ("20.0" in proc.stdout or "20.00" in proc.stdout):
                results["assertions"]["zero_quantities_and_prices"] = True
                log("PASS: Zero quantities and zero unit prices computed correctly as 0.00 revenue.")
            else:
                results["assertions"]["zero_quantities_and_prices"] = False
                log(f"FAIL: Zero quantities/prices failed: out={proc.stdout}")
        except Exception as e:
            results["assertions"]["zero_quantities_and_prices"] = False
            log(f"FAIL: Zero test exception: {e}")

        # 11. Malformed rows and warning behavior (insufficient columns / irregular length)
        malformed_csv = os.path.join(tmp_dir, "malformed.csv")
        with open(malformed_csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["product_name", "quantity", "unit_price"])
            writer.writerow(["GoodItem", "2", "15.00"])
            writer.writerow(["BrokenRowSingleColumn"])
            writer.writerow(["AnotherGoodItem", "1", "10.00"])
        # Total = 30.00 + 10.00 = 40.00
        try:
            proc = run_cli([malformed_csv])
            if proc.returncode == 0 and ("40.0" in proc.stdout or "40.00" in proc.stdout) and "insufficient" in proc.stderr.lower():
                results["assertions"]["malformed_rows_warning"] = True
                log("PASS: Malformed row with insufficient columns warned to stderr and skipped.")
            else:
                results["assertions"]["malformed_rows_warning"] = False
                log(f"FAIL: Malformed rows warning failed: out={proc.stdout}, err={proc.stderr}")
        except Exception as e:
            results["assertions"]["malformed_rows_warning"] = False
            log(f"FAIL: Malformed rows test exception: {e}")

        # 12. Missing input file (FileNotFound)
        nonexistent_csv = os.path.join(tmp_dir, "does_not_exist.csv")
        try:
            proc = run_cli([nonexistent_csv])
            if proc.returncode == 1 and ("not found" in proc.stderr.lower() or "error" in proc.stderr.lower()) and "traceback" not in proc.stderr.lower():
                results["assertions"]["missing_input_file"] = True
                log("PASS: Nonexistent input file cleanly exited with code 1 and error on stderr.")
            else:
                results["assertions"]["missing_input_file"] = False
                log(f"FAIL: Missing input file returned code {proc.returncode}: {proc.stderr}")
        except Exception as e:
            results["assertions"]["missing_input_file"] = False
            log(f"FAIL: Missing input file exception: {e}")

        # 13. Empty fields and whitespace handling
        empty_fields_csv = os.path.join(tmp_dir, "empty_fields.csv")
        with open(empty_fields_csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["product_name", "quantity", "unit_price"])
            writer.writerow(["ItemOne", "1", "50.00"])
            writer.writerow(["", "2", "20.00"])       # Missing product name
            writer.writerow(["ItemThree", "", "10.00"]) # Missing quantity
            writer.writerow(["ItemFour", "4", ""])     # Missing price
        # Total = 50.00
        try:
            proc = run_cli([empty_fields_csv])
            if proc.returncode == 0 and ("50.0" in proc.stdout or "50.00" in proc.stdout):
                results["assertions"]["empty_fields_handling"] = True
                log("PASS: Rows with blank fields skipped cleanly without traceback.")
            else:
                results["assertions"]["empty_fields_handling"] = False
                log(f"FAIL: Empty fields handling failed: out={proc.stdout}, err={proc.stderr}")
        except Exception as e:
            results["assertions"]["empty_fields_handling"] = False
            log(f"FAIL: Empty fields exception: {e}")

        # 14. CLI --help option
        try:
            proc = run_cli(["--help"])
            if proc.returncode == 0 and "usage:" in proc.stdout.lower() and "file_path" in proc.stdout.lower():
                results["assertions"]["cli_help_option"] = True
                log("PASS: CLI --help option verified with exit code 0 and usage grammar.")
            else:
                results["assertions"]["cli_help_option"] = False
                log(f"FAIL: CLI --help failed: code={proc.returncode}, out={proc.stdout}")
        except Exception as e:
            results["assertions"]["cli_help_option"] = False
            log(f"FAIL: CLI --help exception: {e}")

        # 15. CLI missing arguments (usage error exit code 2)
        try:
            proc = run_cli([])
            if proc.returncode == 2 and ("usage:" in proc.stderr.lower() or "required" in proc.stderr.lower()):
                results["assertions"]["cli_missing_args_usage_error"] = True
                log("PASS: Invocation with missing arguments correctly produced code 2 usage error.")
            else:
                results["assertions"]["cli_missing_args_usage_error"] = False
                log(f"FAIL: Missing arguments produced code={proc.returncode}, stderr={proc.stderr}")
        except Exception as e:
            results["assertions"]["cli_missing_args_usage_error"] = False
            log(f"FAIL: Missing arguments exception: {e}")

        # 16. Developer automated test suite presence and passing
        dev_test_file = os.path.join(abs_ws, "test_main.py")
        if os.path.exists(dev_test_file):
            try:
                proc = subprocess.run([sys.executable, "-m", "unittest", "test_main.py"], capture_output=True, text=True, cwd=abs_ws, timeout=15)
                if proc.returncode == 0:
                    results["assertions"]["developer_automated_tests"] = True
                    log("PASS: Developer-generated automated tests (test_main.py) present and passing.")
                else:
                    results["assertions"]["developer_automated_tests"] = False
                    log(f"FAIL: Developer test suite failed: {proc.stderr}")
            except Exception as e:
                results["assertions"]["developer_automated_tests"] = False
                log(f"FAIL: Running developer test suite threw exception: {e}")
        else:
            results["assertions"]["developer_automated_tests"] = False
            log("FAIL: Developer test file test_main.py not found in workspace.")

    # Compute overall outcome
    total = len(results["assertions"])
    passed = sum(1 for v in results["assertions"].values() if v)
    results["all_passed"] = (passed == total and total > 0)
    results["pass_rate"] = round(passed / total, 4) if total > 0 else 0.0
    results["total_assertions"] = total
    results["passed_assertions"] = passed
    return results


# Pytest test integration for development pilot evaluation
def test_expanded_dev_csv_sales_suite():
    """Pytest wrapper executing all 16 Level 2 behavioral assertions on the generated artifact."""
    workspace = os.path.abspath("workspace/mas_dev_csv_sales_1792211689")
    res = run_neutral_test(workspace)
    assert res["all_passed"], f"Behavioral test suite failures: {[k for k, v in res['assertions'].items() if not v]}"
    assert res["total_assertions"] == 16
    assert res["passed_assertions"] == 16
    assert res["pass_rate"] == 1.0
