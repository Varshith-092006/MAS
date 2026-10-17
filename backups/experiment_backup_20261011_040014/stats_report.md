# MAS Empirical Evaluation Statistics Report

## Primary Experimental Metrics (Paired Permutation Test, N=20 Tasks)

| Metric | MAS (Mean ± SD) | ChatDev (Mean ± SD) | Difference | % Gain | Cohen's d | p-value (α=0.05) | Sig? |
|---|---|---|---|---|---|---|---|
| **Quality** | 0.858 ± 0.008 | 0.774 ± 0.265 | +0.084 | +10.9% | 0.321 | 0.3251 | NO |
| **Quality / 1k Tokens** | 0.540 ± 0.005 | 0.258 ± 0.088 | +0.282 | +109.2% | 3.225 | 0.0001 | YES |

> **Note on Research Comparison**:
> MAS is compared directly against ChatDev under identical conditions and logging proxy token measurements.
> The comparison with iCoder is indirect and referenced only through published values in You et al. (2026).
