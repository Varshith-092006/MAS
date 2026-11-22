# MAS Empirical Evaluation Statistics Report

## Primary Experimental Metrics (Paired Permutation & Wilcoxon Tests, N=18 Tasks)

### System Reliability & Success Rate
- **MAS Success Rate**: 88.2% (30/34 official runs finished)
- **ChatDev Success Rate**: 82.9% (29/35 official runs finished)

### Hypothesis Testing Table
| Metric | MAS (Mean ± SD) | ChatDev (Mean ± SD) | Difference | % Gain | Cohen's d | Permutation p | Wilcoxon p | Sig? (α=0.05) |
|---|---|---|---|---|---|---|---|---|
| **Quality** | 0.430 ± 0.178 | 0.046 ± 0.111 | +0.384 | +833.8% | 1.813 | 0.0001 | 0.0003 | YES |
| **Quality / 1k Tokens** | 0.037 ± 0.028 | 0.001 ± 0.002 | +0.036 | +3570.0% | 1.255 | 0.0001 | 0.0003 | YES |

> **Note on Research Comparison**:
> MAS is compared directly against ChatDev under identical conditions and logging proxy token measurements.
> The comparison with iCoder is indirect and referenced only through published values in You et al. (2026).
