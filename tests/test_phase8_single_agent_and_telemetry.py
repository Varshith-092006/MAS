"""Phase 8 (DEC-041): single-agent baseline, per-agent telemetry, runner token_cap fix."""

import json
import os

import pytest

import eval.runner as runner_mod
from eval.telemetry import get_agent_breakdown, summarize_breakdown, pct_change
from mas.baselines.single_agent import SingleAgentBaseline, SYSTEM_PROMPT, _safe_rel_path
from mas.core.llm import FakeLLMProvider, ModelResult


@pytest.fixture
def isolated_runner(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_mod, "MANIFEST_FILE", str(tmp_path / "manifest.json"))
    monkeypatch.setattr(runner_mod, "generate_stats_markdown_report", lambda *a, **k: "")
    monkeypatch.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    r = runner_mod.EvaluationRunner(results_path=str(tmp_path / "results.csv"))
    return r, tmp_path


def test_single_agent_writes_files_with_one_call(tmp_path):
    out = SingleAgentBaseline(FakeLLMProvider()).run(
        requirement="Count items. The program must run with 'python main.py'.",
        run_id="p8_single_unit",
        model="fake",
        workspace_base=str(tmp_path),
    )
    assert out["files"] == ["main.py"]
    assert os.path.exists(os.path.join(out["workspace_path"], "main.py"))
    bd = get_agent_breakdown("p8_single_unit")
    assert bd["single_agent"]["calls"] == 1
    assert summarize_breakdown(bd)["calls"] == 1


def test_single_agent_unparseable_output_is_quality_failure_not_retry(tmp_path):
    calls = []

    class Garbage(FakeLLMProvider):
        def generate(self, messages, **kw):
            calls.append(1)
            return ModelResult(text="sorry, no code", model_name="fake", input_tokens=5, output_tokens=5, total_tokens=10)

    out = SingleAgentBaseline(Garbage()).run("req", run_id="p8_single_garbage", model="fake", workspace_base=str(tmp_path))
    assert len(calls) == 1  # never re-sent for quality
    assert out["files"] == [] and out["error"]


def test_single_agent_prompt_is_generic():
    # AGENTS.md rule 2: no task-specific content in prompts.
    lowered = SYSTEM_PROMPT.lower()
    for word in ("science", "inventory", "game", "student", "sales"):
        assert word not in lowered


def test_safe_rel_path_blocks_traversal():
    assert _safe_rel_path("../evil.py") is None
    assert _safe_rel_path("C:/x.py") is None
    assert _safe_rel_path("pkg/mod.py") == "pkg/mod.py"


def test_pct_change():
    assert pct_change(1.2, 1.0) == 20.0
    assert pct_change(1.0, 0) is None
    assert pct_change(None, 1.0) is None


def test_runner_single_system_simulation_records_breakdown(isolated_runner):
    r, tmp = isolated_runner
    res = r.run_benchmark(
        task_count=1, repeats=1, model="fake", use_fake=True,
        systems=["mas", "single"], tasks_file="eval/tasks_v2.json",
    )
    manifest = json.load(open(tmp / "manifest.json", encoding="utf-8"))
    runs = {x["system"]: x for x in manifest["runs"]}
    assert set(runs) == {"mas", "single"}
    assert runs["single"]["status"] == "SIMULATION_ONLY"
    assert runs["single"]["llm_calls"] == 1
    assert runs["single"]["agent_breakdown"]["single_agent"]["calls"] == 1
    assert "tester" not in runs["mas"]["agent_breakdown"]  # deterministic Tester
    assert runs["mas"]["llm_calls"] == sum(v["calls"] for v in runs["mas"]["agent_breakdown"].values())
    assert "single_quality" in res


def test_run_benchmark_defines_token_cap_for_live_path():
    """Regression: token_cap used to be undefined inside run_benchmark (NameError on live runs)."""
    import inspect
    src = inspect.getsource(runner_mod.EvaluationRunner.run_benchmark)
    assert "token_cap = " in src
    assert src.index("token_cap = ") < src.index("tot_tok > token_cap")
