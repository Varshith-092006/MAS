"""DEC-045: loop fixes P1-P4 found by the end-to-end audit (MAS_SYSTEM_GUIDE.md section 7).

P1 the Developer sees its current code from iteration 2 and may return only changed files
P2 the Architect's class diagram reaches the Developer
P3 the best-scoring iteration ships, not simply the last one
P4 guidance when the Developer's own unit tests fail
"""

import os

from mas.agents.developer import DeveloperAgent, SELF_TEST_GUIDANCE, current_code_section
from mas.agents.reviewer import ReviewerAgent
from mas.core.llm import FakeLLMProvider, ModelResult
from mas.core.state import create_initial_state

NL = "\n"


def _result(text):
    return ModelResult(
        text=text, model_name="fake", provider_model_version="fake", input_tokens=1, output_tokens=1,
        total_tokens=2, latency_ms=1, request_id="t", estimated_cost=0.0,
    )


class CapturingLLM(FakeLLMProvider):
    """Records prompts; answers the Developer with a fixed delimiter-block reply."""

    def __init__(self, developer_reply):
        super().__init__()
        self.prompts = []
        self.developer_reply = developer_reply

    def generate(self, messages, agent_name="agent", **kw):
        self.prompts.append((agent_name, messages[-1]["content"]))
        if agent_name == "developer":
            return _result(self.developer_reply)
        return super().generate(messages, agent_name=agent_name, **kw)


def _state(ws, iteration):
    st = create_initial_state("p8-loop", "Count words in a file", "t", str(ws), model="fake")
    st["iteration"] = iteration
    st["artifacts"]["TaskPlan"] = {"acceptance_criteria": ["counts words"]}
    st["artifacts"]["Architecture"] = {
        "file_structure": ["main.py", "counter.py"],
        "uml_class_diagram": "classDiagram" + NL + "class WordCounter { +count(text) int }",
    }
    return st


# ---------------------------------------------------------------- P1
def test_current_code_section_format_and_budget():
    files = {"util.py": "x = 1" + NL, "main.py": "print(1)" + NL, "notes.txt": "skip"}
    sec = current_code_section(files)
    assert sec.index("=== FILE: main.py ===") < sec.index("=== FILE: util.py ===")  # main.py first
    assert "notes.txt" not in sec and "Return ONLY the files you change" in sec
    small = current_code_section({"main.py": "a" * 50, "big.py": "b" * 500}, budget=200)
    assert "=== FILE: main.py ===" in small and "Not shown" in small and "big.py" in small
    assert current_code_section({}) == ""


def test_developer_sees_current_code_from_iteration_2_only(tmp_path):
    reply = "=== FILE: counter.py ===" + NL + "def count(t):" + NL + "    return len(t.split())" + NL + "=== END FILE ==="
    llm = CapturingLLM(reply)
    st = _state(tmp_path, iteration=1)
    st["context_files"] = {"main.py": "print('old main')"}
    DeveloperAgent(llm=llm).run(st)
    assert "print('old main')" not in llm.prompts[-1][1]

    st2 = _state(tmp_path, iteration=2)
    st2["context_files"] = {"main.py": "print('old main')"}
    DeveloperAgent(llm=llm).run(st2)
    prompt = llm.prompts[-1][1]
    assert "Current Code" in prompt and "print('old main')" in prompt


def test_partial_patch_keeps_unchanged_files(tmp_path):
    (tmp_path / "main.py").write_text("from counter import count" + NL + "print(count('a b'))" + NL)
    (tmp_path / "counter.py").write_text("def count(t):" + NL + "    return 0" + NL)
    reply = "=== FILE: counter.py ===" + NL + "def count(t):" + NL + "    return len(t.split())" + NL + "=== END FILE ==="
    st = _state(tmp_path, iteration=2)
    st["context_files"] = {"main.py": (tmp_path / "main.py").read_text(), "counter.py": (tmp_path / "counter.py").read_text()}
    st = DeveloperAgent(llm=CapturingLLM(reply)).run(st)
    assert st["changed_files"] == ["counter.py"]
    assert "from counter import count" in (tmp_path / "main.py").read_text()  # untouched
    assert "len(t.split())" in (tmp_path / "counter.py").read_text()


def test_reviewer_reviews_whole_workspace_after_partial_patch(tmp_path):
    (tmp_path / "main.py").write_text("print('UNCHANGED_MAIN_MARKER')" + NL)
    (tmp_path / "counter.py").write_text("def count(t):" + NL + "    return len(t.split())" + NL)
    llm = CapturingLLM("")
    st = _state(tmp_path, iteration=2)
    st["artifacts"]["CodePatch"] = {"file_contents": {"counter.py": "def count(t):" + NL + "    return len(t.split())"}}
    st["mas_pytest_report"] = {"pass_rate": 1.0, "details": []}
    st["sandbox_execution"] = {"is_success": True, "exit_code": 0}
    ReviewerAgent(llm=llm).run(st)
    reviewer_prompt = [p for a, p in llm.prompts if a == "reviewer"][-1]
    assert "UNCHANGED_MAIN_MARKER" in reviewer_prompt


def test_files_named_in_feedback_join_the_slice():
    """A file named in a failure stays visible even if it was neither changed nor dependent."""
    from mas.core.context import ContextSlicer

    workspace_files = {"main.py": "import util", "util.py": "x = 1", "test_main.py": "assert False"}
    st = create_initial_state("p1-slice", "req", "t", ".", model="fake")
    st["iteration"] = 3
    st["changed_files"] = ["util.py"]
    st["mas_pytest_report"] = {"details": ["FAILED pytest: test_main.py::test_x AssertionError"]}
    graph = {"main": {"util"}, "util": set(), "test_main": set()}
    sliced = ContextSlicer().build_context(st, workspace_files, graph)["files"]
    assert set(sliced) == {"util.py", "main.py"}  # changed + dependent; test_main.py not yet
    # The workflow adds files named in the feedback on top of the slice:
    import mas.core.workflow as wf_mod
    src = open(wf_mod.__file__, encoding="utf-8").read()
    assert "os.path.basename(rel_fp) in feedback_text" in src


# ---------------------------------------------------------------- P2
def test_class_diagram_reaches_developer(tmp_path):
    llm = CapturingLLM("=== FILE: main.py ===" + NL + "print(1)" + NL + "=== END FILE ===")
    DeveloperAgent(llm=llm).run(_state(tmp_path, iteration=1))
    prompt = llm.prompts[-1][1]
    assert "class WordCounter" in prompt and "Design (class diagram" in prompt


# ---------------------------------------------------------------- P4
def test_self_test_guidance_only_when_developer_tests_fail(tmp_path):
    llm = CapturingLLM("=== FILE: main.py ===" + NL + "print(1)" + NL + "=== END FILE ===")
    st = _state(tmp_path, iteration=2)
    st["mas_pytest_report"] = {"details": ["FAILED pytest (1 failing): AssertionError: 8 != 9"]}
    DeveloperAgent(llm=llm).run(st)
    assert SELF_TEST_GUIDANCE.strip() in llm.prompts[-1][1]

    st2 = _state(tmp_path, iteration=2)
    st2["mas_pytest_report"] = {"details": ["FAILED smoke: entry point runs without crashing: boom"]}
    DeveloperAgent(llm=llm).run(st2)
    assert SELF_TEST_GUIDANCE.strip() not in llm.prompts[-1][1]


# ---------------------------------------------------------------- P3
GOOD_MAIN = NL.join([
    "import argparse",
    "def add(a, b):",
    "    return a + b",
    "def main():",
    "    argparse.ArgumentParser().parse_args()",
    "    print(add(1, 2))",
    "if __name__ == '__main__':",
    "    main()",
]) + NL
FAILING_TEST = NL.join(["from main import add", "def test_ok():", "    assert add(1, 1) == 2", "def test_wrong():", "    assert add(1, 1) == 3"]) + NL
CRASHING_MAIN = "raise RuntimeError('regressed')" + NL


class RegressingLLM(FakeLLMProvider):
    """Iteration 1: working program with one wrong test (not clean). Later: a crashing program."""

    def generate(self, messages, agent_name="agent", **kw):
        if agent_name == "developer":
            content = messages[-1]["content"]
            if "Iteration: 1" in content:
                text = (
                    "=== FILE: main.py ===" + NL + GOOD_MAIN + "=== END FILE ===" + NL
                    + "=== FILE: test_main.py ===" + NL + FAILING_TEST + "=== END FILE ==="
                )
            else:
                text = "=== FILE: main.py ===" + NL + CRASHING_MAIN + "=== END FILE ==="
            return _result(text)
        return super().generate(messages, agent_name=agent_name, **kw)


def test_best_iteration_is_restored_when_later_iterations_regress(tmp_path):
    from mas.core.workflow import MASWorkflow

    st = MASWorkflow(llm=RegressingLLM()).run(
        requirement="Add two numbers", task_id="p3_best", run_id="p3_best", workspace_base=str(tmp_path),
    )
    ws = st["workspace_path"]
    assert st["iteration"] == 3  # all three iterations ran
    assert st["shipped_iteration"] == 1  # but iteration 1 shipped
    assert "def add" in open(os.path.join(ws, "main.py"), encoding="utf-8").read()
    assert "restored best iteration 1" in st["stop_reason"]
    assert st["sandbox_execution"]["is_success"] is True  # reports match the shipped code


def test_clean_final_iteration_is_never_replaced(tmp_path):
    from mas.core.workflow import MASWorkflow

    st = MASWorkflow(llm=FakeLLMProvider()).run(
        requirement="Simple math helper module", task_id="p3_clean", run_id="p3_clean", workspace_base=str(tmp_path),
    )
    assert st["shipped_iteration"] == st["iteration"]
