"""DEC-044: fixes from the 5-task Gemini pilot run.

Parser variants, shared generic generation rules, one per-call output cap for every system,
and benchmark series scoping (pilot rows can never mix with runs on newer code).
"""

import json
import os
import sys

import eval.runner as runner_mod
from eval.runner import current_series, update_benchmark_manifest
from mas.agents.developer import GENERATION_RULES, max_output_tokens, parse_delimiter_blocks
from mas.baselines.single_agent import SYSTEM_PROMPT

NL = "\n"


def test_parser_accepts_end_marker_with_filename():
    text = NL.join([
        "=== FILE: main.py ===", "print('a')", "=== END FILE: main.py ===",
        "=== FILE: util.py ===", "x = 1", "=== END FILE ===",
    ])
    files = parse_delimiter_blocks(text)["file_contents"]
    assert files == {"main.py": "print('a')", "util.py": "x = 1"}


def test_parser_accepts_quoted_or_backticked_names():
    text = NL.join(["=== FILE: `main.py` ===", "print(1)", "=== END FILE ===",
                    '=== FILE: "helper.py" ===', "y = 2", "=== END FILE ==="])
    files = parse_delimiter_blocks(text)["file_contents"]
    assert set(files) == {"main.py", "helper.py"}


def test_end_marker_never_left_in_code():
    text = NL.join(["=== FILE: main.py ===", "print(1)", "=== END FILE main.py ==="])
    assert "END FILE" not in parse_delimiter_blocks(text)["file_contents"]["main.py"]


def test_generation_rules_are_generic_and_shared():
    assert "standard library" in GENERATION_RULES and "EOFError" in GENERATION_RULES
    assert GENERATION_RULES in SYSTEM_PROMPT  # single-agent gets the same rules as the MAS Developer
    for word in ("book", "inventory", "game", "student", "language"):
        assert word not in GENERATION_RULES.lower()
    assert all(line.startswith("- ") for line in GENERATION_RULES.strip().split(NL))


def test_output_cap_comes_from_config():
    assert max_output_tokens() == 8192


def test_proxy_uses_the_same_output_cap(monkeypatch):
    """ChatDev (through the proxy) is capped exactly like MAS and the single agent."""
    import asyncio
    import httpx
    import mas.core.governor as governor_mod
    import mas.core.proxy as proxy_mod

    sent = {}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json=None, headers=None):
            sent.update(json or {})
            return httpx.Response(200, json={"id": "x", "model": "m-1",
                                             "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                                             "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}},
                                  request=httpx.Request("POST", url))

    monkeypatch.setattr(governor_mod, "GovernedHTTPClient", FakeClient)

    async def call(max_tokens):
        transport = httpx.ASGITransport(app=proxy_mod.proxy_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://proxy.test") as c:
            await c.post("/v1/chat/completions",
                         json={"model": "m-1", "messages": [{"role": "user", "content": "hi"}], "max_tokens": max_tokens},
                         headers={"Authorization": "Bearer test-key-not-real"})

    asyncio.run(call(50000))
    assert sent["max_tokens"] == max_output_tokens()


def test_current_series_from_config():
    assert current_series() == "v2"


def _rec(run_id, series=None):
    r = {"run_id": run_id, "task_id": "t1", "system": "mas", "repeat_no": 1, "ablation": "A0", "model": "m",
         "status": "COMPLETED", "tokens": 100, "llm_calls": 3, "quality": 0.5, "execution_mode": "LIVE_API",
         "is_live_benchmark": True, "timestamp_utc": "2026-11-22T00:00:00Z", "provider": "gemini"}
    if series:
        r["series"] = series
    return r


def test_official_rows_are_scoped_by_series(tmp_path):
    m = update_benchmark_manifest([_rec("mas_t1_r1"), _rec("mas_t1_r1_attempt2", series="v2")],
                                  manifest_path=str(tmp_path / "m.json"), canonical_task_ids={"t1"})
    assert {str(r.get("series") or "v1"): r["official"] for r in m["runs"]} == {"v1": True, "v2": True}


def test_resume_does_not_skip_tasks_done_only_in_an_older_series(tmp_path, monkeypatch):
    path = tmp_path / "m.json"
    update_benchmark_manifest([_rec("mas_t1_r1")], manifest_path=str(path), canonical_task_ids={"t1"})
    # Make the stored pilot row look like the model about to run, so only the series differs.
    data = json.loads(path.read_text())
    data["runs"][0]["model"] = "fake"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(runner_mod, "MANIFEST_FILE", str(path))
    monkeypatch.setattr(runner_mod, "generate_stats_markdown_report", lambda *a, **k: "")
    ran = []

    def fake_workflow(*a, **k):
        ran.append(1)
        raise RuntimeError("stop")

    monkeypatch.setattr(runner_mod, "MASWorkflow", fake_workflow)
    tasks = tmp_path / "tasks.json"
    tasks.write_text('[{"task_id": "t1", "name": "T", "description": "d", "category": "Work"}]')
    runner_mod.EvaluationRunner(results_path=str(tmp_path / "r.csv")).run_benchmark(
        task_count=1, model="fake", use_fake=True, systems=["mas"], resume=True, tasks_file=str(tasks))
    assert ran == [1]


def test_dashboard_official_tier_only_shows_active_series(tmp_path):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
    import make_dashboard as md

    pilot = dict(_rec("mas_t1_r1"), official=True)
    new = dict(_rec("mas_t1_r1_attempt2", series="v2"), official=True)
    (tmp_path / "m.json").write_text(json.dumps({"runs": [pilot, new]}))
    d = md.build_data(str(tmp_path / "m.json"), str(tmp_path / "none.db"), series="v2")
    assert d["official"]["count"] == 1
    assert d["official"]["other_series_count"] == 1 and d["official"]["other_series_official"] == ["v1"]
