"""Unit tests for deterministic ComplexityRouter and 10 draft diagnostics."""

import json
import os
import pytest
from mas.agents.router import ComplexityRouter


def test_router_simple_task():
    router = ComplexityRouter(threshold=4)
    req = "Write a python function to compute the factorial of a number."
    label, score, features = router.route(req)
    assert label == "SIMPLE"
    assert score <= 3
    assert "persistence" not in features


def test_router_structured_task():
    router = ComplexityRouter(threshold=4)
    req = (
        "Build a multi-user inventory management system with a SQLite database, "
        "user authentication and login, role-based access for admin and staff roles, "
        "REST API endpoints, and an order approval workflow state machine."
    )
    label, score, features = router.route(req)
    assert label == "STRUCTURED"
    assert score >= 4
    assert "persistence" in features
    assert "authentication" in features
    assert "multiple_roles" in features
    assert "workflow_state" in features


def test_router_separator_rules():
    router = ComplexityRouter(threshold=4)
    # 4 separators should give +1 bonus
    req_4_seps = "Item one, and item two; item three, and item four."
    _, _, feat_4 = router.route(req_4_seps)
    assert feat_4["separator_bonus"] >= 1

    # 7 separators should give +2 bonus
    req_7_seps = "One, two, three, four, five, six, seven, and eight."
    _, _, feat_7 = router.route(req_7_seps)
    assert feat_7["separator_bonus"] == 2


def test_router_length_rule():
    router = ComplexityRouter(threshold=4)
    long_req = " ".join(["word"] * 85)
    _, _, feat = router.route(long_req)
    assert feat["length_bonus"] == 1


def test_router_diagnostics_10_draft():
    """Evaluates the 10 draft hand-labelled requirements from evaluation/router_labels.json."""
    labels_file = os.path.join("evaluation", "router_labels.json")
    assert os.path.exists(labels_file), "evaluation/router_labels.json must exist"

    with open(labels_file, "r", encoding="utf-8") as f:
        items = json.load(f)

    assert len(items) == 10, "Must contain exactly 10 draft requirements"

    router = ComplexityRouter(threshold=4)
    correct = 0
    false_simple = 0
    false_structured = 0

    for item in items:
        assert item.get("needs_human_review") is True, "Must include needs_human_review: true"
        label, score, _ = router.route(item["requirement"])
        expected = item["expected_label"]

        if label == expected:
            correct += 1
        elif label == "SIMPLE" and expected == "STRUCTURED":
            false_simple += 1
        elif label == "STRUCTURED" and expected == "SIMPLE":
            false_structured += 1

    accuracy = correct / len(items)
    print(f"\nRouter Diagnostic Accuracy: {accuracy:.2f} (False SIMPLE: {false_simple}, False STRUCTURED: {false_structured})")
    assert accuracy >= 0.8, f"Expected accuracy >= 0.8 on diagnostic draft, got {accuracy}"
