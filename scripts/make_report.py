#!/usr/bin/env python3
"""Unified reporting script producing Tables 1-6 (Markdown, LaTeX, CSV) and figures."""

import argparse
import csv
import json
import math
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

# Try importing stats utilities from repository
try:
    from eval.stats import bootstrap_ci, cohens_d, mean, std, wilcoxon_signed_rank_test
except ImportError:
    import numpy as np

    def mean(data: List[float]) -> float:
        return float(np.mean(data)) if data else 0.0

    def std(data: List[float]) -> float:
        return float(np.std(data, ddof=1)) if len(data) > 1 else 0.0

    def bootstrap_ci(data: List[float], n_resamples: int = 10000, confidence: float = 0.95, seed: int = 42) -> Tuple[float, float]:
        if not data:
            return (0.0, 0.0)
        if len(data) == 1:
            return (round(float(data[0]), 4), round(float(data[0]), 4))
        rng = np.random.default_rng(seed)
        arr = np.array(data, dtype=float)
        boot_samples = rng.choice(arr, size=(n_resamples, len(arr)), replace=True)
        boot_means = np.mean(boot_samples, axis=1)
        alpha = (1.0 - confidence) / 2.0
        return (round(float(np.percentile(boot_means, alpha * 100)), 4), round(float(np.percentile(boot_means, (1.0 - alpha) * 100)), 4))

    def wilcoxon_signed_rank_test(a: List[float], b: List[float]) -> float:
        try:
            from scipy import stats
            res = stats.wilcoxon(a, b, alternative="two-sided")
            return round(float(res.pvalue), 5)
        except Exception:
            return 1.0

    def cohens_d(a: List[float], b: List[float]) -> float:
        if len(a) != len(b) or len(a) < 2:
            return 0.0
        diffs = np.array(a) - np.array(b)
        s = np.std(diffs, ddof=1)
        return float(np.mean(diffs) / s) if s != 0 else 0.0

# Try importing published references
try:
    from eval.published_references import PUBLISHED_REFERENCES
except ImportError:
    PUBLISHED_REFERENCES = {
        "gpt-3.5-turbo": {
            "model_condition": "gpt-3.5-turbo",
            "tasks_evaluated": 100,
            "chatdev_quality": 0.590626,
            "icoder_quality": 0.690192,
            "chatdev_completeness": 0.902194,
            "icoder_completeness": 0.952062,
            "chatdev_executability": 0.81,
            "icoder_executability": 0.88,
            "chatdev_consistency": 0.808389,
            "icoder_consistency": 0.823800,
            "chatdev_tokens_per_task": 22327.02,
            "icoder_tokens_per_task": 411144.62,
            "chatdev_duration_seconds": 439.59,
            "icoder_duration_seconds": 2700.43,
            "chatdev_loc": 113.93,
            "icoder_loc": 168.92,
        },
        "gpt-4o": {
            "model_condition": "gpt-4o",
            "tasks_evaluated": 20,
            "chatdev_quality": 0.654990,
            "icoder_quality": 0.792398,
            "chatdev_completeness": 1.0,
            "icoder_completeness": 0.995992,
            "chatdev_executability": 0.80,
            "icoder_executability": 0.95,
            "chatdev_consistency": 0.818738,
            "icoder_consistency": 0.837460,
            "chatdev_tokens_per_task": 30416.6,
            "icoder_tokens_per_task": 104883.2,
            "chatdev_duration_seconds": 1058.7,
            "icoder_duration_seconds": 1620.05,
            "chatdev_loc": 125.95,
            "icoder_loc": 216.15,
        },
    }

CATEGORIES = ["Education", "Work", "Life", "Games", "Creation"]

CATEGORY_PREFIX_MAP = {
    "educ": "Education",
    "work": "Work",
    "life": "Life",
    "game": "Games",
    "crea": "Creation",
}


def get_task_category(task_id: str) -> str:
    """Infers category from task_id or category map."""
    tid = (task_id or "").lower()
    for pfx, cat in CATEGORY_PREFIX_MAP.items():
        if f"_{pfx}_" in tid or tid.startswith(f"srdd_{pfx}"):
            return cat
    return "Other"


def load_runs(csv_path: Optional[str] = None, manifest_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Loads benchmark runs from CSV or manifest, strictly ignoring simulation runs."""
    runs: List[Dict[str, Any]] = []

    # 1. Try reading CSV
    if csv_path and os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                runs.append(dict(row))
        return runs

    # 2. Fallback to manifest
    m_path = manifest_path or "eval/benchmark_manifest.json"
    if os.path.exists(m_path):
        try:
            with open(m_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
            runs = manifest_data.get("runs", [])
        except Exception:
            pass

    return runs


def is_official_live_run(r: Dict[str, Any]) -> bool:
    """Strictly checks if a row is an official, non-simulated benchmark execution."""
    if r.get("status") == "SIMULATION_ONLY":
        return False
    if r.get("execution_mode") in ("SIMULATED", "SIMULATION_ONLY"):
        return False
    if r.get("token_provenance") == "SIMULATION_ONLY":
        return False
    off = r.get("official")
    if off is None:
        return r.get("execution_mode") == "LIVE_API"
    return off is True or str(off).lower() == "true"


def escape_latex(s: str) -> str:
    """Escapes special LaTeX characters in text strings."""
    return str(s).replace("_", "\\_").replace("%", "\\%").replace("&", "\\&").replace("$", "\\$")


def format_ci(val_mean: float, ci: Tuple[float, float]) -> str:
    return f"{val_mean:.4f} [{ci[0]:.4f}, {ci[1]:.4f}]"


def generate_table_1_markdown() -> str:
    """Table 1: Published Baselines from Literature (Indicative Only)."""
    p35 = PUBLISHED_REFERENCES["gpt-3.5-turbo"]
    p4o = PUBLISHED_REFERENCES["gpt-4o"]

    md = """### Table 1: Indicative Published Baselines from Literature (You et al., 2026)

> [!WARNING]
> Indicative only: The numbers below are published literature references from the iCoder paper (Information and Software Technology 198 (2026) 108224) evaluated on different models (commercial GPT-3.5-Turbo and GPT-4o) and task splits. They are NOT local experimental results and must never be claimed as beaten locally.

| Model Condition | System | Tasks | Completeness | Executability | Consistency | Quality | Tokens / Task | Time (s) | LOC |
|---|---|---|---|---|---|---|---|---|---|
| GPT-3.5 Turbo | ChatDev | 100 | 0.9022 | 0.8100 | 0.8084 | 0.5906 | 22,327 | 439.6 | 113.9 |
| GPT-3.5 Turbo | iCoder | 100 | 0.9521 | 0.8800 | 0.8238 | 0.6902 | 411,145 | 2,700.4 | 168.9 |
| GPT-4o | ChatDev | 20 | 1.0000 | 0.8000 | 0.8187 | 0.6550 | 30,417 | 1,058.7 | 126.0 |
| GPT-4o | iCoder | 20 | 0.9960 | 0.9500 | 0.8375 | 0.7924 | 104,883 | 1,620.1 | 216.2 |
"""
    return md


def generate_table_2_markdown(mas_runs: List[Dict[str, Any]], cd_runs: List[Dict[str, Any]]) -> str:
    """Table 2: Primary Benchmark Comparison (MAS vs ChatDev on Pinned Model)."""
    if not mas_runs or not cd_runs:
        return """### Table 2: Primary Benchmark Comparison on Pinned Model

| System | N | Completeness (95% CI) | Executability (95% CI) | Consistency (95% CI) | Quality (95% CI) | Wilcoxon p-value | Cohen's d |
|---|---|---|---|---|---|---|---|
| **MAS (Ours)** | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| **ChatDev** | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
"""

    def parse_float(r, k, default=0.0):
        try:
            v = r.get(k)
            return float(v) if v not in (None, "") else default
        except Exception:
            return default

    # Extract metrics, setting Quality to 0.0 for failed runs
    def get_metrics(runs):
        comps, execs, consts, quals = [], [], [], []
        for r in runs:
            st = r.get("status")
            c = parse_float(r, "completeness", 0.0)
            e = parse_float(r, "executability", 0.0)
            s = parse_float(r, "consistency", 0.0)
            q = (c * e * s) if st in ("COMPLETED", "COMPLETED_QUALITY_GATE") else 0.0
            comps.append(c)
            execs.append(e)
            consts.append(s)
            quals.append(q)
        return comps, execs, consts, quals

    m_c, m_e, m_s, m_q = get_metrics(mas_runs)
    c_c, c_e, c_s, c_q = get_metrics(cd_runs)

    m_c_m, m_c_ci = mean(m_c), bootstrap_ci(m_c)
    m_e_m, m_e_ci = mean(m_e), bootstrap_ci(m_e)
    m_s_m, m_s_ci = mean(m_s), bootstrap_ci(m_s)
    m_q_m, m_q_ci = mean(m_q), bootstrap_ci(m_q)

    c_c_m, c_c_ci = mean(c_c), bootstrap_ci(c_c)
    c_e_m, c_e_ci = mean(c_e), bootstrap_ci(c_e)
    c_s_m, c_s_ci = mean(c_s), bootstrap_ci(c_s)
    c_q_m, c_q_ci = mean(c_q), bootstrap_ci(c_q)

    # Paired stats across task_ids
    paired_mas_q, paired_cd_q = [], []
    mas_by_task = {r.get("task_id"): r for r in mas_runs}
    cd_by_task = {r.get("task_id"): r for r in cd_runs}
    for tid, mr in mas_by_task.items():
        if tid in cd_by_task:
            cr = cd_by_task[tid]
            mq = parse_float(mr, "quality", 0.0) if mr.get("status") in ("COMPLETED", "COMPLETED_QUALITY_GATE") else 0.0
            cq = parse_float(cr, "quality", 0.0) if cr.get("status") in ("COMPLETED", "COMPLETED_QUALITY_GATE") else 0.0
            paired_mas_q.append(mq)
            paired_cd_q.append(cq)

    wilc_p = wilcoxon_signed_rank_test(paired_mas_q, paired_cd_q) if paired_mas_q else 1.0
    d_val = cohens_d(paired_mas_q, paired_cd_q) if paired_mas_q else 0.0

    md = f"""### Table 2: Primary Benchmark Comparison on Pinned Model

| System | N | Completeness (95% CI) | Executability (95% CI) | Consistency (95% CI) | Quality (95% CI) | Wilcoxon p-value | Cohen's d |
|---|---|---|---|---|---|---|---|
| **MAS (Ours)** | {len(mas_runs)} | {format_ci(m_c_m, m_c_ci)} | {format_ci(m_e_m, m_e_ci)} | {format_ci(m_s_m, m_s_ci)} | {format_ci(m_q_m, m_q_ci)} | {wilc_p:.5f} | {d_val:.4f} |
| **ChatDev** | {len(cd_runs)} | {format_ci(c_c_m, c_c_ci)} | {format_ci(c_e_m, c_e_ci)} | {format_ci(c_s_m, c_s_ci)} | {format_ci(c_q_m, c_q_ci)} | — | — |
"""
    return md


def generate_table_3_markdown(mas_runs: List[Dict[str, Any]], cd_runs: List[Dict[str, Any]]) -> str:
    """Table 3: Efficiency & Resource Consumption."""
    if not mas_runs or not cd_runs:
        return """### Table 3: Efficiency and Computational Overhead

| System | Tokens / Task | Quality / 1k Tokens | Est. Cost ($) | LLM Calls | Wall-Clock Time (s) | Lines of Code (LOC) |
|---|---|---|---|---|---|---|
| **MAS (Ours)** | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| **ChatDev** | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
"""

    def parse_f(r, k):
        try:
            return float(r.get(k, 0) or 0)
        except Exception:
            return 0.0

    m_tok = mean([parse_f(r, "tokens") for r in mas_runs])
    m_cost = mean([parse_f(r, "cost") for r in mas_runs])
    m_calls = mean([parse_f(r, "llm_calls") for r in mas_runs])
    m_time = mean([parse_f(r, "wall_clock_seconds") for r in mas_runs])
    m_loc = mean([parse_f(r, "loc") for r in mas_runs])
    m_q = mean([parse_f(r, "quality") if r.get("status") in ("COMPLETED", "COMPLETED_QUALITY_GATE") else 0.0 for r in mas_runs])
    m_q1k = round(m_q / (m_tok / 1000.0), 4) if m_tok > 0 else 0.0

    c_tok = mean([parse_f(r, "tokens") for r in cd_runs])
    c_cost = mean([parse_f(r, "cost") for r in cd_runs])
    c_calls = mean([parse_f(r, "llm_calls") for r in cd_runs])
    c_time = mean([parse_f(r, "wall_clock_seconds") for r in cd_runs])
    c_loc = mean([parse_f(r, "loc") for r in cd_runs])
    c_q = mean([parse_f(r, "quality") if r.get("status") in ("COMPLETED", "COMPLETED_QUALITY_GATE") else 0.0 for r in cd_runs])
    c_q1k = round(c_q / (c_tok / 1000.0), 4) if c_tok > 0 else 0.0

    md = f"""### Table 3: Efficiency and Computational Overhead

| System | Tokens / Task | Quality / 1k Tokens | Est. Cost ($) | LLM Calls | Wall-Clock Time (s) | Lines of Code (LOC) |
|---|---|---|---|---|---|---|
| **MAS (Ours)** | {m_tok:,.1f} | {m_q1k:.4f} | ${m_cost:.4f} | {m_calls:.1f} | {m_time:.1f}s | {m_loc:.1f} |
| **ChatDev** | {c_tok:,.1f} | {c_q1k:.4f} | ${c_cost:.4f} | {c_calls:.1f} | {c_time:.1f}s | {c_loc:.1f} |
"""
    return md


def generate_table_4_markdown(mas_runs: List[Dict[str, Any]], cd_runs: List[Dict[str, Any]]) -> str:
    """Table 4: Per-Category Quality Breakdown."""
    if not mas_runs or not cd_runs:
        rows = [f"| {cat} | NOT RUN | NOT RUN | NOT RUN | NOT RUN |" for cat in CATEGORIES]
        return f"""### Table 4: Per-Category Quality Breakdown

| Category | Tasks | MAS Quality | ChatDev Quality | Delta (MAS - CD) |
|---|---|---|---|---|
{chr(10).join(rows)}
"""

    def parse_f(r, k):
        try:
            return float(r.get(k, 0) or 0)
        except Exception:
            return 0.0

    md_lines = [
        "### Table 4: Per-Category Quality Breakdown\n",
        "| Category | Tasks | MAS Quality | ChatDev Quality | Delta (MAS - CD) |",
        "|---|---|---|---|---|",
    ]

    for cat in CATEGORIES:
        m_cat = [
            parse_f(r, "quality") if r.get("status") in ("COMPLETED", "COMPLETED_QUALITY_GATE") else 0.0
            for r in mas_runs if get_task_category(r.get("task_id", "")) == cat
        ]
        c_cat = [
            parse_f(r, "quality") if r.get("status") in ("COMPLETED", "COMPLETED_QUALITY_GATE") else 0.0
            for r in cd_runs if get_task_category(r.get("task_id", "")) == cat
        ]
        n_tasks = max(len(m_cat), len(c_cat))
        if n_tasks == 0:
            md_lines.append(f"| {cat} | 0 | NOT RUN | NOT RUN | NOT RUN |")
        else:
            m_qm = mean(m_cat)
            c_qm = mean(c_cat)
            delta = m_qm - c_qm
            md_lines.append(f"| {cat} | {n_tasks} | {m_qm:.4f} | {c_qm:.4f} | {delta:+.4f} |")

    return "\n".join(md_lines) + "\n"


def generate_table_5_markdown(all_runs: List[Dict[str, Any]]) -> str:
    """Table 5: Ablation Matrix (A0 through A4)."""
    ablations = [
        ("A0", "Full MAS (Default Baseline)"),
        ("A1", "Always Architect (No Complexity Router)"),
        ("A2", "Full Repo Context (No AST Slicing)"),
        ("A3", "No Evidence Review (No AST/Ruff/Bandit Checks)"),
        ("A4", "Single Iteration (No Reflection Loop)"),
    ]

    def parse_f(r, k):
        try:
            return float(r.get(k, 0) or 0)
        except Exception:
            return 0.0

    mas_runs = [r for r in all_runs if r.get("system") == "mas" and is_official_live_run(r)]
    a0_runs = [r for r in mas_runs if r.get("ablation", "A0") in ("A0", "", None)]
    a0_q = mean([parse_f(r, "quality") if r.get("status") in ("COMPLETED", "COMPLETED_QUALITY_GATE") else 0.0 for r in a0_runs]) if a0_runs else None

    md_lines = [
        "### Table 5: Ablation Matrix (MAS Modular Architectural Components)\n",
        "| Condition | Description | Tasks | Mean Quality | Mean Tokens | LLM Calls | Delta Quality vs A0 |",
        "|---|---|---|---|---|---|---|",
    ]

    for code, desc in ablations:
        ab_runs = [r for r in mas_runs if r.get("ablation") == code or (code == "A0" and r.get("ablation") in ("A0", "", None))]
        if not ab_runs:
            md_lines.append(f"| **{code}** | {desc} | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |")
        else:
            q_m = mean([parse_f(r, "quality") if r.get("status") in ("COMPLETED", "COMPLETED_QUALITY_GATE") else 0.0 for r in ab_runs])
            tok_m = mean([parse_f(r, "tokens") for r in ab_runs])
            calls_m = mean([parse_f(r, "llm_calls") for r in ab_runs])
            delta_str = f"{(q_m - a0_q):+.4f}" if (a0_q is not None and code != "A0") else "Reference (0.0000)"
            md_lines.append(f"| **{code}** | {desc} | {len(ab_runs)} | {q_m:.4f} | {tok_m:,.0f} | {calls_m:.1f} | {delta_str} |")

    return "\n".join(md_lines) + "\n"


def generate_table_6_markdown(mas_runs: List[Dict[str, Any]], cd_runs: List[Dict[str, Any]]) -> str:
    """Table 6: Shared Test Pass Rate and Executability."""
    if not mas_runs or not cd_runs:
        return """### Table 6: Test Suite Pass Rates and Verification

| System | Shared Test Score | Executability Rate | Benchmark Success Rate |
|---|---|---|---|
| **MAS (Ours)** | NOT RUN | NOT RUN | NOT RUN |
| **ChatDev** | NOT RUN | NOT RUN | NOT RUN |
"""

    def parse_f(r, k):
        try:
            return float(r.get(k, 0) or 0)
        except Exception:
            return 0.0

    m_shared = mean([parse_f(r, "shared_test") for r in mas_runs if r.get("shared_test") is not None])
    m_exec = mean([parse_f(r, "executability") for r in mas_runs])
    m_succ = mean([1.0 if r.get("status") in ("COMPLETED", "COMPLETED_QUALITY_GATE") else 0.0 for r in mas_runs])

    c_shared = mean([parse_f(r, "shared_test") for r in cd_runs if r.get("shared_test") is not None])
    c_exec = mean([parse_f(r, "executability") for r in cd_runs])
    c_succ = mean([1.0 if r.get("status") in ("COMPLETED", "COMPLETED_QUALITY_GATE") else 0.0 for r in cd_runs])

    md = f"""### Table 6: Test Suite Pass Rates and Verification

| System | Shared Test Score | Executability Rate | Benchmark Success Rate |
|---|---|---|---|
| **MAS (Ours)** | {m_shared:.4f} | {m_exec*100:.1f}% | {m_succ*100:.1f}% |
| **ChatDev** | {c_shared:.4f} | {c_exec*100:.1f}% | {c_succ*100:.1f}% |
"""
    return md


def generate_latex_tables(all_runs: List[Dict[str, Any]]) -> str:
    """Produces clean, valid LaTeX tabular environments for Tables 1-6."""
    mas_runs = [r for r in all_runs if r.get("system") == "mas" and is_official_live_run(r)]
    cd_runs = [r for r in all_runs if r.get("system") == "chatdev" and is_official_live_run(r)]

    latex_sections = []

    # Table 1: Literature Reference
    latex_sections.append(r"""% Table 1: Literature Published Baselines
\begin{table}[htbp]
\centering
\caption{Indicative Published Baselines from Literature (You et al., 2026). Indicative only; evaluated on commercial models and not executed locally.}
\label{tab:published-baselines}
\small
\begin{tabular}{llrrrrrr}
\hline
\textbf{Model} & \textbf{System} & \textbf{Tasks} & \textbf{Completeness} & \textbf{Executability} & \textbf{Consistency} & \textbf{Quality} & \textbf{Tokens/Task} \\
\hline
GPT-3.5 Turbo & ChatDev & 100 & 0.9022 & 0.8100 & 0.8084 & 0.5906 & 22,327 \\
GPT-3.5 Turbo & iCoder & 100 & 0.9521 & 0.8800 & 0.8238 & 0.6902 & 411,145 \\
GPT-4o & ChatDev & 20 & 1.0000 & 0.8000 & 0.8187 & 0.6550 & 30,417 \\
GPT-4o & iCoder & 20 & 0.9960 & 0.9500 & 0.8375 & 0.7924 & 104,883 \\
\hline
\end{tabular}
\end{table}
""")

    # Table 2: Primary Benchmark
    if not mas_runs or not cd_runs:
        latex_sections.append(r"""% Table 2: Primary Benchmark Comparison
\begin{table}[htbp]
\centering
\caption{Primary Benchmark Comparison on Pinned Model}
\label{tab:primary-comparison}
\begin{tabular}{lrrrrrrr}
\hline
\textbf{System} & \textbf{N} & \textbf{Completeness} & \textbf{Executability} & \textbf{Consistency} & \textbf{Quality} & \textbf{Wilcoxon $p$} & \textbf{Cohen's $d$} \\
\hline
MAS (Ours) & NOT RUN & NOT RUN & NOT RUN & NOT RUN & NOT RUN & NOT RUN & NOT RUN \\
ChatDev & NOT RUN & NOT RUN & NOT RUN & NOT RUN & NOT RUN & NOT RUN & NOT RUN \\
\hline
\end{tabular}
\end{table}
""")
    else:
        # Fill in metrics
        def parse_f(r, k):
            try:
                return float(r.get(k, 0) or 0)
            except Exception:
                return 0.0

        mq = [parse_f(r, "quality") if r.get("status") in ("COMPLETED", "COMPLETED_QUALITY_GATE") else 0.0 for r in mas_runs]
        cq = [parse_f(r, "quality") if r.get("status") in ("COMPLETED", "COMPLETED_QUALITY_GATE") else 0.0 for r in cd_runs]
        mc = [parse_f(r, "completeness") for r in mas_runs]
        cc = [parse_f(r, "completeness") for r in cd_runs]
        me = [parse_f(r, "executability") for r in mas_runs]
        ce = [parse_f(r, "executability") for r in cd_runs]
        ms = [parse_f(r, "consistency") for r in mas_runs]
        cs = [parse_f(r, "consistency") for r in cd_runs]

        wilc_p = wilcoxon_signed_rank_test(mq, cq) if len(mq) == len(cq) else 1.0
        d_val = cohens_d(mq, cq) if len(mq) == len(cq) else 0.0

        latex_sections.append(f"""% Table 2: Primary Benchmark Comparison
\\begin{{table}}[htbp]
\\centering
\\caption{{Primary Benchmark Comparison on Pinned Model}}
\\label{{tab:primary-comparison}}
\\begin{{tabular}}{{lrrrrrrr}}
\\hline
\\textbf{{System}} & \\textbf{{N}} & \\textbf{{Completeness}} & \\textbf{{Executability}} & \\textbf{{Consistency}} & \\textbf{{Quality}} & \\textbf{{Wilcoxon $p$}} & \\textbf{{Cohen's $d$}} \\\\
\\hline
MAS (Ours) & {len(mas_runs)} & {mean(mc):.4f} & {mean(me):.4f} & {mean(ms):.4f} & {mean(mq):.4f} & {wilc_p:.5f} & {d_val:.4f} \\\\
ChatDev & {len(cd_runs)} & {mean(cc):.4f} & {mean(ce):.4f} & {mean(cs):.4f} & {mean(cq):.4f} & --- & --- \\\\
\\hline
\\end{{tabular}}
\\end{{table}}
""")

    # Table 3: Efficiency
    latex_sections.append(r"""% Table 3: Efficiency and Computational Overhead
\begin{table}[htbp]
\centering
\caption{Efficiency and Computational Overhead}
\label{tab:efficiency}
\begin{tabular}{lrrrrrr}
\hline
\textbf{System} & \textbf{Tokens/Task} & \textbf{Quality/1k Tok} & \textbf{Est. Cost (\$)} & \textbf{LLM Calls} & \textbf{Time (s)} & \textbf{LOC} \\
\hline
""")
    if not mas_runs or not cd_runs:
        latex_sections.append(r"""MAS (Ours) & NOT RUN & NOT RUN & NOT RUN & NOT RUN & NOT RUN & NOT RUN \\
ChatDev & NOT RUN & NOT RUN & NOT RUN & NOT RUN & NOT RUN & NOT RUN \\
\hline
\end{tabular}
\end{table}
""")
    else:
        def parse_f(r, k):
            try: return float(r.get(k, 0) or 0)
            except Exception: return 0.0
        mt = mean([parse_f(r, "tokens") for r in mas_runs])
        ct = mean([parse_f(r, "tokens") for r in cd_runs])
        mq = mean([parse_f(r, "quality") for r in mas_runs])
        cq = mean([parse_f(r, "quality") for r in cd_runs])
        latex_sections.append(f"""MAS (Ours) & {mt:,.0f} & {(mq/(mt/1000.0) if mt>0 else 0):.4f} & \\${mean([parse_f(r, 'cost') for r in mas_runs]):.4f} & {mean([parse_f(r, 'llm_calls') for r in mas_runs]):.1f} & {mean([parse_f(r, 'wall_clock_seconds') for r in mas_runs]):.1f}s & {mean([parse_f(r, 'loc') for r in mas_runs]):.1f} \\\\
ChatDev & {ct:,.0f} & {(cq/(ct/1000.0) if ct>0 else 0):.4f} & \\${mean([parse_f(r, 'cost') for r in cd_runs]):.4f} & {mean([parse_f(r, 'llm_calls') for r in cd_runs]):.1f} & {mean([parse_f(r, 'wall_clock_seconds') for r in cd_runs]):.1f}s & {mean([parse_f(r, 'loc') for r in cd_runs]):.1f} \\\\
\\hline
\\end{{tabular}}
\\end{{table}}
""")

    return "\n".join(latex_sections)


def generate_figures(mas_runs: List[Dict[str, Any]], cd_runs: List[Dict[str, Any]], output_dir: str = "reports/figures") -> None:
    """Generates boxplot and scatter figures if matplotlib is installed."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("[INFO] matplotlib is not installed. Skipping figure generation (install with: pip install '.[report]').")
        return

    if not mas_runs or not cd_runs:
        print("[INFO] Insufficient benchmark data for figure generation (N=0). Skipping figures.")
        return

    os.makedirs(output_dir, exist_ok=True)

    def parse_f(r, k):
        try:
            return float(r.get(k, 0) or 0)
        except Exception:
            return 0.0

    mq = [parse_f(r, "quality") if r.get("status") in ("COMPLETED", "COMPLETED_QUALITY_GATE") else 0.0 for r in mas_runs]
    cq = [parse_f(r, "quality") if r.get("status") in ("COMPLETED", "COMPLETED_QUALITY_GATE") else 0.0 for r in cd_runs]
    mt = [parse_f(r, "tokens") for r in mas_runs]
    ct = [parse_f(r, "tokens") for r in cd_runs]

    # Figure 1: Quality Boxplot
    plt.figure(figsize=(7, 5))
    plt.boxplot([mq, cq], labels=["MAS (Ours)", "ChatDev"])
    plt.title("Software Quality Distribution by Multi-Agent System")
    plt.ylabel("Quality Metric (Completeness x Executability x Consistency)")
    plt.grid(True, linestyle="--", alpha=0.6)
    box_path = os.path.join(output_dir, "quality_boxplot.png")
    plt.savefig(box_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"[FIGURE] Saved Quality boxplot to {box_path}")

    # Figure 2: Quality vs Tokens Scatter
    plt.figure(figsize=(8, 5))
    plt.scatter(mt, mq, color="#1f77b4", label="MAS", alpha=0.8, s=60)
    plt.scatter(ct, cq, color="#ff7f0e", label="ChatDev", alpha=0.8, s=60, marker="^")
    plt.xlabel("Total Provider Tokens Consumed")
    plt.ylabel("Quality Metric")
    plt.title("Quality vs. Token Consumption Overhead")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.6)
    scatter_path = os.path.join(output_dir, "quality_vs_tokens.png")
    plt.savefig(scatter_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"[FIGURE] Saved Quality vs Tokens scatter plot to {scatter_path}")


def main():
    # Windows consoles default to cp1252; force UTF-8 so non-ASCII table text never crashes or garbles.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="MAS Benchmark Report Generator (Tables 1-6 & LaTeX)")
    parser.add_argument("--results", type=str, default="results.csv", help="Path to results.csv")
    parser.add_argument("--manifest", type=str, default="eval/benchmark_manifest.json", help="Path to benchmark manifest JSON")
    parser.add_argument("--output-dir", type=str, default="reports", help="Output directory for reports and LaTeX tables")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    runs = load_runs(csv_path=args.results, manifest_path=args.manifest)

    mas_runs = [r for r in runs if r.get("system") == "mas" and is_official_live_run(r)]
    cd_runs = [r for r in runs if r.get("system") == "chatdev" and is_official_live_run(r)]

    # --- Provider / model consistency check ---
    # Collect all (provider, model) pairs from official live runs.
    provider_model_combos = set()
    all_official = mas_runs + cd_runs
    for r in all_official:
        p = (r.get("provider_type") or r.get("provider") or "").strip().lower() or None
        m = (r.get("model") or r.get("bench_model") or "").strip().lower() or None
        if p or m:
            provider_model_combos.add((p, m))

    # Build metadata header
    meta_lines = []
    if all_official:
        providers = {c[0] for c in provider_model_combos if c[0]}
        models = {c[1] for c in provider_model_combos if c[1]}
        meta_lines.append("**Benchmark metadata** (from run records):\n")
        meta_lines.append(f"- Provider type(s): {', '.join(sorted(str(p) for p in providers)) or '(not recorded)'}")
        meta_lines.append(f"- Model(s): {', '.join(sorted(str(m) for m in models)) or '(not recorded)'}")
        meta_lines.append(f"- Official MAS runs: {len(mas_runs)}, Official ChatDev runs: {len(cd_runs)}")
        meta_lines.append("")

        # Abort if multiple providers or models were mixed
        if len(providers) > 1:
            print(
                f"[ERROR] Cannot generate Table 2+: runs from MULTIPLE providers detected: "
                f"{sorted(str(p) for p in providers)}. "
                f"All runs in one report must use the same provider. Split them first."
            )
            sys.exit(1)
        if len(models) > 1:
            print(
                f"[ERROR] Cannot generate Table 2+: runs from MULTIPLE models detected: "
                f"{sorted(str(m) for m in models)}. "
                f"All runs in one report must use the same model. Split them first."
            )
            sys.exit(1)
    else:
        meta_lines.append("**Benchmark metadata**: No official live runs found — tables will show NOT RUN.\n")
    # ---

    # Generate Markdown Tables
    t1 = generate_table_1_markdown()
    t2 = generate_table_2_markdown(mas_runs, cd_runs)
    t3 = generate_table_3_markdown(mas_runs, cd_runs)
    t4 = generate_table_4_markdown(mas_runs, cd_runs)
    t5 = generate_table_5_markdown(runs)
    t6 = generate_table_6_markdown(mas_runs, cd_runs)

    metadata_block = "\n".join(meta_lines)
    full_md = f"""# MAS Empirical Evaluation Final Benchmark Report

Generated at: {os.path.basename(args.results)} / {os.path.basename(args.manifest)}

{metadata_block}

{t1}

{t2}

{t3}

{t4}

{t5}

{t6}
"""

    # Print to stdout
    print(full_md)

    # Write Markdown file
    md_out_path = os.path.join(args.output_dir, "benchmark_report.md")
    with open(md_out_path, "w", encoding="utf-8") as f:
        f.write(full_md)

    # Write LaTeX tables
    latex_content = generate_latex_tables(runs)
    tex_out_path = os.path.join(args.output_dir, "tables.tex")
    with open(tex_out_path, "w", encoding="utf-8") as f:
        f.write(latex_content)

    # Write CSV summary
    csv_summary_path = os.path.join(args.output_dir, "summary.csv")
    with open(csv_summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["system", "official_runs", "mean_quality", "mean_tokens", "mean_llm_calls", "mean_wall_clock_sec"])
        def pf(r, k):
            try: return float(r.get(k, 0) or 0)
            except Exception: return 0.0
        mq = mean([pf(r, "quality") if r.get("status") in ("COMPLETED", "COMPLETED_QUALITY_GATE") else 0.0 for r in mas_runs]) if mas_runs else 0.0
        mt = mean([pf(r, "tokens") for r in mas_runs]) if mas_runs else 0.0
        mc = mean([pf(r, "llm_calls") for r in mas_runs]) if mas_runs else 0.0
        mw = mean([pf(r, "wall_clock_seconds") for r in mas_runs]) if mas_runs else 0.0
        writer.writerow(["mas", len(mas_runs), f"{mq:.4f}", f"{mt:.1f}", f"{mc:.1f}", f"{mw:.1f}"])

        cq = mean([pf(r, "quality") if r.get("status") in ("COMPLETED", "COMPLETED_QUALITY_GATE") else 0.0 for r in cd_runs]) if cd_runs else 0.0
        ct = mean([pf(r, "tokens") for r in cd_runs]) if cd_runs else 0.0
        cc = mean([pf(r, "llm_calls") for r in cd_runs]) if cd_runs else 0.0
        cw = mean([pf(r, "wall_clock_seconds") for r in cd_runs]) if cd_runs else 0.0
        writer.writerow(["chatdev", len(cd_runs), f"{cq:.4f}", f"{ct:.1f}", f"{cc:.1f}", f"{cw:.1f}"])

    # Generate Figures
    generate_figures(mas_runs, cd_runs, output_dir=os.path.join(args.output_dir, "figures"))
    print(f"\n[REPORT] Saved benchmark report to {md_out_path}")
    print(f"[REPORT] Saved LaTeX tables to {tex_out_path}")
    print(f"[REPORT] Saved summary CSV to {csv_summary_path}")


if __name__ == "__main__":
    main()
