"""Phase 8 (DEC-041): deterministic Tester, real completeness signal, review-once policy."""

from mas.agents.tester import TesterAgent, scan_placeholders, parse_pytest_counts, find_test_files
from mas.core.llm import FakeLLMProvider
from mas.core.state import create_initial_state


class NoCallLLM(FakeLLMProvider):
    def generate(self, *a, **k):  # pragma: no cover - must never be reached
        raise AssertionError("Deterministic Tester must not call the LLM")


def _state(ws):
    st = create_initial_state("p8-run", "req", "t", str(ws), model="fake")
    st["artifacts"]["TaskPlan"] = {"acceptance_criteria": []}
    return st


GOOD_MAIN = (
    "import argparse\n\n"
    "def add(a, b):\n    return a + b\n\n"
    "def main():\n"
    "    p = argparse.ArgumentParser()\n"
    "    p.parse_args()\n"
    "    print(add(1, 2))\n\n"
    "if __name__ == '__main__':\n    main()\n"
)


def test_clean_project_passes_all_checks_with_zero_llm_calls(tmp_path):
    (tmp_path / "main.py").write_text(GOOD_MAIN, encoding="utf-8")
    st = TesterAgent(llm=NoCallLLM(), mode="deterministic").run(_state(tmp_path))
    rep = st["mas_pytest_report"]
    assert rep["failed_tests"] == 0
    assert rep["pass_rate"] == 1.0
    assert rep["coverage"] == 0.0  # never invented
    assert st["internal_completeness"] == 1.0


def test_crashing_project_fails_smoke_and_reports_real_stderr(tmp_path):
    (tmp_path / "main.py").write_text("raise RuntimeError('boom at startup')\n", encoding="utf-8")
    st = TesterAgent(llm=NoCallLLM(), mode="deterministic").run(_state(tmp_path))
    rep = st["mas_pytest_report"]
    assert rep["pass_rate"] < 1.0
    assert any("boom at startup" in d for d in rep["details"])


def test_placeholders_lower_internal_completeness(tmp_path):
    code = GOOD_MAIN + "\n\ndef todo_func():\n    pass\n\ndef doc_only():\n    \"\"\"Nothing.\"\"\"\n"
    (tmp_path / "main.py").write_text(code, encoding="utf-8")
    total, unimpl, findings = scan_placeholders(str(tmp_path))
    assert total == 4 and unimpl == 2
    assert any("empty 'pass' body" in f for f in findings)
    assert any("docstring-only" in f for f in findings)
    st = TesterAgent(llm=NoCallLLM(), mode="deterministic").run(_state(tmp_path))
    assert st["internal_completeness"] == 0.5


def test_todo_marker_counts_as_unimplemented(tmp_path):
    (tmp_path / "main.py").write_text("def f():\n    # TODO: finish\n    return 1\n", encoding="utf-8")
    _, unimpl, findings = scan_placeholders(str(tmp_path))
    assert unimpl == 1 and "TODO" in findings[0]


def test_developer_pytest_files_are_executed(tmp_path):
    (tmp_path / "main.py").write_text(GOOD_MAIN, encoding="utf-8")
    (tmp_path / "test_main.py").write_text(
        "from main import add\n\n"
        "def test_ok():\n    assert add(2, 2) == 4\n\n"
        "def test_bad():\n    assert add(2, 2) == 5\n",
        encoding="utf-8",
    )
    assert find_test_files(str(tmp_path)) == ["test_main.py"]
    st = TesterAgent(llm=NoCallLLM(), mode="deterministic").run(_state(tmp_path))
    rep = st["mas_pytest_report"]
    # 3 built-in checks pass + 1 pytest pass; 1 pytest failure
    assert rep["passed_tests"] == 4
    assert rep["failed_tests"] == 1
    assert any("pytest" in d for d in rep["details"])


def test_parse_pytest_counts():
    assert parse_pytest_counts("....\n3 passed, 1 failed in 0.1s") == (3, 1)
    assert parse_pytest_counts("2 passed in 0.01s") == (2, 0)
    assert parse_pytest_counts("1 failed, 1 error in 0.2s") == (0, 2)
    assert parse_pytest_counts("") == (0, 0)


def test_default_mode_comes_from_config():
    assert TesterAgent(llm=NoCallLLM()).mode == "deterministic"


def test_semantic_bug_is_caught_by_review_even_when_code_runs(tmp_path):
    """Code that runs but is wrong must still get a review (Reviewer runs once per run)."""
    from mas.core.workflow import MASWorkflow

    calls = []

    class Tracking(FakeLLMProvider):
        def generate(self, messages, agent_name=None, **kw):
            calls.append(agent_name)
            return super().generate(messages, agent_name=agent_name, **kw)

    MASWorkflow(llm=Tracking()).run(
        requirement="Simple math helper module",
        task_id="p8_review_once",
        run_id="p8_review_once",
        workspace_base=str(tmp_path),
    )
    assert "tester" not in calls
    assert calls.count("reviewer") == 1
    assert len(calls) <= 3
