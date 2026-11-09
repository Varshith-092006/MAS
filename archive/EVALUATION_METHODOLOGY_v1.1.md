# Evaluation Methodology & Experimental Protocols (v1.1 Methodology Revision)

**Document Version:** 1.1.0-REVISION  
**Previous Version:** 1.0.0-FROZEN (`EVALUATION_METHODOLOGY_v1.0.md`, preserved intact)  
**Date of Revision:** October 11, 2026  
**Status:** Pre-Benchmark Evaluation Methodology Revision  
**Platform:** Multi-Agent Software Engineering Team (MAS) Research Platform  
**Target Suite:** SRDD-20 Canonical Dataset  

---

## 1. Rationale for Methodology Revision v1.1

Following the live matched pilot on task `srdd_educ_01`, two methodological defects were identified during formal pre-benchmark auditing:

1. **Dataset Task Selection Unalignment:**
   - *Defect:* `scripts/run_real_task_benchmark.py` invoked `load_srdd_benchmark_tasks("eval/tasks.json")`, accidentally passing the string file path as the first positional argument (`seed`), which overrode the random seed and sampled row 716 (`QuickStudy`) instead of canonical row 823 (`Science Question Solver`, `srdd_educ_01`).
   - *Correction:* Task loading is strictly bound to `eval/tasks.json` by direct JSON deserialization. Byte-for-byte identical canonical requirement strings and SHA-256 requirement checksums are audited before every run. Old pilot runs are retained as historical diagnostic records (`DIAGNOSTIC_RUN`).

2. **Evaluator Asymmetry & Non-Behavioral Smoke Stubs:**
   - *Defect:* The smoke test in `mas/analysis/sandbox.py` stubbed `tk.Tk.mainloop = lambda self: None`, allowing Tkinter applications to score $E=1.0$ without proving that any domain logic was executed or that objects functioned. Conversely, MAS generated an HTML/JS web artifact and received $E=0.0$ because only `.py` files were inspected.
   - *Correction:* 
     - A unified Software-Generation Contract (`BENCHMARK_TASK_CONTRACT.md`) requires Python 3.11+ executable projects with a `main.py` entry point for both systems.
     - Headless GUI execution is verified by instantiating the UI/application classes, feeding input queries, exercising solver logic, and asserting clean termination.
     - CLI / modular projects are exercised across identical test cases and timeout bounds.
     - Format-specific neutral adapters ensure neither framework is arbitrarily penalized or rewarded based on UI modality.

---

## 2. Frozen Primary Quality Metric ($Q_i$)

The primary metric from iCoder (*Information and Software Technology*, 2026) remains strictly unmodified:

$$Q_i = C_i \times E_i \times S_i$$

$$\bar{Q} = \frac{1}{N}\sum_{i=1}^{N} Q_i$$

### 2.1 Completeness ($C_i \in [0.0, 1.0]$)
$$C_i = 1 - \frac{\text{unimplemented\_functions}}{\text{total\_functions}}$$
Where unimplemented functions are detected via AST analysis as bodies containing exclusively `pass`, docstring literals, `...`, or `raise NotImplementedError`. If a project contains only module-level execution statements without function declarations, $C_i = 1.0$.

### 2.2 Executability ($E_i \in \{0.0, 1.0\}$)
$$E_i = \begin{cases} 1.0 & \text{if project entry point and essential behavior test execute with exit code 0} \\ 0.0 & \text{if execution crashes, times out (>45s), or raises unhandled exception} \end{cases}$$

### 2.3 Consistency ($S_i \in [0.0, 1.0]$)
$$S_i = \cos(\mathbf{e}_{\text{prompt}}, \mathbf{e}_{\text{code}}) = \frac{\mathbf{e}_{\text{prompt}} \cdot \mathbf{e}_{\text{code}}}{\|\mathbf{e}_{\text{prompt}}\| \|\mathbf{e}_{\text{code}}\|}$$
Computed using `all-MiniLM-L6-v2` neural sentence embeddings over aggregate source code text.

---

## 3. Token Efficiency Index

$$\text{Efficiency}_i = \frac{Q_i}{T_i} \times 1000$$

- $T_i$ is derived strictly from provider-reported usage (`usage.total_tokens`).
- If $T_i$ is unavailable, missing, or zero, Efficiency is recorded as `UNAVAILABLE` (`N/A`), never as an invented zero or synthetic estimation.

---

## 4. Frozen Independent Fixed Neutral Tests (Level 1 + Level 2)

Shared test evaluation follows:
$$\text{SharedTest} = 0.5 \times \text{Level1\_Smoke} + 0.5 \times \text{Level2\_Checks}$$

- **Level 1 (Smoke & Lifecycle):** Clean import, module object construction, and clean shutdown under 45s sandbox limit.
- **Level 2 (Fixed Behavioral Checks):** Standardized, frozen assertions stored in `eval/checks/level2_checks.json` and `eval/checks/test_srdd_educ_01.py`.
  - Physics Question: Velocity/speed or motion calculation.
  - Chemistry Question: Atomic structure / Carbon properties.
  - Biology Question: Photosynthesis process and components.
- Neither system can inspect, alter, or generate these evaluation assertions.
- Internal MAS pytest pass rates are retained exclusively as a diagnostic engineering metric and are excluded from the neutral benchmark $Q_i$.
