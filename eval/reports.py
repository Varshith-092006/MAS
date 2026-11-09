"""Generates structured CSV and markdown reports from evaluation runs."""

import csv
import json
import os
from typing import Any, Dict, List

from eval.stats import calculate_success_rate, compare_systems, summarize_metric_distribution


def export_results_csv(records: List[Dict[str, Any]], output_path: str = "results.csv"):
    """Exports evaluated benchmark runs to standardized results.csv."""
    if not records:
        return

    fieldnames = [
        "run_id", "task_id", "system", "provider", "model", "actual_model",
        "repeat_no", "ablation", "official", "retry_reason",
        "quality", "quality_per_1k_tokens", "completeness", "executability",
        "consistency", "consistency_method", "shared_test", "ruff", "bandit", "radon",
        "tokens", "cost", "llm_calls", "pytest_pass_rate", "coverage", "status", "failure_classification",
    ]

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            row = dict(r)
            if "official" in row and isinstance(row["official"], bool):
                row["official"] = str(row["official"]).lower()
            writer.writerow(row)


def generate_stats_markdown_report(
    mas_runs: List[Dict[str, Any]],
    chatdev_runs: List[Dict[str, Any]],
    output_path: str = "eval/stats_report.md",
) -> str:
    """Produces the formatted experimental statistics markdown report using official rows only."""
    # Filter strictly to official runs, excluding simulation runs
    mas_official = [
        r for r in mas_runs
        if (r.get("official") is True or str(r.get("official")).lower() == "true")
        and r.get("status") != "SIMULATION_ONLY"
    ]
    cd_official = [
        r for r in chatdev_runs
        if (r.get("official") is True or str(r.get("official")).lower() == "true")
        and r.get("status") != "SIMULATION_ONLY"
    ]

    # Fallback to non-simulation completed runs if official flag not yet assigned
    if not mas_official and not cd_official:
        mas_official = [
            r for r in mas_runs
            if r.get("status") != "SIMULATION_ONLY" and r.get("execution_mode") == "LIVE_API"
        ]
        cd_official = [
            r for r in chatdev_runs
            if r.get("status") != "SIMULATION_ONLY" and r.get("execution_mode") == "LIVE_API"
        ]

    if not mas_official or not cd_official:
        md = """# MAS Empirical Evaluation Statistics Report

## Primary Experimental Metrics (Paired Permutation & Wilcoxon Tests)

**Status**: No official live benchmark runs yet (N=0). Simulation-only runs are strictly excluded from empirical statistics.

> **Note on Research Comparison**:
> Live benchmark data requires real provider execution under governed transport.
> Simulation runs (`SIMULATION_ONLY`) and test mocks are preserved for offline pipeline validation but are strictly excluded from empirical hypothesis testing or superiority claims.
"""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md)
        return md

    mas_sr = calculate_success_rate(mas_official)
    cd_sr = calculate_success_rate(cd_official)

    # Group task-level averages across official runs
    def get_task_metric_means(runs: List[Dict[str, Any]], metric_key: str) -> Dict[str, float]:
        task_vals: Dict[str, List[float]] = {}
        for r in runs:
            tid = r.get("task_id", "unknown")
            raw_v = r.get(metric_key)
            if metric_key == "quality":
                if r.get("status") not in ("COMPLETED", "COMPLETED_QUALITY_GATE"):
                    val = 0.0
                else:
                    val = float(raw_v) if raw_v is not None else 0.0
            else:
                val = float(raw_v) if raw_v is not None else 0.0
            task_vals.setdefault(tid, []).append(val)
        return {tid: sum(vals) / len(vals) for tid, vals in task_vals.items()}

    mas_q = get_task_metric_means(mas_official, "quality")
    cd_q = get_task_metric_means(cd_official, "quality")
    mas_q_per_1k = get_task_metric_means(mas_official, "quality_per_1k_tokens")
    cd_q_per_1k = get_task_metric_means(cd_official, "quality_per_1k_tokens")

    common_tasks = sorted(list(set(mas_q.keys()) & set(cd_q.keys())))
    if not common_tasks:
        md = """# MAS Empirical Evaluation Statistics Report

## Primary Experimental Metrics (Paired Permutation & Wilcoxon Tests)

**Status**: No common paired tasks completed between MAS and ChatDev (N=0).
"""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md)
        return md

    mas_q_list = [mas_q[t] for t in common_tasks]
    cd_q_list = [cd_q[t] for t in common_tasks]
    mas_q1k_list = [mas_q_per_1k[t] for t in common_tasks]
    cd_q1k_list = [cd_q_per_1k[t] for t in common_tasks]

    q_stat = compare_systems(mas_q_list, cd_q_list, metric_name="Quality")
    q1k_stat = compare_systems(mas_q1k_list, cd_q1k_list, metric_name="Quality per 1,000 tokens")

    md = f"""# MAS Empirical Evaluation Statistics Report

## Primary Experimental Metrics (Paired Permutation & Wilcoxon Tests, N={len(common_tasks)} Tasks)

### System Reliability & Success Rate
- **MAS Success Rate**: {mas_sr * 100:.1f}% ({sum(1 for r in mas_official if r.get('status') in ('COMPLETED', 'COMPLETED_QUALITY_GATE'))}/{len(mas_official)} official runs finished)
- **ChatDev Success Rate**: {cd_sr * 100:.1f}% ({sum(1 for r in cd_official if r.get('status') in ('COMPLETED', 'COMPLETED_QUALITY_GATE'))}/{len(cd_official)} official runs finished)

### Hypothesis Testing Table
| Metric | MAS (Mean ± SD) | ChatDev (Mean ± SD) | Difference | % Gain | Cohen's d | Permutation p | Wilcoxon p | Sig? (α=0.05) |
|---|---|---|---|---|---|---|---|---|
| **Quality** | {q_stat['mas_mean']:.3f} ± {q_stat['mas_std']:.3f} | {q_stat['chatdev_mean']:.3f} ± {q_stat['chatdev_std']:.3f} | {q_stat['difference']:+.3f} | {q_stat['percentage_gain']:+.1f}% | {q_stat['effect_size_cohens_d']:.3f} | {q_stat['permutation_p_value']:.4f} | {q_stat['wilcoxon_p_value']:.4f} | {'YES' if q_stat['statistically_significant'] else 'NO'} |
| **Quality / 1k Tokens** | {q1k_stat['mas_mean']:.3f} ± {q1k_stat['mas_std']:.3f} | {q1k_stat['chatdev_mean']:.3f} ± {q1k_stat['chatdev_std']:.3f} | {q1k_stat['difference']:+.3f} | {q1k_stat['percentage_gain']:+.1f}% | {q1k_stat['effect_size_cohens_d']:.3f} | {q1k_stat['permutation_p_value']:.4f} | {q1k_stat['wilcoxon_p_value']:.4f} | {'YES' if q1k_stat['statistically_significant'] else 'NO'} |

> **Note on Research Comparison**:
> MAS is compared directly against ChatDev under identical conditions and logging proxy token measurements.
> The comparison with iCoder is indirect and referenced only through published values in You et al. (2026).
"""

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md)

    return md
