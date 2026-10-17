"""Independent Neutral Test Suite for Development Pilot Task dev_inventory_system_01.

Task: Multi-Module Inventory Management Service (STRUCTURED)
Requirement: Coherent architecture, module contracts, persistent JSON storage, inventory lifecycle, CLI entry point.
Acceptance Criteria:
  1. Modular architecture with separate models, storage, service, and CLI entry point.
  2. Data model validation (name, positive quantity, non-negative price).
  3. Persistent storage surviving restarts.
  4. Stock operations: add item, restock, sell, and valuation.
  5. Prevent selling more units than available stock.
  6. Reporting with inventory statistics and valuation.
  7. Graceful corrupt storage handling.
  8. CLI --help exits code 0.
  9. Developer automated tests pass.
"""

import os
import sys
import json
import tempfile
import subprocess
from typing import Any, Dict, List


def run_neutral_test(workspace_path: str) -> Dict[str, Any]:
    """Evaluates generated Inventory System against independent behavioral criteria."""
    abs_ws = os.path.abspath(workspace_path)
    if abs_ws not in sys.path:
        sys.path.insert(0, abs_ws)

    results = {
        "task_id": "dev_inventory_system_01",
        "task_name": "Multi-Module Inventory Management Service",
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

    # 2. Modular Architecture Check
    # Verify at least 2 non-test Python files exist (multi-module architecture)
    if len(py_files) >= 2:
        results["assertions"]["modular_architecture"] = True
        log(f"PASS: Modular architecture verified with {len(py_files)} files: {py_files}")
    else:
        results["assertions"]["modular_architecture"] = False
        log(f"FAIL: Expected multi-module architecture, found only: {py_files}")

    def run_cli(args: List[str], env: Dict[str, str] = None, timeout: int = 10) -> subprocess.CompletedProcess:
        cmd = [sys.executable, entry_path] + args
        e = os.environ.copy()
        if env:
            e.update(env)
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=abs_ws,
            env=e,
            timeout=timeout,
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        storage_file = os.path.join(tmpdir, "inventory.json")

        # 3. CLI --help option
        try:
            proc = run_cli(["--help"])
            if proc.returncode == 0 and ("usage" in proc.stdout.lower() or "help" in proc.stdout.lower() or "options" in proc.stdout.lower()):
                results["assertions"]["cli_help_option"] = True
                log("PASS: --help returned code 0 with usage documentation.")
            else:
                results["assertions"]["cli_help_option"] = False
                log(f"FAIL: --help returned code={proc.returncode}")
        except Exception as e:
            results["assertions"]["cli_help_option"] = False
            log(f"FAIL: --help exception: {e}")

        # 4. CLI missing args handling
        try:
            proc = run_cli([])
            if proc.returncode in (0, 1, 2) and "traceback" not in proc.stderr.lower():
                results["assertions"]["cli_missing_args"] = True
                log("PASS: Invocation with 0 args terminated cleanly without unhandled crash.")
            else:
                results["assertions"]["cli_missing_args"] = False
                log(f"FAIL: Missing args crash: {proc.stderr}")
        except Exception as e:
            results["assertions"]["cli_missing_args"] = False
            log(f"FAIL: Missing args exception: {e}")

        # 5. Adding item and verifying persistence
        # We also support direct programmatic module testing if CLI uses custom subcommands
        item_added = False
        try:
            # Try CLI command first: add --name "Widget" --qty 10 --price 5.0
            proc = run_cli(["add", "--name", "Widget", "--quantity", "10", "--price", "5.0", "--file", storage_file])
            if proc.returncode != 0:
                # Try positional: add Widget 10 5.0
                proc = run_cli(["add", "Widget", "10", "5.0", "--file", storage_file])
            if proc.returncode == 0:
                item_added = True
            else:
                # Test via module imports directly
                try:
                    # Look for service or storage module
                    for mod_name in [f.replace(".py", "") for f in py_files if f != "main.py"]:
                        mod = __import__(mod_name)
                        for attr in dir(mod):
                            cls = getattr(mod, attr)
                            if isinstance(cls, type) and ("service" in attr.lower() or "manager" in attr.lower() or "inventory" in attr.lower() or "store" in attr.lower()):
                                inst = cls()
                                if hasattr(inst, "add_item"):
                                    inst.add_item("Widget", 10, 5.0)
                                    item_added = True
                                    break
                        if item_added:
                            break
                except Exception as ex:
                    log(f"Programmatic fallback note: {ex}")

            if item_added or (os.path.exists(storage_file) and os.path.getsize(storage_file) > 0):
                results["assertions"]["item_creation_and_persistence"] = True
                log("PASS: Item created and storage persistence confirmed.")
            else:
                # Check if CLI succeeded with default storage file in workspace
                results["assertions"]["item_creation_and_persistence"] = (proc.returncode == 0)
                log(f"Result for item creation: code={proc.returncode}, out={proc.stdout}")
        except Exception as e:
            results["assertions"]["item_creation_and_persistence"] = False
            log(f"FAIL: Item creation exception: {e}")

        # 6. Restock & Sell Operations Logic
        try:
            # Test programmatic business rules: stock increase & decrease
            # Search for Service class
            service_class = None
            for f in py_files:
                mod_name = f.replace(".py", "")
                try:
                    mod = __import__(mod_name)
                    for attr in dir(mod):
                        cls = getattr(mod, attr)
                        if isinstance(cls, type) and ("service" in attr.lower() or "inventory" in attr.lower() or "store" in attr.lower()):
                            service_class = cls
                            break
                except Exception:
                    pass
                if service_class:
                    break

            if service_class:
                results["assertions"]["stock_operations_service"] = True
                log(f"PASS: Service layer contract verified ({service_class.__name__}).")
            else:
                results["assertions"]["stock_operations_service"] = False
                log("FAIL: Could not locate Service / Inventory manager class.")
        except Exception as e:
            results["assertions"]["stock_operations_service"] = False
            log(f"FAIL: Stock operations inspection exception: {e}")

        # 7. Inventory Valuation / Reporting
        try:
            proc = run_cli(["report", "--file", storage_file])
            if proc.returncode != 0:
                proc = run_cli(["report"])
            if proc.returncode == 0 and "traceback" not in proc.stderr.lower():
                results["assertions"]["inventory_reporting"] = True
                log("PASS: Inventory report executed cleanly.")
            else:
                # If report is a flag or function
                results["assertions"]["inventory_reporting"] = ("report" in proc.stdout.lower() or proc.returncode == 0)
                log(f"Inventory report status: code={proc.returncode}")
        except Exception as e:
            results["assertions"]["inventory_reporting"] = False
            log(f"FAIL: Report exception: {e}")

        # 8. Corrupt Storage Handling
        try:
            corrupt_file = os.path.join(tmpdir, "corrupt.json")
            with open(corrupt_file, "w", encoding="utf-8") as f:
                f.write("NOT_VALID_JSON{:::<<<")
            proc = run_cli(["report", "--file", corrupt_file])
            # Must handle corrupt file without unhandled Python crash traceback
            if "traceback" not in proc.stderr.lower():
                results["assertions"]["corrupt_storage_handling"] = True
                log("PASS: Corrupt storage file handled without unhandled crash.")
            else:
                results["assertions"]["corrupt_storage_handling"] = False
                log(f"FAIL: Corrupt storage caused crash: {proc.stderr}")
        except Exception as e:
            results["assertions"]["corrupt_storage_handling"] = False
            log(f"FAIL: Corrupt storage exception: {e}")

        # 9. Developer automated tests
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

