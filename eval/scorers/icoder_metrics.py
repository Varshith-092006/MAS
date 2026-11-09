"""Neutral evaluator iCoder-style metrics: Completeness, Executability, Consistency, Quality."""

import ast
import os
from typing import Dict, List, Optional, Tuple, Union
import numpy as np


def is_unimplemented_function(func_node: ast.FunctionDef) -> bool:
    """Checks if a function body contains only pass, docstring, ellipsis, or NotImplementedError."""
    body = func_node.body
    if not body:
        return True

    # If only docstring
    if len(body) == 1 and isinstance(body[0], ast.Expr) and isinstance(body[0].value, (ast.Str, ast.Constant)):
        return True

    # Check for pass or ... or raise NotImplementedError
    for stmt in body:
        if isinstance(stmt, ast.Pass):
            return True
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and stmt.value.value is Ellipsis:
            return True
        if isinstance(stmt, ast.Raise):
            if isinstance(stmt.exc, ast.Name) and stmt.exc.id == "NotImplementedError":
                return True
            if isinstance(stmt.exc, ast.Call) and getattr(stmt.exc.func, "id", "") == "NotImplementedError":
                return True
    return False


def calculate_completeness(workspace_path: str) -> float:
    """Calculates function completeness = 1 - (unimplemented / total_functions).

    Returns 0.0 if no python code files exist in workspace.
    """
    total_funcs = 0
    unimplemented_funcs = 0
    has_py_files = False

    for root, _, filenames in os.walk(workspace_path):
        if any(skip in root for skip in [".git", "__pycache__", ".mas_snapshots"]):
            continue
        for f in filenames:
            if f.endswith(".py"):
                has_py_files = True
                path = os.path.join(root, f)
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        tree = ast.parse(fh.read(), filename=path)
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            total_funcs += 1
                            if is_unimplemented_function(node):
                                unimplemented_funcs += 1
                except Exception:
                    pass

    if not has_py_files:
        return 0.0
    if total_funcs == 0:
        return 1.0  # If script has module-level code without explicit function defs
    return round(1.0 - (unimplemented_funcs / total_funcs), 4)


def calculate_executability_v1_2(workspace_path: str, sandbox_runner=None) -> float:
    """Legacy Evaluator v1.2: checks if main entry point executes cleanly under zero-arg smoke test."""
    from mas.analysis.sandbox import SandboxRunner
    runner = sandbox_runner or SandboxRunner()

    entry_points = ["main.py", "app.py"]
    chosen_entry = None
    for ep in entry_points:
        if os.path.exists(os.path.join(workspace_path, ep)):
            chosen_entry = ep
            break

    if not chosen_entry and os.path.exists(workspace_path):
        for f in os.listdir(workspace_path):
            if f.endswith(".py") and not f.startswith("test_"):
                chosen_entry = f
                break

    if not chosen_entry:
        if os.path.exists(os.path.join(workspace_path, "index.html")):
            res = runner.smoke_run(workspace_path, entry_point=None, allow_fallback=True)
            return 1.0 if res.is_success else 0.0
        return 0.0

    # Legacy v1.2: direct zero-argument execution without CLI protocol fallback
    py_stem = os.path.splitext(chosen_entry)[0]
    smoke_code = (
        "import sys, os\n"
        "sys.path.insert(0, '.')\n"
        "import importlib\n"
        f"mod = importlib.import_module('{py_stem}')\n"
        "if hasattr(mod, 'main'):\n"
        "    try:\n"
        "        mod.main()\n"
        "    except SystemExit as se:\n"
        "        if se.code not in (0, None):\n"
        "            raise\n"
    )
    smoke_cmd = ["python", "-c", smoke_code]
    res = runner.execute(workspace_path, smoke_cmd, allow_fallback=True)
    return 1.0 if res.is_success else 0.0


def calculate_executability_v1_3(workspace_path: str, sandbox_runner=None) -> float:
    """Evaluator v1.3: executes Level 1 Entry-Point Smoke Protocol handling supported app types."""
    from mas.analysis.sandbox import SandboxRunner
    runner = sandbox_runner or SandboxRunner()

    entry_points = ["main.py", "app.py"]
    chosen_entry = None
    for ep in entry_points:
        if os.path.exists(os.path.join(workspace_path, ep)):
            chosen_entry = ep
            break

    if not chosen_entry and os.path.exists(workspace_path):
        for f in os.listdir(workspace_path):
            if f.endswith(".py") and not f.startswith("test_"):
                chosen_entry = f
                break

    if not chosen_entry:
        if os.path.exists(os.path.join(workspace_path, "index.html")):
            res = runner.smoke_run(workspace_path, entry_point=None, allow_fallback=True)
            return 1.0 if res.is_success else 0.0
        return 0.0

    res = runner.smoke_run(workspace_path, entry_point=chosen_entry, allow_fallback=True)
    return 1.0 if res.is_success else 0.0


def calculate_executability(workspace_path: str, sandbox_runner=None, version: str = "v1.3") -> float:
    """Calculates entry-point executability under specified evaluator methodology version."""
    if version == "v1.2":
        return calculate_executability_v1_2(workspace_path, sandbox_runner=sandbox_runner)
    return calculate_executability_v1_3(workspace_path, sandbox_runner=sandbox_runner)


_embedder = None


def get_consistency_max_chars() -> int:
    """Returns the maximum code characters to embed, configured in config.yaml."""
    try:
        from mas.core.config import get_config
        cfg = get_config()
        return int(cfg.get("eval", {}).get("consistency_max_code_chars", 2000))
    except Exception:
        return 2000


def get_embedding_model(force_reload: bool = False):
    global _embedder
    if force_reload:
        _embedder = None
    if _embedder is None:
        if os.environ.get("MAS_DISABLE_TORCH") == "1":
            _embedder = "mock"
            return _embedder
        try:
            from sentence_transformers import SentenceTransformer
            _embedder = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            _embedder = "mock"
    return _embedder


def is_embedding_available() -> bool:
    """Checks whether the real sentence-transformers model is loadable."""
    m = get_embedding_model()
    return m is not None and m != "mock"


def calculate_consistency(
    requirement: str,
    code_text: Optional[str],
    max_chars: Optional[int] = None,
    return_method: bool = False,
    embedder=None,
) -> Union[Optional[float], Tuple[Optional[float], str]]:
    """Calculates cosine similarity between requirement and code embedding using all-MiniLM-L6-v2.

    Returns None (or None, "unavailable") if requirement or code is missing.
    Uses sentence-transformers embedding when available; otherwise falls back to lexical overlap.
    Only the first max_chars (default 2000) characters of code are embedded.
    """
    if not requirement or not code_text or not code_text.strip():
        if return_method:
            return None, "unavailable"
        return None

    if max_chars is None:
        max_chars = get_consistency_max_chars()

    emb_model = embedder if embedder is not None else get_embedding_model()
    score = None
    method = "lexical_fallback"

    if emb_model and emb_model != "mock":
        try:
            emb1 = emb_model.encode(requirement)
            emb2 = emb_model.encode(code_text[:max_chars])
            norm1 = np.linalg.norm(emb1)
            norm2 = np.linalg.norm(emb2)
            if norm1 > 0 and norm2 > 0:
                cosine = float(np.dot(emb1, emb2) / (norm1 * norm2))
                score = round(max(0.0, min(cosine, 1.0)), 4)
                method = "embedding"
        except Exception:
            score = None

    if score is None:
        # Genuine lexical keyword overlap without artificial floor
        import re
        clean_req_words = set(w for w in re.findall(r'[a-zA-Z0-9_]{3,}', requirement.lower()) if w not in {'the', 'and', 'for', 'with', 'that', 'this', 'you', 'from'})
        clean_code_words = set(w for w in re.findall(r'[a-zA-Z0-9_]{3,}', code_text.lower()))
        if not clean_req_words:
            score = 0.0
        else:
            overlap = len(clean_req_words & clean_code_words)
            recall = overlap / len(clean_req_words)
            score = round(float(recall), 4)
        method = "lexical_fallback"

    if return_method:
        return score, method
    return score


def calculate_quality(
    completeness: Optional[float],
    executability: Optional[float],
    consistency: Optional[float],
) -> Optional[float]:
    """Quality_i = Completeness_i * Executability_i * Consistency_i.

    Returns None if any component metric is None / UNAVAILABLE.
    """
    if completeness is None or executability is None or consistency is None:
        return None
    return round(completeness * executability * consistency, 4)

