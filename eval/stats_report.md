# MAS Empirical Evaluation Statistics Report

## Primary Experimental Metrics (Paired Permutation & Wilcoxon Tests, N=21 Tasks)

### System Reliability & Success Rate
- **MAS Success Rate**: 89.2% (33/37 official runs finished)
- **ChatDev Success Rate**: 83.8% (31/37 official runs finished)

### Hypothesis Testing Table
| Metric | MAS (Mean ± SD) | ChatDev (Mean ± SD) | Difference | % Gain | Cohen's d | Permutation p | Wilcoxon p | Sig? (α=0.05) |
|---|---|---|---|---|---|---|---|---|
| **Quality** | 0.445 ± 0.170 | 0.040 ± 0.104 | +0.405 | +1025.3% | 1.987 | 0.0001 | 0.0001 | YES |
| **Quality / 1k Tokens** | 0.040 ± 0.027 | 0.001 ± 0.002 | +0.039 | +4862.5% | 1.409 | 0.0001 | 0.0001 | YES |

> **Note on Research Comparison**:
> MAS is compared directly against ChatDev under identical conditions and logging proxy token measurements.
> The comparison with iCoder is indirect and referenced only through published values in You et al. (2026).
