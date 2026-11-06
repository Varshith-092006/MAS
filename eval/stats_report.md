# MAS Empirical Evaluation Statistics Report

## Primary Experimental Metrics (Paired Permutation Test, N=1 Tasks)

| Metric | MAS (Mean ± SD) | ChatDev (Mean ± SD) | Difference | % Gain | Cohen's d | p-value (α=0.05) | Sig? |
|---|---|---|---|---|---|---|---|
| **Quality** | 0.643 ± 0.000 | 0.673 ± 0.000 | -0.030 | -4.5% | 0.000 | 1.0000 | NO |
| **Quality / 1k Tokens** | 0.023 ± 0.000 | 0.012 ± 0.000 | +0.011 | +95.8% | 0.000 | 1.0000 | NO |

> **Note on Research Comparison**:
> MAS is compared directly against ChatDev under identical conditions and logging proxy token measurements.
> The comparison with iCoder is indirect and referenced only through published values in You et al. (2026).
