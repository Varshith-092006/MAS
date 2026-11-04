# MAS Empirical Evaluation Statistics Report

## Primary Experimental Metrics (Paired Permutation Test, N=1 Tasks)

| Metric | MAS (Mean ± SD) | ChatDev (Mean ± SD) | Difference | % Gain | Cohen's d | p-value (α=0.05) | Sig? |
|---|---|---|---|---|---|---|---|
| **Quality** | 0.364 ± 0.000 | 0.857 ± 0.000 | -0.493 | -57.6% | 0.000 | 1.0000 | NO |
| **Quality / 1k Tokens** | 0.006 ± 0.000 | 0.015 ± 0.000 | -0.009 | -57.0% | 0.000 | 1.0000 | NO |

> **Note on Research Comparison**:
> MAS is compared directly against ChatDev under identical conditions and logging proxy token measurements.
> The comparison with iCoder is indirect and referenced only through published values in You et al. (2026).
