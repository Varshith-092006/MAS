"""Deterministic design-vs-code conformance check (iCoder "reverse architecture validation").

iCoder's UMLBot/ReviewBot rebuild a design model from the generated code and diff it with
the forward design (paper Sec. 3.2.2, 3.2.4). This module does the same with the AST, at
zero LLM cost:

  forward design  = Architect's file_structure, class names in uml_class_diagram,
                    module_dependencies
  reverse design  = files, classes and intra-project imports found in the workspace

Deviations become review evidence and Developer feedback. They are signals, not hard
failures: a model may legitimately merge two planned modules.
"""

import ast
import os
import re
from typing import Any, Dict, List, Set

_SKIP = (".git", "__pycache__", ".mas_snapshots", ".pytest_cache")
# "class Foo", "class Foo {", "Foo <|-- Bar", plantuml "class Foo as ..."
_CLASS_DECL_RE = re.compile(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)")


def planned_classes(uml_text: str) -> Set[str]:
    names = set(_CLASS_DECL_RE.findall(uml_text or ""))
    names.discard("Diagram")
    names.discard("classDiagram")
    return names


def reverse_model(workspace_path: str) -> Dict[str, Any]:
    files: Set[str] = set()
    classes: Set[str] = set()
    imports: Dict[str, Set[str]] = {}
    for root, _, fnames in os.walk(workspace_path):
        if any(s in root for s in _SKIP):
            continue
        for fn in fnames:
            if not fn.endswith(".py"):
                continue
            rel = os.path.relpath(os.path.join(root, fn), workspace_path).replace("\\", "/")
            files.add(rel)
            mod = rel[:-3].replace("/", ".")
            try:
                with open(os.path.join(root, fn), "r", encoding="utf-8") as fh:
                    tree = ast.parse(fh.read())
            except Exception:
                continue
            deps: Set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes.add(node.name)
                elif isinstance(node, ast.Import):
                    deps.update(a.name.split(".")[0] for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    deps.add(node.module.split(".")[0])
            imports[mod] = deps
    local = {f[:-3].replace("/", ".").split(".")[0] for f in files}
    return {
        "files": files,
        "classes": classes,
        "imports": {m: sorted(d & local - {m}) for m, d in imports.items()},
    }


def check_conformance(architecture: Dict[str, Any], workspace_path: str) -> Dict[str, Any]:
    """Returns deviations between the Architect's design and the generated code."""
    if not architecture or not workspace_path or not os.path.isdir(workspace_path):
        return {"applicable": False}
    rev = reverse_model(workspace_path)
    planned_files = {
        str(f).replace("\\", "/").lstrip("./") for f in architecture.get("file_structure", []) or []
        if str(f).endswith(".py")
    }
    actual_basenames = {os.path.basename(f) for f in rev["files"]}
    missing_files = sorted(f for f in planned_files if f not in rev["files"] and os.path.basename(f) not in actual_basenames)

    p_classes = planned_classes(architecture.get("uml_class_diagram", ""))
    missing_classes = sorted(p_classes - rev["classes"])

    missing_deps: List[str] = []
    for mod, deps in (architecture.get("module_dependencies") or {}).items():
        m = str(mod).replace(".py", "").split("/")[-1]
        if m not in rev["imports"]:
            continue
        for d in deps or []:
            d = str(d).replace(".py", "").split("/")[-1]
            if d in rev["imports"] and d not in rev["imports"][m]:
                missing_deps.append(f"{m} -> {d}")

    checked = len(planned_files) + len(p_classes)
    deviations = len(missing_files) + len(missing_classes)
    score = round(1.0 - deviations / checked, 4) if checked else 1.0
    findings = (
        [f"Planned file not implemented: {f}" for f in missing_files]
        + [f"Planned class not found in code: {c}" for c in missing_classes]
        + [f"Planned dependency not present: {d}" for d in sorted(missing_deps)]
    )
    return {
        "applicable": checked > 0,
        "conformance_score": score,
        "missing_files": missing_files,
        "missing_classes": missing_classes,
        "missing_dependencies": sorted(missing_deps),
        "findings": findings[:8],
    }
