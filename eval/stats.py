"""Statistical analysis engine for task-level paired comparisons, permutation testing, Wilcoxon, and bootstrap CIs."""

import math
import random
from typing import Any, Dict, List, Tuple
import numpy as np


def mean(data: List[float]) -> float:
    return float(np.mean(data)) if len(data) > 0 else 0.0


def std(data: List[float]) -> float:
    return float(np.std(data, ddof=1)) if len(data) > 1 else 0.0


def median(data: List[float]) -> float:
    return float(np.median(data)) if len(data) > 0 else 0.0


def cohens_d(a: List[float], b: List[float]) -> float:
    """Calculates Cohen's d effect size for paired differences."""
    if len(a) != len(b) or len(a) < 2:
        return 0.0
    diffs = np.array(a) - np.array(b)
    s = np.std(diffs, ddof=1)
    if s == 0:
        return 0.0
    return float(np.mean(diffs) / s)


def confidence_interval(data: List[float], confidence: float = 0.95) -> Tuple[float, float]:
    """Calculates normal/t confidence interval for sample mean."""
    if len(data) < 2:
        val = data[0] if data else 0.0
        return (val, val)
    m = np.mean(data)
    s = np.std(data, ddof=1)
    # 1.96 approximation for 95% CI
    margin = 1.96 * (s / math.sqrt(len(data)))
    return (round(float(m - margin), 4), round(float(m + margin), 4))


def bootstrap_ci(
    data: List[float],
    n_resamples: int = 10000,
    confidence: float = 0.95,
    seed: int = 42,
) -> Tuple[float, float]:
    """Calculates percentile bootstrap confidence interval for sample mean (10,000 resamples)."""
    if not data:
        return (0.0, 0.0)
    if len(data) == 1:
        v = round(float(data[0]), 4)
        return (v, v)

    rng = np.random.default_rng(seed)
    arr = np.array(data, dtype=float)
    boot_samples = rng.choice(arr, size=(n_resamples, len(arr)), replace=True)
    boot_means = np.mean(boot_samples, axis=1)

    alpha = (1.0 - confidence) / 2.0
    low = np.percentile(boot_means, alpha * 100)
    high = np.percentile(boot_means, (1.0 - alpha) * 100)
    return (round(float(low), 4), round(float(high), 4))


def wilcoxon_signed_rank_test(
    a: List[float],
    b: List[float],
) -> float:
    """Computes two-sided Wilcoxon signed-rank test across paired task-level observations.

    Handles small n and identical samples safely without crashing.
    """
    if len(a) != len(b) or len(a) == 0:
        return 1.0

    arr_a = np.array(a, dtype=float)
    arr_b = np.array(b, dtype=float)
    diffs = arr_a - arr_b

    # If all differences are zero, samples are identical
    if np.all(diffs == 0):
        return 1.0

    # Wilcoxon requires non-zero differences
    non_zero_diffs = diffs[diffs != 0]
    if len(non_zero_diffs) == 0:
        return 1.0

    try:
        from scipy import stats
        res = stats.wilcoxon(arr_a, arr_b, alternative="two-sided")
        return round(float(res.pvalue), 5)
    except Exception:
        return 1.0


def paired_permutation_test(
    a: List[float],
    b: List[float],
    trials: int = 10000,
    seed: int = 42,
) -> float:
    """Executes two-sided paired permutation test across task-level observations (LLD Sec 7.8)."""
    if len(a) != len(b) or len(a) == 0:
        return 1.0

    rng = random.Random(seed)
    diffs = [a_i - b_i for a_i, b_i in zip(a, b)]
    observed = abs(sum(diffs) / len(diffs))

    count = 0
    n = len(diffs)

    for _ in range(trials):
        flipped = [d if rng.random() > 0.5 else -d for d in diffs]
        perm_mean = abs(sum(flipped) / n)
        if perm_mean >= observed:
            count += 1

    p_value = (count + 1) / (trials + 1)
    return round(p_value, 5)


def summarize_metric_distribution(data: List[float]) -> Dict[str, Any]:
    """Computes mean, standard deviation, median, 95% CI, and bootstrap 95% CI."""
    if not data:
        return {
            "mean": 0.0,
            "std": 0.0,
            "median": 0.0,
            "ci_95": (0.0, 0.0),
            "ci_95_bootstrap": (0.0, 0.0),
            "n": 0,
        }
    return {
        "mean": round(mean(data), 4),
        "std": round(std(data), 4),
        "median": round(median(data), 4),
        "ci_95": confidence_interval(data),
        "ci_95_bootstrap": bootstrap_ci(data, n_resamples=10000, seed=42),
        "n": len(data),
    }


def calculate_success_rate(runs: List[Dict[str, Any]]) -> float:
    """Calculates the share of official runs that finished successfully (COMPLETED / COMPLETED_QUALITY_GATE)."""
    if not runs:
        return 0.0
    official_runs = [
        r for r in runs
        if (r.get("official") is True or str(r.get("official")).lower() == "true")
        and r.get("status") != "SIMULATION_ONLY"
    ]
    if not official_runs:
        # Fallback to all non-simulation runs if official flag is not populated yet
        official_runs = [r for r in runs if r.get("status") != "SIMULATION_ONLY"]
    if not official_runs:
        return 0.0
    success_count = sum(
        1 for r in official_runs
        if r.get("status") in ("COMPLETED", "COMPLETED_QUALITY_GATE")
    )
    return round(success_count / len(official_runs), 4)


def compare_systems(
    mas_values: List[float],
    chatdev_values: List[float],
    metric_name: str = "Quality",
    trials: int = 10000,
) -> Dict[str, Any]:
    """Performs full statistical comparison between MAS and ChatDev on a specific metric."""
    mas_sum = summarize_metric_distribution(mas_values)
    cd_sum = summarize_metric_distribution(chatdev_values)
    p_val = paired_permutation_test(mas_values, chatdev_values, trials=trials)
    wilc_p = wilcoxon_signed_rank_test(mas_values, chatdev_values)
    eff_size = cohens_d(mas_values, chatdev_values)

    mas_m = mas_sum["mean"]
    cd_m = cd_sum["mean"]
    pct_gain = round(((mas_m - cd_m) / cd_m * 100), 2) if cd_m > 0 else 0.0

    return {
        "metric": metric_name,
        "mas_mean": mas_m,
        "mas_std": mas_sum["std"],
        "mas_ci_95": mas_sum["ci_95"],
        "mas_ci_95_bootstrap": mas_sum["ci_95_bootstrap"],
        "chatdev_mean": cd_m,
        "chatdev_std": cd_sum["std"],
        "chatdev_ci_95": cd_sum["ci_95"],
        "chatdev_ci_95_bootstrap": cd_sum["ci_95_bootstrap"],
        "difference": round(mas_m - cd_m, 4),
        "percentage_gain": pct_gain,
        "effect_size_cohens_d": round(eff_size, 4),
        "p_value": p_val,
        "permutation_p_value": p_val,
        "wilcoxon_p_value": wilc_p,
        "statistically_significant": p_val < 0.05 or wilc_p < 0.05,
    }
