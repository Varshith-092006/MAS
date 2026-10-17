"""Generates structured CSV and markdown reports from evaluation runs."""

import csv
import json
import os
from typing import Any, Dict, List

from eval.stats import compare_systems, summarize_metric_distribution


def export_results_csv(records: List[Dict[str, Any]], output_path: str = "results.csv"):
    """Exports evaluated benchmark runs to standardized results.csv."""
    if not records:
        return

    fieldnames = [
        "run_id", "task_id", "system", "model", "repeat_no", "ablation",
        "quality", "quality_per_1k_tokens", "completeness", "executability",
        "consistency", "shared_test", "ruff", "bandit", "radon",
        "tokens", "cost", "pytest_pass_rate", "coverage", "status",
    ]

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            writer.writerow(r)


def generate_stats_markdown_report(
    mas_runs: List[Dict[str, Any]],
    chatdev_runs: List[Dict[str, Any]],
    output_path: str = "eval/stats_report.md",
) -> str:
    """Produces the formatted experimental statistics markdown report."""
    # Group task-level averages
    def get_task_metric_means(runs: List[Dict[str, Any]], metric_key: str) -> Dict[str, float]:
        task_vals: Dict[str, List[float]] = {}
        for r in runs:
            tid = r.get("task_id", "unknown")
            raw_v = r.get(metric_key)
            val = float(raw_v) if raw_v is not None else 0.0
            task_vals.setdefault(tid, []).append(val)
        return {tid: sum(vals) / len(vals) for tid, vals in task_vals.items()}

    mas_q = get_task_metric_means(mas_runs, "quality")
    cd_q = get_task_metric_means(chatdev_runs, "quality")
    mas_q_per_1k = get_task_metric_means(mas_runs, "quality_per_1k_tokens")
    cd_q_per_1k = get_task_metric_means(chatdev_runs, "quality_per_1k_tokens")

    common_tasks = sorted(list(set(mas_q.keys()) & set(cd_q.keys())))

    mas_q_list = [mas_q[t] for t in common_tasks]
    cd_q_list = [cd_q[t] for t in common_tasks]
    mas_q1k_list = [mas_q_per_1k[t] for t in common_tasks]
    cd_q1k_list = [cd_q_per_1k[t] for t in common_tasks]

    q_stat = compare_systems(mas_q_list, cd_q_list, metric_name="Quality")
    q1k_stat = compare_systems(mas_q1k_list, cd_q1k_list, metric_name="Quality per 1,000 tokens")

    md = f"""# MAS Empirical Evaluation Statistics Report

## Primary Experimental Metrics (Paired Permutation Test, N={len(common_tasks)} Tasks)

| Metric | MAS (Mean ± SD) | ChatDev (Mean ± SD) | Difference | % Gain | Cohen's d | p-value (α=0.05) | Sig? |
|---|---|---|---|---|---|---|---|
| **Quality** | {q_stat['mas_mean']:.3f} ± {q_stat['mas_std']:.3f} | {q_stat['chatdev_mean']:.3f} ± {q_stat['chatdev_std']:.3f} | {q_stat['difference']:+.3f} | {q_stat['percentage_gain']:+.1f}% | {q_stat['effect_size_cohens_d']:.3f} | {q_stat['p_value']:.4f} | {'YES' if q_stat['statistically_significant'] else 'NO'} |
| **Quality / 1k Tokens** | {q1k_stat['mas_mean']:.3f} ± {q1k_stat['mas_std']:.3f} | {q1k_stat['chatdev_mean']:.3f} ± {q1k_stat['chatdev_std']:.3f} | {q1k_stat['difference']:+.3f} | {q1k_stat['percentage_gain']:+.1f}% | {q1k_stat['effect_size_cohens_d']:.3f} | {q1k_stat['p_value']:.4f} | {'YES' if q1k_stat['statistically_significant'] else 'NO'} |

> **Note on Research Comparison**:
> MAS is compared directly against ChatDev under identical conditions and logging proxy token measurements.
> The comparison with iCoder is indirect and referenced only through published values in You et al. (2026).
"""

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md)

    return md
