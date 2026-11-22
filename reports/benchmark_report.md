# MAS Empirical Evaluation Final Benchmark Report

Generated at: results.csv / benchmark_manifest.json

**Benchmark metadata** (from run records):

- Provider type(s): gemini
- Model(s): gemini-3.5-flash-lite
- Official MAS runs: 5, Official ChatDev runs: 5


### Table 1: Indicative Published Baselines from Literature (You et al., 2026)

> [!WARNING]
> Indicative only: The numbers below are published literature references from the iCoder paper (Information and Software Technology 198 (2026) 108224) evaluated on different models (commercial GPT-3.5-Turbo and GPT-4o) and task splits. They are NOT local experimental results and must never be claimed as beaten locally.

| Model Condition | System | Tasks | Completeness | Executability | Consistency | Quality | Tokens / Task | Time (s) | LOC |
|---|---|---|---|---|---|---|---|---|---|
| GPT-3.5 Turbo | ChatDev | 100 | 0.9022 | 0.8100 | 0.8084 | 0.5906 | 22,327 | 439.6 | 113.9 |
| GPT-3.5 Turbo | iCoder | 100 | 0.9521 | 0.8800 | 0.8238 | 0.6902 | 411,145 | 2,700.4 | 168.9 |
| GPT-4o | ChatDev | 20 | 1.0000 | 0.8000 | 0.8187 | 0.6550 | 30,417 | 1,058.7 | 126.0 |
| GPT-4o | iCoder | 20 | 0.9960 | 0.9500 | 0.8375 | 0.7924 | 104,883 | 1,620.1 | 216.2 |


### Table 2: Primary Benchmark Comparison on Pinned Model

| System | N | Completeness (95% CI) | Executability (95% CI) | Consistency (95% CI) | Quality (95% CI) | Wilcoxon p-value | Cohen's d |
|---|---|---|---|---|---|---|---|
| **MAS (Ours)** | 5 | 1.0000 [1.0000, 1.0000] | 1.0000 [1.0000, 1.0000] | 0.4968 [0.4383, 0.5741] | 0.4968 [0.4383, 0.5741] | 0.12500 | 1.0470 |
| **ChatDev** | 5 | 1.0000 [1.0000, 1.0000] | 0.4000 [0.0000, 0.8000] | 0.5469 [0.4885, 0.6053] | 0.2182 [0.0000, 0.4700] | — | — |


### Table 3: Efficiency and Computational Overhead

| System | Tokens / Task | Quality / 1k Tokens | Est. Cost ($) | LLM Calls | Wall-Clock Time (s) | Lines of Code (LOC) |
|---|---|---|---|---|---|---|
| **MAS (Ours)** | 16,635.2 | 0.0299 | $0.0000 | 4.8 | 41.8s | 969.0 |
| **ChatDev** | 45,090.4 | 0.0048 | $0.0000 | 14.8 | 332.5s | 172.6 |


### Table 4: Per-Category Quality Breakdown

| Category | Tasks | MAS Quality | ChatDev Quality | Delta (MAS - CD) |
|---|---|---|---|---|
| Education | 4 | 0.4996 | 0.1154 | +0.3842 |
| Work | 1 | 0.4855 | 0.6294 | -0.1439 |
| Life | 0 | NOT RUN | NOT RUN | NOT RUN |
| Games | 0 | NOT RUN | NOT RUN | NOT RUN |
| Creation | 0 | NOT RUN | NOT RUN | NOT RUN |


### Table 5: Ablation Matrix (MAS Modular Architectural Components)

| Condition | Description | Tasks | Mean Quality | Mean Tokens | LLM Calls | Delta Quality vs A0 |
|---|---|---|---|---|---|---|
| **A0** | Full MAS (Default Baseline) | 5 | 0.4968 | 16,635 | 4.8 | Reference (0.0000) |
| **A1** | Always Architect (No Complexity Router) | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| **A2** | Full Repo Context (No AST Slicing) | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| **A3** | No Evidence Review (No AST/Ruff/Bandit Checks) | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| **A4** | Single Iteration (No Reflection Loop) | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |


### Table 6: Test Suite Pass Rates and Verification

| System | Shared Test Score | Executability Rate | Benchmark Success Rate |
|---|---|---|---|
| **MAS (Ours)** | 0.9000 | 100.0% | 100.0% |
| **ChatDev** | 0.4000 | 40.0% | 100.0% |

