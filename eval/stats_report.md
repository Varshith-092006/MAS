# MAS Empirical Evaluation Statistics Report

## Primary Experimental Metrics (Paired Permutation & Wilcoxon Tests, N=6 Tasks)

### System Reliability & Success Rate
- **MAS Success Rate**: 81.8% (18/22 official runs finished)
- **ChatDev Success Rate**: 77.3% (17/22 official runs finished)

### Hypothesis Testing Table
| Metric | MAS (Mean ± SD) | ChatDev (Mean ± SD) | Difference | % Gain | Cohen's d | Permutation p | Wilcoxon p | Sig? (α=0.05) |
|---|---|---|---|---|---|---|---|---|
| **Quality** | 0.327 ± 0.172 | 0.138 ± 0.164 | +0.189 | +136.6% | 1.202 | 0.0628 | 0.0625 | NO |
| **Quality / 1k Tokens** | 0.020 ± 0.015 | 0.003 ± 0.004 | +0.017 | +576.7% | 1.257 | 0.0628 | 0.0625 | NO |

> **Note on Research Comparison**:
> MAS is compared directly against ChatDev under identical conditions and logging proxy token measurements.
> The comparison with iCoder is indirect and referenced only through published values in You et al. (2026).
