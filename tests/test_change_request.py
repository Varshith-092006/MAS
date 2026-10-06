"""Unit and integration tests for Change Request flow."""

import os
from mas.core.change_request import ChangeRequestManager
from mas.core.llm import FakeLLMProvider


def test_change_request_diff_and_seeds(tmp_path):
    ws = tmp_path / "ws_change"
    os.makedirs(ws, exist_ok=True)
    with open(ws / "billing.py", "w") as f:
        f.write("def calculate_invoice(): pass\ndef get_tax(): pass\n")
    with open(ws / "users.py", "w") as f:
        f.write("def get_user(): pass\n")

    cm = ChangeRequestManager(llm=FakeLLMProvider())
    old_req = "Build a billing system with invoice generation"
    new_req = "Build a billing system with invoice generation and discount calculations"

    diff_info = cm.compute_requirement_diff(old_req, new_req)
    assert diff_info["has_changes"] is True
    assert "discount" in diff_info["added_terms"]

    seeds = cm.detect_seed_modules(str(ws), diff_info["added_terms"], diff_info["removed_terms"])
    assert len(seeds) > 0


def test_change_request_obsolete_code_detection(tmp_path):
    ws = tmp_path / "ws_obsolete"
    os.makedirs(ws, exist_ok=True)
    with open(ws / "service.py", "w") as f:
        f.write("def old_deprecated_method(): return 1\ndef active_method(): return 2\n")

    cm = ChangeRequestManager(llm=FakeLLMProvider())
    removed_terms = ["deprecated"]
    obsolete = cm.detect_obsolete_code(str(ws), removed_terms)
    assert len(obsolete) == 1
    assert "old_deprecated_method" in obsolete[0]
