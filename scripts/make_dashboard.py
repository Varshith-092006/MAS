#!/usr/bin/env python3
"""Builds a self-contained HTML results dashboard from recorded data only.

Data sources (nothing is estimated or hardcoded):
  * eval/benchmark_manifest.json : benchmark run records written by eval/runner.py
  * mas.db (model_calls, runs)   : provider-reported token usage and latency per LLM call
  * eval/published_references.py : the iCoder paper's published numbers (indicative only)

Three strictly separated tiers:
  OFFICIAL     official rows, provider == gemini, live (AGENTS.md: one pinned model/provider)
  EXPLORATORY  older live calls recorded in mas.db (OpenRouter free models, legacy MAS
               versions). Real data, shown for agent-cost profiling only, never as results.
  SIMULATION   FakeLLM rows. Excluded everywhere (AGENTS.md rule 6).

Usage:
  python scripts/make_dashboard.py [--manifest eval/benchmark_manifest.json] [--db mas.db]
                                   [--out reports/dashboard.html]
"""

import argparse
import html
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from eval.published_references import PUBLISHED_REFERENCES  # noqa: E402
from eval.stats import bootstrap_ci, mean, wilcoxon_signed_rank_test  # noqa: E402

SYSTEMS = [("mas", "MAS (ours)"), ("chatdev", "ChatDev"), ("single", "Single-agent")]
SIM_MARKERS = ("SIMULATION_ONLY", "SIMULATED")
OK_STATUSES = ("COMPLETED", "COMPLETED_QUALITY_GATE")


# ----------------------------------------------------------------------------- selection
def is_simulation(r: Dict[str, Any]) -> bool:
    return (
        r.get("status") in SIM_MARKERS
        or r.get("execution_mode") in SIM_MARKERS
        or r.get("token_provenance") in SIM_MARKERS
        or str(r.get("model", "")).lower() == "fake"
    )


def is_official(r: Dict[str, Any]) -> bool:
    off = r.get("official")
    return (
        not is_simulation(r)
        and (off is True or str(off).lower() == "true")
        and str(r.get("provider", "")).lower() == "gemini"
    )


def _f(v) -> Optional[float]:
    try:
        return None if v is None or v == "" else float(v)
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------------------- official tier
def system_summary(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not runs:
        return {"n": 0}
    # Honest counting: an official run without a quality score counts as Quality 0.
    q = [(_f(r.get("quality")) or 0.0) for r in runs]
    def m(key):
        vals = [_f(r.get(key)) for r in runs if _f(r.get(key)) is not None]
        return round(mean(vals), 4) if vals else None
    tokens = [_f(r.get("tokens")) or 0.0 for r in runs]
    ci = bootstrap_ci(q) if len(q) > 1 else (q[0], q[0])
    mq = mean(q)
    mt = mean(tokens)
    return {
        "n": len(runs),
        "quality": round(mq, 4),
        "quality_ci": [round(ci[0], 4), round(ci[1], 4)],
        "completeness": m("completeness"),
        "executability": m("executability"),
        "consistency": m("consistency"),
        "tokens": round(mt, 1),
        "llm_calls": m("llm_calls"),
        "wall_clock_seconds": m("wall_clock_seconds"),
        "loc": m("loc"),
        "cost": round(sum(_f(r.get("cost")) or 0.0 for r in runs), 6),
        "quality_per_1k_tokens": round(mq / (mt / 1000), 4) if mt else None,
        "success_rate": round(sum(1 for r in runs if r.get("status") in OK_STATUSES) / len(runs), 4),
    }


def agent_totals(runs: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for r in runs:
        for agent, v in (r.get("agent_breakdown") or {}).items():
            a = out.setdefault(agent, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "latency_ms": 0})
            for k in a:
                a[k] += v.get(k, 0) or 0
    return out


def pct(new, old):
    if new is None or old in (None, 0):
        return None
    return round((new - old) / abs(old) * 100, 2)


def paired_test(a_runs, b_runs) -> Dict[str, Any]:
    a = {(r.get("task_id"), r.get("repeat_no")): (_f(r.get("quality")) or 0.0) for r in a_runs}
    b = {(r.get("task_id"), r.get("repeat_no")): (_f(r.get("quality")) or 0.0) for r in b_runs}
    keys = sorted(set(a) & set(b), key=str)
    if len(keys) < 2:
        return {"pairs": len(keys), "p_value": None}
    return {"pairs": len(keys), "p_value": wilcoxon_signed_rank_test([a[k] for k in keys], [b[k] for k in keys])}


def build_official(manifest_runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    official = [r for r in manifest_runs if is_official(r)]
    a0 = [r for r in official if (r.get("ablation") or "A0") == "A0"]
    by_sys = {s: [r for r in a0 if r.get("system") == s] for s, _ in SYSTEMS}
    summ = {s: system_summary(v) for s, v in by_sys.items()}
    comparisons = {}
    for base in ("chatdev", "single"):
        if summ["mas"].get("n") and summ[base].get("n"):
            comparisons[base] = {
                "quality_change_pct": pct(summ["mas"]["quality"], summ[base]["quality"]),
                "token_change_pct": pct(summ["mas"]["tokens"], summ[base]["tokens"]),
                "calls_change_pct": pct(summ["mas"]["llm_calls"], summ[base]["llm_calls"]),
                **paired_test(by_sys["mas"], by_sys[base]),
            }
    ablations = {}
    for ab in ("A0", "A1", "A2", "A3", "A4"):
        rs = [r for r in official if r.get("system") == "mas" and (r.get("ablation") or "A0") == ab]
        if rs:
            ablations[ab] = system_summary(rs)
    models = sorted({str(r.get("model")) for r in official})
    return {
        "count": len(official),
        "models": models,
        "summary": summ,
        "comparisons": comparisons,
        "agents": {s: agent_totals(v) for s, v in by_sys.items()},
        "ablations": ablations,
        "runs": [
            {k: r.get(k) for k in ("run_id", "task_id", "system", "ablation", "status", "quality", "tokens", "llm_calls", "wall_clock_seconds")}
            for r in sorted(official, key=lambda x: str(x.get("timestamp_utc", "")))
        ],
    }


# ----------------------------------------------------------------------------- exploratory tier
def build_exploratory(db_path: str) -> Dict[str, Any]:
    if not os.path.exists(db_path):
        return {"available": False}
    con = sqlite3.connect(db_path)
    try:
        q = lambda sql, *a: con.execute(sql, a).fetchall()  # noqa: E731
        live = "lower(c.model) != 'fake' AND c.agent NOT IN ('test_agent')"
        agents = q(f"""
            SELECT c.agent, COUNT(*), SUM(c.input_tokens), SUM(c.output_tokens), SUM(c.total_tokens), AVG(c.latency_ms)
            FROM model_calls c WHERE {live} GROUP BY c.agent ORDER BY SUM(c.total_tokens) DESC""")
        models = q(f"SELECT c.model, COUNT(*) FROM model_calls c WHERE {live} GROUP BY c.model ORDER BY 2 DESC")
        per_run = q(f"""
            SELECT r.system, c.run_id, COUNT(*), SUM(c.total_tokens), r.status
            FROM model_calls c JOIN runs r ON r.run_id = c.run_id
            WHERE {live} GROUP BY c.run_id""")
        statuses = q("""
            SELECT system, status, COUNT(*) FROM runs
            WHERE execution_mode NOT IN ('SIMULATED') AND lower(model) != 'fake' AND status != 'SIMULATION_ONLY'
            GROUP BY system, status ORDER BY system, 3 DESC""")
        history = q("""
            SELECT run_id, system, model, status, total_tokens, started_at, finished_at FROM runs
            WHERE execution_mode NOT IN ('SIMULATED') AND lower(model) != 'fake' AND status != 'SIMULATION_ONLY'
            ORDER BY started_at DESC LIMIT 40""")
    finally:
        con.close()

    sys_stats: Dict[str, Dict[str, Any]] = {}
    for system, _rid, calls, toks, status in per_run:
        s = sys_stats.setdefault(system, {"runs": 0, "calls": 0, "tokens": 0, "completed_runs": 0, "completed_calls": 0, "completed_tokens": 0})
        s["runs"] += 1
        s["calls"] += calls
        s["tokens"] += toks or 0
        if status in OK_STATUSES:
            s["completed_runs"] += 1
            s["completed_calls"] += calls
            s["completed_tokens"] += toks or 0

    def dur(a, b):
        try:
            return round((datetime.fromisoformat(str(b)) - datetime.fromisoformat(str(a))).total_seconds(), 1)
        except Exception:
            return None

    return {
        "available": True,
        "agents": [
            {"agent": a, "calls": c, "input_tokens": i or 0, "output_tokens": o or 0, "total_tokens": t or 0,
             "avg_latency_ms": round(lat or 0)} for a, c, i, o, t, lat in agents
        ],
        "models": [{"model": m, "calls": c} for m, c in models],
        "systems": sys_stats,
        "statuses": [{"system": s, "status": st, "count": c} for s, st, c in statuses],
        "history": [
            {"run_id": rid, "system": s, "model": m, "status": st, "tokens": tk, "started_at": str(sa)[:19], "duration_s": dur(sa, fa)}
            for rid, s, m, st, tk, sa, fa in history
        ],
    }


# ----------------------------------------------------------------------------- html
def build_data(manifest_path: str, db_path: str) -> Dict[str, Any]:
    runs: List[Dict[str, Any]] = []
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as fh:
            runs = json.load(fh).get("runs", [])
    return {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "sources": {"manifest": os.path.relpath(manifest_path, ROOT), "db": os.path.relpath(db_path, ROOT)},
        "simulation_rows_excluded": sum(1 for r in runs if is_simulation(r)),
        "official": build_official(runs),
        "exploratory": build_exploratory(db_path),
        "published": PUBLISHED_REFERENCES,
        "systems": dict(SYSTEMS),
    }


def render_html(data: Dict[str, Any]) -> str:
    payload = json.dumps(data, default=str).replace("</", "<\\/")
    with open(os.path.join(ROOT, "scripts", "dashboard_template.html"), "r", encoding="utf-8") as fh:
        tpl = fh.read()
    return tpl.replace("/*__DATA__*/null", payload).replace("__GENERATED__", html.escape(data["generated_utc"]))


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", default=os.path.join(ROOT, "eval", "benchmark_manifest.json"))
    ap.add_argument("--db", default=os.path.join(ROOT, "mas.db"))
    ap.add_argument("--out", default=os.path.join(ROOT, "reports", "dashboard.html"))
    args = ap.parse_args()

    data = build_data(args.manifest, args.db)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(render_html(data))
    with open(os.path.splitext(args.out)[0] + "_data.json", "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)

    off = data["official"]
    print(f"[DASHBOARD] Official runs (gemini, live): {off['count']}" + ("" if off["count"] else "  -> tables show NOT RUN"))
    ex = data["exploratory"]
    if ex.get("available"):
        print(f"[DASHBOARD] Exploratory live LLM calls profiled: {sum(a['calls'] for a in ex['agents'])} (labelled EXPLORATORY)")
    print(f"[DASHBOARD] Simulation rows excluded: {data['simulation_rows_excluded']}")
    print(f"[DASHBOARD] Wrote {args.out}")


if __name__ == "__main__":
    main()
