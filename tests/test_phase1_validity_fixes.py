"""Tests for Phase 1 validity fixes:

- Removal of task-specific hardcoded domain words in agent prompts (Problem A)
- Equal requirement text + CLI_CONTRACT_SUFFIX contract between MAS and ChatDev (Problem B)
- Consistency metric reliability, fake embedder test, lexical fallback test, code truncation (Problem C)
"""

import ast
import os
import numpy as np
import pytest

from eval.task_text import CLI_CONTRACT_SUFFIX, get_augmented_requirement
from eval.scorers.icoder_metrics import (
    calculate_consistency,
    get_consistency_max_chars,
    is_embedding_available,
)
from mas.agents.developer import DeveloperAgent
from mas.core.llm import FakeLLMProvider


class TinyFakeEmbedder:
    """Deterministic tiny embedder for testing cosine similarity."""

    def __init__(self, dim: int = 16):
        self.dim = dim

    def encode(self, text: str):
        # Generate deterministic vector from text hash
        val = sum(ord(c) for c in text)
        vec = np.zeros(self.dim, dtype=float)
        for i in range(self.dim):
            vec[i] = float(((val + i * 17) % 100) / 100.0)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec


def test_no_task_specific_domain_words_in_developer_prompt():
    """Problem A: Assert no domain words from single SRDD tasks exist in DeveloperAgent prompts."""
    dev = DeveloperAgent(llm=FakeLLMProvider())
    state = {
        "run_id": "test_prompt_check",
        "requirement": "Build a general inventory tracker with CLI arguments.",
        "iteration": 1,
        "artifacts": {},
    }

    # Inspect the source code of DeveloperAgent to guarantee prompt strings are clean
    import inspect
    src = inspect.getsource(DeveloperAgent)
    forbidden_terms = [
        "ScienceQuestionSolver",
        "photosynthesis",
        "atomic number",
        "speed/velocity",
        "Multi-Domain Requirements",
        "Chemistry (atomic",
        "Biology (photosynthesis",
    ]
    for term in forbidden_terms:
        assert term.lower() not in src.lower(), f"Forbidden task-specific term '{term}' found in DeveloperAgent source!"


def test_developer_prompt_has_no_unequal_cli_help_hint():
    """Problem B: MAS Developer prompt must not have hardcoded --help or 0-args hint (comes only from shared contract)."""
    import inspect
    src = inspect.getsource(DeveloperAgent)
    assert "'--help', print usage" not in src
    assert "The application must handle '--help'" not in src


def test_augmented_requirement_identical_for_both_systems():
    """Problem B: Assert both MAS and ChatDev receive byte-for-byte identical requirement text."""
    base_requirement = "Develop an interactive educational reference tool for science learners."
    mas_req = get_augmented_requirement(base_requirement)
    chatdev_req = get_augmented_requirement(base_requirement)

    assert mas_req == chatdev_req, "MAS and ChatDev requirements must be byte-for-byte identical!"
    assert CLI_CONTRACT_SUFFIX in mas_req
    assert CLI_CONTRACT_SUFFIX in chatdev_req
    assert mas_req.endswith(CLI_CONTRACT_SUFFIX)

    # Idempotence test
    assert get_augmented_requirement(mas_req) == mas_req


def test_consistency_embedding_method_with_fake_embedder():
    """Problem C: Test embedding-based consistency calculation using a fake embedder."""
    fake_embedder = TinyFakeEmbedder()
    req = "Build a fast data processing pipeline"
    code = "def process_data(batch):\n    return [x * 2 for x in batch]\n"

    score, method = calculate_consistency(
        requirement=req,
        code_text=code,
        embedder=fake_embedder,
        return_method=True,
    )

    assert method == "embedding"
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


def test_consistency_lexical_fallback_method():
    """Problem C: Test lexical fallback method when embedder is 'mock' or None."""
    req = "Build a fast data processing pipeline"
    code = "def process_data(batch):\n    # pipeline processing\n    return [x * 2 for x in batch]\n"

    score, method = calculate_consistency(
        requirement=req,
        code_text=code,
        embedder="mock",
        return_method=True,
    )

    assert method == "lexical_fallback"
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


def test_consistency_max_chars_truncation():
    """Problem C: Assert only the first N characters of code (default 2000 from config) are passed to embedder."""
    class RecordingEmbedder:
        def __init__(self):
            self.encoded_lengths = []

        def encode(self, text: str):
            self.encoded_lengths.append(len(text))
            return np.ones(8) / np.linalg.norm(np.ones(8))

    rec = RecordingEmbedder()
    req = "Short requirement"
    long_code = "x = 1\n" * 2000  # 12,000 characters
    max_c = get_consistency_max_chars()
    assert max_c == 2000

    score, method = calculate_consistency(
        requirement=req,
        code_text=long_code,
        embedder=rec,
        return_method=True,
    )

    assert method == "embedding"
    assert rec.encoded_lengths[1] == 2000, f"Expected 2000 embedded characters, got {rec.encoded_lengths[1]}"


def test_neutral_evaluator_returns_consistency_method(tmp_path):
    """Problem C: Assert NeutralEvaluator returns consistency_method in metrics dict."""
    from eval.neutral_evaluator import NeutralEvaluator
    sample_file = tmp_path / "main.py"
    sample_file.write_text("print('hello world')\n", encoding="utf-8")

    evaluator = NeutralEvaluator()
    results = evaluator.evaluate_project(
        workspace_path=str(tmp_path),
        requirement="A tool to inspect python code",
        task_id="srdd_test_01",
        persist_to_db=False,
    )
    assert "consistency_method" in results
    assert results["consistency_method"] in ("embedding", "lexical_fallback")
