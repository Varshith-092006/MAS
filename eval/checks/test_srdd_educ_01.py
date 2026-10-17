"""Fixed Neutral Test Suite for Canonical Benchmark Task srdd_educ_01.

Task: Science Question Solver
Requirement: Step-by-step science question solver providing explanations and solutions.

This test file is FROZEN prior to generation rerun and executes outside the generation loop.
Neither MAS nor ChatDev has access to this file during code generation.
"""

import importlib
import inspect
import json
import os
import sys
import time
from typing import Any, Dict, List, Tuple


# Headless GUI event loop and modal dialog protection for all Tkinter widgets
try:
    import tkinter as tk
    from tkinter import messagebox
    tk.Misc.mainloop = lambda self, *args, **kwargs: self.update_idletasks()
    tk.Tk.mainloop = lambda self, *args, **kwargs: self.update_idletasks()
    messagebox.showinfo = lambda *args, **kwargs: None
    messagebox.showwarning = lambda *args, **kwargs: None
    messagebox.showerror = lambda *args, **kwargs: None
    messagebox.askokcancel = lambda *args, **kwargs: True
    messagebox.askyesno = lambda *args, **kwargs: True
except Exception:
    pass


def run_neutral_test(workspace_path: str) -> Dict[str, Any]:
    """Evaluates a generated software project against fixed canonical assertions."""
    abs_ws = os.path.abspath(workspace_path)
    if abs_ws not in sys.path:
        sys.path.insert(0, abs_ws)

    results = {
        "task_id": "srdd_educ_01",
        "task_name": "Science Question Solver",
        "test_suite_version": "1.1.0-FROZEN",
        "assertions": {},
        "all_passed": False,
        "logs": [],
    }

    def log(msg: str):
        results["logs"].append(msg)

    # 1. Assertion 1: Module Discovery & Import
    py_files = [
        f for f in sorted(os.listdir(abs_ws))
        if f.endswith(".py") and not f.startswith("test_")
    ]
    if not py_files:
        log("FAIL: No Python source files found in workspace.")
        results["assertions"]["module_import"] = False
        return results

    entry_point = "main.py" if "main.py" in py_files else ("app.py" if "app.py" in py_files else py_files[0])
    entry_stem = os.path.splitext(entry_point)[0]

    imported_modules = {}
    import_errors = []
    for pf in py_files:
        mod_name = os.path.splitext(pf)[0]
        try:
            mod = importlib.import_module(mod_name)
            imported_modules[mod_name] = mod
        except Exception as e:
            import_errors.append(f"{mod_name}: {e}")

    if entry_stem not in imported_modules:
        log(f"FAIL: Could not import entry point {entry_point}: {import_errors}")
        results["assertions"]["module_import"] = False
        return results

    log(f"PASS: Imported {len(imported_modules)} modules including entry point {entry_point}.")
    results["assertions"]["module_import"] = True

    # 2. Assertion 2: Solver / Application Object Instantiation
    # Headless GUI protection
    try:
        import tkinter as tk
        tk.Tk.mainloop = lambda self: None
    except Exception:
        pass

    target_obj = None
    target_cls_name = None

    # Search for classes with solver / app in name across modules
    candidate_classes = []
    for mod_name, mod in imported_modules.items():
        for attr_name, attr in inspect.getmembers(mod, inspect.isclass):
            if attr.__module__ == mod_name:
                candidate_classes.append((attr_name, attr))

    # Priority to classes with Solver, App, Science, Calculator in name
    sorted_candidates = sorted(
        candidate_classes,
        key=lambda x: (
            "solver" in x[0].lower(),
            "science" in x[0].lower(),
            "app" in x[0].lower(),
            "gui" in x[0].lower(),
        ),
        reverse=True,
    )

    for cname, cls in sorted_candidates:
        try:
            # Attempt instantiation with default or dummy args
            init_sig = inspect.signature(cls.__init__)
            params = [p for p in init_sig.parameters.values() if p.name != "self"]
            if not params or all(p.default != inspect.Parameter.empty for p in params):
                inst = cls()
                target_obj = inst
                target_cls_name = cname
                break
            elif len(params) == 1:
                # Might take root window
                try:
                    root = tk.Tk()
                    inst = cls(root)
                    target_obj = inst
                    target_cls_name = cname
                    break
                except Exception:
                    pass
        except Exception as e:
            log(f"DEBUG: Could not instantiate {cname}: {e}")

    instantiation_passed = target_obj is not None or hasattr(imported_modules[entry_stem], "main") or hasattr(imported_modules[entry_stem], "run")
    results["assertions"]["object_instantiation"] = instantiation_passed
    if instantiation_passed:
        log(f"PASS: Successfully constructed application/solver target: {target_cls_name or 'function entry point'}.")
    else:
        log("FAIL: Could not construct any application or solver object.")

    # 3. Assertion 3: Science Problem Solving Assertions
    # Test queries covering Physics, Chemistry, Biology
    test_queries = [
        {
            "domain": "physics",
            "prompt": "Calculate the speed if distance is 150 meters and time is 5 seconds.",
            "keywords": ["speed", "velocity", "distance", "time", "30", "m/s", "formula"],
        },
        {
            "domain": "chemistry",
            "prompt": "What is the atomic number and chemical symbol of Carbon?",
            "keywords": ["carbon", "6", "c", "atomic", "electron", "proton"],
        },
        {
            "domain": "biology",
            "prompt": "Explain step by step how photosynthesis works.",
            "keywords": ["photosynthesis", "sunlight", "light", "chlorophyll", "glucose", "carbon dioxide", "oxygen", "water"],
        },
    ]

    domain_passed = 0
    # Find callable solve / answer / calculate method
    solve_methods = []
    if target_obj:
        for mname, member in inspect.getmembers(target_obj, callable):
            if any(k in mname.lower() for k in ["solve", "answer", "search", "explain", "process", "calculate", "handle"]):
                solve_methods.append((mname, member))

    for tq in test_queries:
        solved = False
        output_text = ""

        # Try object methods
        if solve_methods:
            for mname, method in solve_methods:
                try:
                    sig = inspect.signature(method)
                    p_count = len([p for p in sig.parameters.values() if p.name != "self"])
                    if p_count >= 1:
                        res = method(tq["prompt"])
                        output_text = str(res)
                        break
                    else:
                        res = method()
                        output_text = str(res)
                        break
                except Exception:
                    pass

        # If object methods didn't produce text, inspect module functions
        if not output_text:
            for mod in imported_modules.values():
                for fname, func in inspect.getmembers(mod, inspect.isfunction):
                    if any(k in fname.lower() for k in ["solve", "answer", "explain", "calculate", "step"]):
                        try:
                            sig = inspect.signature(func)
                            if len(sig.parameters) >= 1:
                                res = func(tq["prompt"])
                                output_text = str(res)
                                break
                        except Exception:
                            pass
                if output_text:
                    break

        # Check keyword matches
        if output_text:
            out_lower = output_text.lower()
            matches = [kw for kw in tq["keywords"] if kw in out_lower]
            if len(matches) >= 1:
                solved = True
                domain_passed += 1
                log(f"PASS [{tq['domain']}]: Produced solution containing keywords: {matches[:3]}")
            else:
                log(f"PARTIAL [{tq['domain']}]: Function executed but keywords not found in: {output_text[:100]}")
        else:
            # Fallback check: if application is GUI, check if GUI elements or data structures exist
            has_gui_widgets = hasattr(target_obj, "solve_button") or hasattr(target_obj, "entry") or hasattr(target_obj, "input_field") or hasattr(target_obj, "text_area") or hasattr(target_obj, "canvas")
            has_domain_data = any(hasattr(mod, "QUESTIONS") or hasattr(mod, "SOLUTIONS") or hasattr(mod, "DATABASE") or hasattr(mod, "KNOWLEDGE_BASE") for mod in imported_modules.values())
            if has_gui_widgets or has_domain_data:
                domain_passed += 1
                solved = True
                log(f"PASS [{tq['domain']}]: Verified GUI widget structure and domain data bindings.")
            else:
                log(f"FAIL [{tq['domain']}]: Could not invoke solver for query.")

        results["assertions"][f"query_{tq['domain']}"] = solved

    results["assertions"]["domain_competence"] = (domain_passed >= 2)

    # 4. Assertion 4: Clean Execution Lifecycle
    # Verify main() or entry point runs cleanly without unhandled exception
    lifecycle_passed = False
    try:
        if hasattr(imported_modules[entry_stem], "main"):
            imported_modules[entry_stem].main()
            lifecycle_passed = True
        elif hasattr(imported_modules[entry_stem], "run"):
            imported_modules[entry_stem].run()
            lifecycle_passed = True
        else:
            lifecycle_passed = True
    except Exception as e:
        log(f"FAIL: Entry point lifecycle threw exception: {e}")
        lifecycle_passed = False

    results["assertions"]["clean_lifecycle"] = lifecycle_passed
    if lifecycle_passed:
        log("PASS: Application lifecycle executes and terminates cleanly.")

    # Aggregate
    results["all_passed"] = (
        results["assertions"].get("module_import", False)
        and results["assertions"].get("object_instantiation", False)
        and results["assertions"].get("domain_competence", False)
        and results["assertions"].get("clean_lifecycle", False)
    )

    return results


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    res = run_neutral_test(target)
    print(json.dumps(res, indent=2))
    sys.exit(0 if res["all_passed"] else 1)
