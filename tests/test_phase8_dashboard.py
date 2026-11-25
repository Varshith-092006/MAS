"""Phase 8 (DEC-041): dashboard tiers are strictly separated and never invent numbers.

The run rows below are synthetic TEST FIXTURES written to tmp_path only; they never touch
eval/benchmark_manifest.json or reports/.
"""

import json
import os
import sqlite3
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import make_dashboard as md  # noqa: E402


def _row(system, task, q, tokens, calls, provider="gemini", official=True, status="COMPLETED", **kw):
    r = {
        "run_id": f"{system}_{task}", "task_id": task, "system": system, "repeat_no": 1, "ablation": "A0",
        "provider": provider, "model": "bench-model", "official": official, "status": status,
        "execution_mode": "LIVE_API", "token_provenance": "PROVIDER_REPORTED", "quality": q,
        "completeness": 1.0, "executability": 1.0 if q else 0.0, "consistency": q, "tokens": tokens,
        "llm_calls": calls, "wall_clock_seconds": 10.0, "cost": 0.0,
        "agent_breakdown": {"developer": {"calls": 1, "input_tokens": 100, "output_tokens": 400, "total_tokens": 500, "latency_ms": 1000}},
    }
    r.update(kw)
    return r


def test_filters_exclude_simulation_and_non_gemini():
    assert md.is_official(_row("mas", "t1", 0.5, 1000, 3))
    assert not md.is_official(_row("mas", "t1", 0.5, 1000, 3, provider="openrouter"))
    assert not md.is_official(_row("mas", "t1", 0.5, 1000, 3, status="SIMULATION_ONLY"))
    assert not md.is_official(_row("mas", "t1", 0.5, 1000, 3, official=False))
    assert not md.is_official(_row("mas", "t1", 0.5, 1000, 3, model="fake"))


def test_empty_manifest_reports_nothing_official(tmp_path):
    (tmp_path / "m.json").write_text(json.dumps({"runs": [_row("mas", "t1", 0.9, 1, 1, provider="openrouter")]}))
    d = md.build_data(str(tmp_path / "m.json"), str(tmp_path / "missing.db"))
    assert d["official"]["count"] == 0
    assert d["official"]["summary"]["mas"] == {"n": 0}
    assert d["official"]["comparisons"] == {}
    assert d["exploratory"] == {"available": False}


def test_official_summary_and_comparisons(tmp_path):
    runs = [
        _row("mas", "t1", 0.6, 3000, 3), _row("mas", "t2", 0.8, 5000, 4),
        _row("chatdev", "t1", 0.5, 20000, 20), _row("chatdev", "t2", None, 25000, 22, status="FAILED"),
        _row("single", "t1", 0.4, 1500, 1), _row("single", "t2", 0.6, 1700, 1),
        _row("mas", "t3", 0.99, 10, 1, status="SIMULATION_ONLY"),
    ]
    (tmp_path / "m.json").write_text(json.dumps({"runs": runs}))
    d = md.build_data(str(tmp_path / "m.json"), str(tmp_path / "missing.db"))
    s = d["official"]["summary"]
    assert s["mas"]["n"] == 2 and s["mas"]["quality"] == 0.7
    assert s["chatdev"]["quality"] == 0.25  # failed official run counts as 0
    assert s["chatdev"]["success_rate"] == 0.5
    c = d["official"]["comparisons"]["chatdev"]
    assert c["quality_change_pct"] == 180.0
    assert c["pairs"] == 2
    assert d["official"]["comparisons"]["single"]["quality_change_pct"] == 40.0
    assert d["official"]["agents"]["mas"]["developer"]["calls"] == 2
    assert d["simulation_rows_excluded"] == 1


def test_exploratory_reads_model_calls_and_skips_fake(tmp_path):
    db = tmp_path / "x.db"
    con = sqlite3.connect(db)
    con.executescript("""
      CREATE TABLE runs (run_id TEXT, system TEXT, model TEXT, status TEXT, execution_mode TEXT,
                         total_tokens INT, started_at TEXT, finished_at TEXT);
      CREATE TABLE model_calls (run_id TEXT, agent TEXT, model TEXT, input_tokens INT, output_tokens INT,
                                total_tokens INT, latency_ms INT);
      INSERT INTO runs VALUES ('r1','mas','m1','COMPLETED','LIVE_API',300,'2026-01-01 00:00:00','2026-01-01 00:01:00');
      INSERT INTO runs VALUES ('r2','mas','fake','SIMULATION_ONLY','SIMULATED',50,'2026-01-01','2026-01-01');
      INSERT INTO model_calls VALUES ('r1','developer','m1',100,200,300,2000);
      INSERT INTO model_calls VALUES ('r2','developer','fake',10,40,50,5);
    """)
    con.commit(); con.close()
    ex = md.build_exploratory(str(db))
    assert ex["agents"] == [{"agent": "developer", "calls": 1, "input_tokens": 100, "output_tokens": 200, "total_tokens": 300, "avg_latency_ms": 2000}]
    assert ex["systems"]["mas"]["completed_runs"] == 1
    assert [h["run_id"] for h in ex["history"]] == ["r1"]
    assert ex["history"][0]["duration_s"] == 60.0
    # A benchmark (official-tier) run must never also appear in the exploratory tier.
    ex2 = md.build_exploratory(str(db), exclude_run_ids={"r1"})
    assert ex2["agents"] == [] and ex2["history"] == [] and ex2["systems"] == {}


def test_cli_writes_self_contained_html(tmp_path):
    (tmp_path / "m.json").write_text(json.dumps({"runs": []}))
    out = tmp_path / "dash.html"
    res = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "make_dashboard.py"), "--manifest", str(tmp_path / "m.json"),
         "--db", str(tmp_path / "none.db"), "--out", str(out)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert res.returncode == 0, res.stderr
    html = out.read_text(encoding="utf-8")
    assert "/*__DATA__*/null" not in html and '"official"' in html
    assert "<script src=" not in html  # no external dependencies
    assert (tmp_path / "dash_data.json").exists()
