# MAS Empirical Evaluation Statistics Report

## Primary Experimental Metrics (Paired Permutation & Wilcoxon Tests, N=6 Tasks)

### System Reliability & Success Rate
- **MAS Success Rate**: 76.5% (13/17 official runs finished)
- **ChatDev Success Rate**: 70.6% (12/17 official runs finished)

### Hypothesis Testing Table
| Metric | MAS (Mean ± SD) | ChatDev (Mean ± SD) | Difference | % Gain | Cohen's d | Permutation p | Wilcoxon p | Sig? (α=0.05) |
|---|---|---|---|---|---|---|---|---|
| **Quality** | 0.290 ± 0.158 | 0.102 ± 0.161 | +0.188 | +184.4% | 1.230 | 0.0628 | 0.0625 | NO |
| **Quality / 1k Tokens** | 0.015 ± 0.010 | 0.002 ± 0.003 | +0.013 | +665.0% | 1.535 | 0.0628 | 0.0625 | NO |

> **Note on Research Comparison**:
> MAS is compared directly against ChatDev under identical conditions and logging proxy token measurements.
> The comparison with iCoder is indirect and referenced only through published values in You et al. (2026).
