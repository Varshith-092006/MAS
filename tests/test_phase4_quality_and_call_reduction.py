"""Unit tests for Phase 4: Improve MAS quality and cut LLM calls."""

import ast
import os
import pytest
from mas.core.config import get_config
from mas.core.llm import FakeLLMProvider, TokenLogger
from mas.core.governor import ProviderQuotaGovernor
from mas.core.state import create_initial_state
from mas.core.workflow import MASWorkflow
from mas.agents.developer import DeveloperAgent, parse_delimiter_blocks
from mas.analysis.deterministic_checker import DeterministicRepairChecker


def test_change1_one_source_for_token_cap():
    """Verify config.yaml, TokenLogger, and ProviderQuotaGovernor all read the same token cap."""
    cfg = get_config()
    cap = cfg.get("limits", {}).get("max_tokens_per_run")
    assert cap == 100000, f"Expected 100000 in config.yaml, got {cap}"

    t_logger = TokenLogger()
    assert t_logger.max_tokens_per_run == 100000

    governor = ProviderQuotaGovernor()
    assert governor.max_tokens_per_run == 100000


def test_change2_delimiter_blocks_valid_and_multiple_files():
    """Verify parsing valid delimiter blocks with multiple files."""
    text = (
        "Here is the code implementation:\n"
        "=== FILE: main.py ===\n"
        "def main():\n"
        "    print('Hello World')\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
        "=== END FILE ===\n\n"
        "=== FILE: utils.py ===\n"
        "def add(a, b):\n"
        "    return a + b\n"
        "=== END FILE ===\n"
    )
    res = parse_delimiter_blocks(text)
    assert res is not None
    assert set(res["files"]) == {"main.py", "utils.py"}
    assert "print('Hello World')" in res["file_contents"]["main.py"]
    assert "return a + b" in res["file_contents"]["utils.py"]


def test_change2_delimiter_blocks_missing_end_marker_recovery():
    """Verify recovery when === END FILE === marker is omitted."""
    text = (
        "=== FILE: main.py ===\n"
        "def run():\n"
        "    return 42\n"
        "=== FILE: helper.py ===\n"
        "VALUE = 100\n"
    )
    res = parse_delimiter_blocks(text)
    assert res is not None
    assert "main.py" in res["files"]
    assert "helper.py" in res["files"]
    assert "return 42" in res["file_contents"]["main.py"]
    assert "VALUE = 100" in res["file_contents"]["helper.py"]


def test_change2_delimiter_blocks_quotes_and_backslashes():
    """Verify quotes and backslashes are preserved literally without escaping corruption."""
    text = (
        "=== FILE: main.py ===\n"
        'regex = r"^[a-zA-Z0-9_\\-\\.]+\\.py$"\n'
        'quote_str = "He said \\"Hello\\" and \'welcome\'"\n'
        "=== END FILE ===\n"
    )
    res = parse_delimiter_blocks(text)
    assert res is not None
    code = res["file_contents"]["main.py"]
    assert 'regex = r"^[a-zA-Z0-9_\\-\\.]+\\.py$"' in code
    assert 'He said \\"Hello\\"' in code


def test_change2_delimiter_blocks_reasoning_before_first_marker():
    """Verify preceding chain-of-thought or conversational preamble is ignored."""
    text = (
        "I will now design the solution.\n"
        "First, I consider standard library modules.\n"
        "Then I write the implementation.\n\n"
        "=== FILE: main.py ===\n"
        "def execute():\n"
        "    return True\n"
        "=== END FILE ===\n"
    )
    res = parse_delimiter_blocks(text)
    assert res is not None
    assert "main.py" in res["files"]
    assert "I will now design" not in res["file_contents"]["main.py"]
    assert "def execute():" in res["file_contents"]["main.py"]


def test_change3_deterministic_checker_detects_defects(tmp_path):
    """Verify deterministic checker catches missing main.py, syntax errors, and placeholders."""
    # 1. Missing main.py
    ws1 = tmp_path / "ws1"
    ws1.mkdir()
    (ws1 / "util.py").write_text("x = 1", encoding="utf-8")
    errs1 = DeterministicRepairChecker.run_checks(str(ws1), run_smoke=False)
    assert any("Missing required entry point" in e for e in errs1)

    # 2. Syntax error
    ws2 = tmp_path / "ws2"
    ws2.mkdir()
    (ws2 / "main.py").write_text("def foo(:\n    pass", encoding="utf-8")
    errs2 = DeterministicRepairChecker.run_checks(str(ws2), run_smoke=False)
    assert any("SyntaxError" in e for e in errs2)

    # 3. Placeholders: pass-only and NotImplementedError
    ws3 = tmp_path / "ws3"
    ws3.mkdir()
    code3 = (
        "def calc_tax(income):\n"
        "    pass\n\n"
        "def calc_discount(price):\n"
        "    raise NotImplementedError()\n"
    )
    (ws3 / "main.py").write_text(code3, encoding="utf-8")
    errs3 = DeterministicRepairChecker.run_checks(str(ws3), run_smoke=False)
    assert any("empty 'pass' body" in e for e in errs3)
    assert any("NotImplementedError" in e for e in errs3)


def test_change4_review_runs_once_then_is_skipped_when_clean(tmp_path):
    """Phase 8 (DEC-041): with a deterministic Tester the Reviewer runs once per run; the
    skip only applies once a review has PASSED and the code is still clean."""
    reviewer_calls = []

    class TrackingLLM(FakeLLMProvider):
        def generate(self, messages, agent_name=None, **kwargs):
            if agent_name == "reviewer":
                reviewer_calls.append(1)
            return super().generate(messages, agent_name=agent_name, **kwargs)

    llm = TrackingLLM()
    wf = MASWorkflow(llm=llm)
    state = wf.run(
        requirement="CLI hello application",
        task_id="test_skip_review",
        run_id="test_run_skip_review",
        workspace_base=str(tmp_path),
    )
    assert len(reviewer_calls) == 1
    assert state.get("review_report", {}).get("status") == "PASSED"


def test_change4_legacy_llm_tester_still_skips_review_when_clean(tmp_path, monkeypatch):
    """Legacy mode (deterministic_tester: false) keeps the Phase 4 skip rule."""
    import mas.agents.tester as tester_mod
    orig_init = tester_mod.TesterAgent.__init__

    def legacy_init(self, llm, mode=None, **kw):
        orig_init(self, llm, mode="llm", **kw)

    monkeypatch.setattr(tester_mod.TesterAgent, "__init__", legacy_init)
    reviewer_calls = []

    class TrackingLLM(FakeLLMProvider):
        def generate(self, messages, agent_name=None, **kwargs):
            if agent_name == "reviewer":
                reviewer_calls.append(1)
            return super().generate(messages, agent_name=agent_name, **kwargs)

    state = MASWorkflow(llm=TrackingLLM()).run(
        requirement="CLI hello application",
        task_id="test_skip_review_legacy",
        run_id="test_run_skip_review_legacy",
        workspace_base=str(tmp_path),
    )
    assert reviewer_calls == []
    assert "skipped" in state.get("review_report", {}).get("summary", "").lower()


def test_change5_tester_trims_assertion_output_to_40_lines():
    """Verify TesterAgent limits failing assertion feedback to at most 40 lines."""
    long_traceback = "\n".join(f"Traceback frame line {i}" for i in range(100))

    class MockTesterLLM(FakeLLMProvider):
        def generate(self, messages, **kwargs):
            res = super().generate(messages, **kwargs)
            res.parsed_json = {
                "total_tests": 2,
                "passed_tests": 1,
                "failed_tests": 1,
                "pass_rate": 0.5,
                "coverage": 50.0,
                "details": [long_traceback],
            }
            return res

    from mas.agents.tester import TesterAgent
    llm = MockTesterLLM()
    tester = TesterAgent(llm=llm, mode="llm")
    state = create_initial_state("test_trim", "req", "task", "./tmp")
    state["artifacts"]["TaskPlan"] = {"acceptance_criteria": ["Run tests"]}

    res_state = tester.run(state)
    details = res_state["mas_pytest_report"]["details"]
    assert len(details) > 0
    # Line count of feedback item should be at most 40 lines
    line_count = len(details[0].splitlines())
    assert line_count <= 40


def test_change7_clean_first_iteration_uses_at_most_3_calls(tmp_path):
    """A clean first iteration consumes at most 3 LLM calls (Manager, Developer, Reviewer; Tester is deterministic)."""
    calls_made = []

    class CallTrackingLLM(FakeLLMProvider):
        def generate(self, messages, agent_name=None, **kwargs):
            calls_made.append(agent_name or "unknown")
            return super().generate(messages, agent_name=agent_name, **kwargs)

    llm = CallTrackingLLM()
    wf = MASWorkflow(llm=llm)
    state = wf.run(
        requirement="Simple math helper module",
        task_id="test_calls_budget",
        run_id="test_run_calls_budget",
        workspace_base=str(tmp_path),
    )

    # On clean first iteration: Manager (1), Developer (1), Tester (1) -> 3 calls max!
    assert len(calls_made) <= 3, f"Expected <= 3 calls, got {len(calls_made)}: {calls_made}"
    assert state.get("iteration") == 1

