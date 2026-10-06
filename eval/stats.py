"""Statistical analysis engine for task-level paired comparisons and permutation testing."""

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
    """Computes mean, standard deviation, median, and 95% confidence interval."""
    if not data:
        return {"mean": 0.0, "std": 0.0, "median": 0.0, "ci_95": (0.0, 0.0), "n": 0}
    return {
        "mean": round(mean(data), 4),
        "std": round(std(data), 4),
        "median": round(median(data), 4),
        "ci_95": confidence_interval(data),
        "n": len(data),
    }


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
    eff_size = cohens_d(mas_values, chatdev_values)

    mas_m = mas_sum["mean"]
    cd_m = cd_sum["mean"]
    pct_gain = round(((mas_m - cd_m) / cd_m * 100), 2) if cd_m > 0 else 0.0

    return {
        "metric": metric_name,
        "mas_mean": mas_m,
        "mas_std": mas_sum["std"],
        "chatdev_mean": cd_m,
        "chatdev_std": cd_sum["std"],
        "difference": round(mas_m - cd_m, 4),
        "percentage_gain": pct_gain,
        "effect_size_cohens_d": round(eff_size, 4),
        "p_value": p_val,
        "statistically_significant": p_val < 0.05,
    }
