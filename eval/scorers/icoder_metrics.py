"""Neutral evaluator iCoder-style metrics: Completeness, Executability, Consistency, Quality."""

import ast
import os
from typing import Dict, List, Tuple
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
    """Calculates function completeness = 1 - (unimplemented / total_functions)."""
    total_funcs = 0
    unimplemented_funcs = 0

    for root, _, filenames in os.walk(workspace_path):
        if any(skip in root for skip in [".git", "__pycache__", ".mas_snapshots"]):
            continue
        for f in filenames:
            if f.endswith(".py"):
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

    if total_funcs == 0:
        return 1.0  # If script is module-level statements without explicit defs
    return round(1.0 - (unimplemented_funcs / total_funcs), 4)


def calculate_executability(workspace_path: str, sandbox_runner=None) -> float:
    """Checks if main entry point executes cleanly under neutral smoke test."""
    from mas.analysis.sandbox import SandboxRunner
    runner = sandbox_runner or SandboxRunner()

    entry_points = ["main.py", "app.py", "calculator.py"]
    chosen_entry = None
    for ep in entry_points:
        if os.path.exists(os.path.join(workspace_path, ep)):
            chosen_entry = ep
            break

    if not chosen_entry:
        # Pick any python file
        for f in os.listdir(workspace_path):
            if f.endswith(".py") and not f.startswith("test_"):
                chosen_entry = f
                break

    if not chosen_entry:
        return 0.0

    res = runner.smoke_run(workspace_path, entry_point=chosen_entry)
    return 1.0 if res.is_success else 0.0


_embedder = None


def get_embedding_model():
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedder = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            _embedder = "mock"
    return _embedder


def calculate_consistency(requirement: str, code_text: str) -> float:
    """Calculates cosine similarity between requirement and code embedding using all-MiniLM-L6-v2.

    (Note: This is an MAS implementation choice, not claimed to be iCoder's original model).
    """
    if not requirement or not code_text:
        return 0.5

    embedder = get_embedding_model()
    if embedder != "mock":
        try:
            emb1 = embedder.encode(requirement)
            emb2 = embedder.encode(code_text[:2000])  # limit length
            norm1 = np.linalg.norm(emb1)
            norm2 = np.linalg.norm(emb2)
            if norm1 > 0 and norm2 > 0:
                cosine = float(np.dot(emb1, emb2) / (norm1 * norm2))
                return round(max(0.0, min(cosine, 1.0)), 4)
        except Exception:
            pass

    # Deterministic lexical fallback
    req_words = set(requirement.lower().split())
    code_words = set(code_text.lower().split())
    if not req_words or not code_words:
        return 0.5
    overlap = len(req_words & code_words) / len(req_words | code_words)
    sim = 0.5 + min(overlap * 2.0, 0.5)
    return round(sim, 4)


def calculate_quality(completeness: float, executability: float, consistency: float) -> float:
    """Quality_i = Completeness_i * Executability_i * Consistency_i."""
    return round(completeness * executability * consistency, 4)
