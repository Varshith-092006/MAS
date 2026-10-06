"""Unit tests for statistical analysis engine."""

from eval.stats import (
    cohens_d,
    compare_systems,
    confidence_interval,
    mean,
    paired_permutation_test,
    std,
    summarize_metric_distribution,
)


def test_metric_distributions():
    data = [0.8, 0.85, 0.9, 0.75, 0.8]
    summary = summarize_metric_distribution(data)
    assert summary["mean"] == 0.82
    assert summary["n"] == 5
    assert len(summary["ci_95"]) == 2


def test_paired_permutation_test_significance():
    # Superior performance in arm A vs arm B
    a = [0.90, 0.88, 0.92, 0.85, 0.89, 0.94, 0.91, 0.87, 0.93, 0.90]
    b = [0.40, 0.45, 0.42, 0.38, 0.41, 0.44, 0.39, 0.43, 0.40, 0.42]

    p_val = paired_permutation_test(a, b, trials=1000)
    assert p_val < 0.05, f"Expected significant p < 0.05, got {p_val}"

    # Comparison helper
    comp = compare_systems(a, b, metric_name="Quality", trials=1000)
    assert comp["statistically_significant"] is True
    assert comp["percentage_gain"] > 0
    assert comp["effect_size_cohens_d"] > 1.0


def test_paired_permutation_test_null():
    # Identical performance
    a = [0.70, 0.75, 0.72, 0.68, 0.71]
    b = [0.70, 0.75, 0.72, 0.68, 0.71]

    p_val = paired_permutation_test(a, b, trials=500)
    assert p_val > 0.5
