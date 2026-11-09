"""Unit tests for Phase 3: Task set, honest counting, statistics, and ablation switches."""

import hashlib
import json
import os
import pytest
from mas.core.llm import FakeLLMProvider
from mas.core.state import create_initial_state
from mas.core.workflow import MASWorkflow
from mas.core.context import ContextSlicer
from mas.agents.reviewer import ReviewerAgent
from mas.agents.architect import ArchitectAgent
from eval.runner import classify_failure, update_benchmark_manifest
from eval.stats import (
    bootstrap_ci,
    calculate_success_rate,
    compare_systems,
    wilcoxon_signed_rank_test,
    summarize_metric_distribution,
)


def test_tasks_v2_structure_and_categories():
    """Verify tasks_v2.json has 20 tasks, 4 per major category, with 40-80 word count."""
    tasks_file = "eval/tasks_v2.json"
    assert os.path.exists(tasks_file), "eval/tasks_v2.json must exist"

    with open(tasks_file, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    assert len(tasks) == 20, f"Expected 20 tasks, got {len(tasks)}"

    expected_categories = {"Education", "Work", "Life", "Games", "Creation"}
    by_category = {c: [] for c in expected_categories}
    names = set()

    for t in tasks:
        assert "task_id" in t
        assert "name" in t
        assert "description" in t
        assert "category" in t
        assert "subcategory" in t
        assert "word_count" in t

        cat = t["category"]
        assert cat in expected_categories, f"Unexpected category {cat}"
        by_category[cat].append(t)

        wc = t["word_count"]
        assert 40 <= wc <= 80, f"Task {t['name']} word count {wc} outside 40-80 range"

        assert t["name"] not in names, f"Duplicate task name {t['name']}"
        names.add(t["name"])

    for cat, items in by_category.items():
        assert len(items) == 4, f"Category {cat} has {len(items)} tasks, expected 4"


def test_tasks_v2_manifest_hash():
    """Verify tasks_v2_sha256 in benchmark_manifest matches file SHA-256."""
    with open("eval/tasks_v2.json", "rb") as f:
        computed_sha = hashlib.sha256(f.read()).hexdigest()

    with open("eval/benchmark_manifest.json", "r", encoding="utf-8") as f:
        manifest = json.load(f)

    recorded_sha = manifest.get("tasks_v2_sha256")
    assert recorded_sha == computed_sha, f"Manifest hash {recorded_sha} != computed {computed_sha}"


def test_category_map_covers_40_subcategories():
    """Verify category_map.json maps 40 subcategories to the 5 major categories."""
    map_file = "eval/category_map.json"
    assert os.path.exists(map_file), "eval/category_map.json must exist"

    with open(map_file, "r", encoding="utf-8") as f:
        cat_map = json.load(f)

    assert len(cat_map) == 40, f"Expected 40 subcategories, got {len(cat_map)}"
    valid_majors = {"Education", "Work", "Life", "Games", "Creation"}
    for subcat, major in cat_map.items():
        assert major in valid_majors, f"Invalid major category {major} for subcat {subcat}"


def test_honest_counting_and_official_row_designation(tmp_path):
    """Verify first non-infra attempt is official, quality failures count as 0, and reruns after infra error."""
    manifest_file = str(tmp_path / "test_manifest.json")
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump({"benchmark": "test", "runs": []}, f)

    runs = [
        # Attempt 1: Infra error (429 rate limit) -> retry permitted, not official
        {
            "run_id": "mas_task_01_r1",
            "task_id": "task_01",
            "system": "mas",
            "repeat_no": 1,
            "ablation": "A0",
            "status": "STOPPED_PROVIDER_QUOTA",
            "error": "HTTP 429: Rate limit exceeded",
            "quality": None,
            "tokens": 1200,
        },
        # Attempt 2: Quality failure (bad syntax / stopped budget ceiling) -> OFFICIAL, quality = 0.0
        {
            "run_id": "mas_task_01_r1_attempt2",
            "task_id": "task_01",
            "system": "mas",
            "repeat_no": 1,
            "ablation": "A0",
            "status": "STOPPED_BUDGET_CEILING",
            "error": "TokenCapExceededError",
            "quality": 0.65,
            "tokens": 62000,
        },
        # Attempt 3: Subsequent rerun attempt -> Unofficial (no cherry-picking after quality failure)
        {
            "run_id": "mas_task_01_r1_attempt3",
            "task_id": "task_01",
            "system": "mas",
            "repeat_no": 1,
            "ablation": "A0",
            "status": "COMPLETED",
            "quality": 0.85,
            "tokens": 45000,
        },
        # Simulation run: Must always be unofficial
        {
            "run_id": "sim_mas_task_01_r1",
            "task_id": "task_01",
            "system": "mas",
            "repeat_no": 1,
            "ablation": "A0",
            "status": "SIMULATION_ONLY",
            "execution_mode": "SIMULATED",
            "quality": 0.90,
            "tokens": 1000,
        },
    ]

    manifest = update_benchmark_manifest(runs, manifest_path=manifest_file)
    by_id = {r["run_id"]: r for r in manifest["runs"]}

    # Attempt 1: infra error
    assert by_id["mas_task_01_r1"]["official"] is False
    assert by_id["mas_task_01_r1"]["failure_classification"] == "INFRA_ERROR"
    assert "INFRA_ERROR" in by_id["mas_task_01_r1"]["retry_reason"]

    # Attempt 2: first non-infra -> official!
    assert by_id["mas_task_01_r1_attempt2"]["official"] is True
    assert by_id["mas_task_01_r1_attempt2"]["failure_classification"] == "QUALITY_FAILURE"
    assert by_id["mas_task_01_r1_attempt2"]["retry_reason"] is None
    assert by_id["mas_task_01_r1_attempt2"]["quality"] == 0.0  # Quality failure counted as 0.0

    # Attempt 3: subsequent attempt -> unofficial
    assert by_id["mas_task_01_r1_attempt3"]["official"] is False
    assert "Subsequent" in by_id["mas_task_01_r1_attempt3"]["retry_reason"]

    # Simulation run -> unofficial
    assert by_id["sim_mas_task_01_r1"]["official"] is False
    assert by_id["sim_mas_task_01_r1"]["retry_reason"] == "SIMULATION_ONLY"


def test_statistics_bootstrap_ci_reproducible():
    """Verify bootstrap 95% CI with 10,000 resamples and seed 42."""
    data = [0.85, 0.72, 0.91, 0.64, 0.78, 0.82]
    ci1 = bootstrap_ci(data, n_resamples=10000, seed=42)
    ci2 = bootstrap_ci(data, n_resamples=10000, seed=42)
    assert ci1 == ci2
    assert ci1[0] < ci1[1]
    assert 0.65 < ci1[0] < 0.80
    assert 0.78 < ci1[1] < 0.90

    # Edge cases
    assert bootstrap_ci([]) == (0.0, 0.0)
    assert bootstrap_ci([0.75]) == (0.75, 0.75)


def test_statistics_wilcoxon_signed_rank_test():
    """Verify scipy-based Wilcoxon signed-rank test and small n safety."""
    a = [0.85, 0.90, 0.78, 0.88, 0.92]
    b = [0.55, 0.60, 0.50, 0.62, 0.58]
    p_val = wilcoxon_signed_rank_test(a, b)
    assert 0.0 <= p_val <= 1.0

    # Identical samples should safely return 1.0
    assert wilcoxon_signed_rank_test([0.5, 0.5], [0.5, 0.5]) == 1.0

    # Empty / mismatched length
    assert wilcoxon_signed_rank_test([], []) == 1.0
    assert wilcoxon_signed_rank_test([0.5], [0.5, 0.6]) == 1.0


def test_calculate_success_rate():
    """Verify calculate_success_rate handles official completed runs."""
    runs = [
        {"official": True, "status": "COMPLETED"},
        {"official": True, "status": "COMPLETED_QUALITY_GATE"},
        {"official": True, "status": "STOPPED_BUDGET_CEILING"},
        {"official": True, "status": "FAILED"},
        {"official": False, "status": "COMPLETED"},  # Unofficial should be excluded
        {"official": False, "status": "SIMULATION_ONLY"},  # Simulation excluded
    ]
    # 2 completed out of 4 official runs = 0.50
    sr = calculate_success_rate(runs)
    assert sr == 0.50


def test_compare_systems_includes_new_statistics():
    """Verify compare_systems returns wilcoxon_p_value and bootstrap CIs."""
    mas = [0.80, 0.85, 0.75, 0.90]
    cd = [0.60, 0.65, 0.55, 0.70]
    res = compare_systems(mas, cd, metric_name="Quality")

    assert "wilcoxon_p_value" in res
    assert "permutation_p_value" in res
    assert "mas_ci_95_bootstrap" in res
    assert "chatdev_ci_95_bootstrap" in res
    assert res["mas_ci_95_bootstrap"][0] <= res["mas_ci_95_bootstrap"][1]


def test_ablation_a1_always_runs_architect(tmp_path):
    """A1 ablation: always run Architect even on SIMPLE tasks."""
    fake_llm = FakeLLMProvider()
    wf = MASWorkflow(llm=fake_llm, ablation="A1")
    state = wf.run(
        requirement="Simple counter program",
        task_id="test_a1",
        run_id="test_run_a1",
        workspace_base=str(tmp_path),
        ablation="A1",
    )
    # Even if router classified as SIMPLE, A1 forces Architect run
    assert state.get("ablation") == "A1"
    # Architecture artifact should be produced
    assert "Architecture" in state.get("artifacts", {})


def test_ablation_a2_disables_ast_slicing(tmp_path):
    """A2 ablation: send all files every iteration without AST slicing."""
    slicer = ContextSlicer()
    all_files = {"main.py": "x = 1", "util.py": "y = 2", "helper.py": "z = 3"}
    dep_graph = {"main": {"util"}}
    state = create_initial_state("test_a2", "req", "task", str(tmp_path))
    state["iteration"] = 2
    state["changed_files"] = ["main.py"]
    state["ablation"] = "A2"

    sliced = slicer.get_sliced_files(state, all_files, dep_graph)
    # Under A2, all workspace files are retained without AST impact slicing
    assert len(sliced) == 3
    assert set(sliced.keys()) == set(all_files.keys())


def test_ablation_a3_omits_deterministic_cross_checks(monkeypatch):
    """A3 ablation: Reviewer skips deterministic cross-checks (AST cycles, Ruff, Bandit, Sandbox)."""
    captured_prompt = None

    class MockLLM(FakeLLMProvider):
        def generate(self, messages, **kwargs):
            nonlocal captured_prompt
            captured_prompt = messages[-1]["content"]
            return super().generate(messages, **kwargs)

    llm = MockLLM()
    reviewer = ReviewerAgent(llm=llm, disable_grounded_review=True)
    state = create_initial_state("test_a3", "req", "task", "./tmp")
    state["ablation"] = "A3"
    state["artifacts"] = {
        "TaskPlan": {"acceptance_criteria": ["run test"]},
        "CodePatch": {"file_contents": {"main.py": "print('hello')"}},
    }
    reviewer.run(state)

    assert captured_prompt is not None
    assert "Ablation A3: ungrounded subjective review" in captured_prompt
    assert "AST Cycles:" not in captured_prompt


def test_ablation_a4_single_iteration_only(tmp_path):
    """A4 ablation: stops after iteration 1 without reflection loop."""
    fake_llm = FakeLLMProvider()
    wf = MASWorkflow(llm=fake_llm, ablation="A4")
    state = wf.run(
        requirement="Counter application",
        task_id="test_a4",
        run_id="test_run_a4",
        workspace_base=str(tmp_path),
        ablation="A4",
    )
    assert state.get("ablation") == "A4"
    assert state.get("iteration") == 1

