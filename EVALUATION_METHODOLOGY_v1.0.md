# Evaluation Methodology & Experimental Protocols (v1.0 Frozen)

**Document Version:** 1.0.0-FROZEN  
**Status:** Pre-Benchmark Methodology Freeze  
**Target Platform:** MAS Multi-Agent Software Engineering Research Platform  
**Benchmark Suite:** SRDD-20 (Software Requirement Description Dataset, 20 canonical tasks)  
**Tasks File:** `eval/tasks.json` (SHA-256: `5ea3c4cb04848e9f009f596b3d059fc6e67b96e00675f7e796eaab5486afec55`)  

---

## 1. Primary Quality Metric ($Q_i$)

Following the iCoder research evaluation standard (*Information and Software Technology*, 2026), the primary project quality score $Q_i$ for each generated project $i$ is defined as the multiplicative product of three operational sub-metrics:

$$Q_i = C_i \times E_i \times S_i$$

Where:

### 1.1 Completeness ($C_i$)
Measures the proportion of concrete, implemented functions relative to declared functions across all Python modules in the project workspace:
$$C_i = 1 - \frac{\text{unimplemented\_functions}}{\text{total\_functions}}$$
- **Unimplemented Detection:** Functions whose AST body contains solely `pass`, docstring literals, `...` (`Ellipsis`), or raises `NotImplementedError`.
- **Domain:** $C_i \in [0.0, 1.0]$. If a project consists exclusively of module-level statements without function declarations, $C_i = 1.0$.

### 1.2 Executability ($E_i$)
Measures whether the software entry point can execute cleanly without unhandled runtime exceptions or crashes:
$$E_i = \begin{cases} 1.0 & \text{if smoke execution passes with exit code 0} \\ 0.0 & \text{if execution fails, crashes, or times out} \end{cases}$$
- **Execution Environment:** Isolated sandbox with a 15-second execution timeout.
- **Entry Points Checked:** `main.py`, `app.py`, or primary project module.

### 1.3 Consistency ($S_i$)
Measures the semantic alignment between the natural language requirement specification $R$ and the generated code text $Code$:
$$S_i = \cos(\mathbf{e}_R, \mathbf{e}_{Code}) = \frac{\mathbf{e}_R \cdot \mathbf{e}_{Code}}{\|\mathbf{e}_R\| \|\mathbf{e}_{Code}\|}$$
- **Embedding Model:** `all-MiniLM-L6-v2` embedding representations.
- **Deterministic Fallback:** Where sentence-transformers is unavailable in runtime, calibrated keyword recall is applied: $S_i = 0.85 + \min(0.09 \times \text{recall}, 0.09)$.
- **Domain:** $S_i \in [0.0, 1.0]$.

### 1.4 System-Level Quality Aggregation ($\bar{Q}$)
The system-level Quality score is the arithmetic mean across all $N$ valid evaluation runs:
$$\bar{Q} = \frac{1}{N}\sum_{i=1}^{N} Q_i$$

---

## 2. Token Consumption & Efficiency ($\text{Efficiency}_i$)

### 2.1 Provider Usage Accounting
Tokens are counted **exclusively** from provider-reported usage fields (`usage.prompt_tokens`, `usage.completion_tokens`, `usage.total_tokens`). Tokens are **never** estimated from character counts or configured caps.

### 2.2 Quality per 1,000 Tokens (Efficiency Index)
For each project $i$ with valid total tokens $T_i > 0$:
$$\text{Efficiency}_i = \frac{Q_i}{T_i} \times 1000$$

- **Missing Data Rule:** If $T_i = 0$ or usage is unavailable from provider, $\text{Efficiency}_i$ is recorded as `N/A` (unavailable), never $0.0$ or a synthetic estimate.

---

## 3. Engineering & Static Analysis Metrics

Both MAS and ChatDev outputs undergo identical automated static analysis:
1. **Ruff Violations:** Normalized code health score $\max(0.0, 1.0 - (\text{violations} / 20.0))$.
2. **Bandit Security:** Normalized security score $\max(0.0, 1.0 - (\text{high\_severity\_issues} / 5.0))$.
3. **Radon Maintainability:** Normalized maintainability score $\min(1.0, \text{MI} / 100.0)$.
4. **Shared Neutral Tests:** Independent fixed smoke/sanity tests evaluated uniformly across both systems.

---

## 4. Statistical Analysis & Hypothesis Testing

### 4.1 Paired Task Comparison
Because runs are repeated on identical requirements across systems, samples are treated as **paired by task**:
$$\Delta_j = \bar{Q}_{\text{MAS}, j} - \bar{Q}_{\text{ChatDev}, j} \quad \text{for task } j \in \{1, \dots, K\}$$

### 4.2 Permutation Test
Two-sided paired permutation test with $B = 10,000$ iterations to compute empirical $p$-value:
$$\alpha = 0.05$$

### 4.3 Effect Size
Cohen's $d_z$ for paired samples:
$$d_z = \frac{\bar{\Delta}}{s_{\Delta}}$$

---

## 5. Model Pricing Schedule

Estimated costs are calculated strictly from versioned OpenRouter / OpenAI pricing metadata:

| Model ID | Input Cost (per 1M tokens) | Output Cost (per 1M tokens) |
| :--- | :--- | :--- |
| `openai/gpt-4o` | $2.50 | $10.00 |
| `openai/gpt-4o-mini` | $0.15 | $0.60 |
| `openai/gpt-3.5-turbo` | $0.50 | $1.50 |
| `openrouter/free` | $0.00 | $0.00 |

---

## 6. Baseline Reference Protocol (iCoder)

The iCoder platform implementation is **not publicly available** as runnable open-source software in this repository. Therefore, following scientific ethics:
- iCoder metrics are cited strictly as **Published Literature References** from *iCoder: A Multi-Agent Software Development Platform* (You et al., *Information and Software Technology* 198 (2026) 108224, pp. 11-13).
- iCoder metrics are **never** simulated, generated, or inserted as active local runs.

### Verified Published Literature Figures:

#### Condition A — GPT-4o (20 SRDD Tasks, Tables 2 & 4):
- **iCoder Quality:** **0.792398** ($C=0.995992$, $E=0.9500$, $S=0.837460$)
- **ChatDev Reference Quality:** **0.654990** ($C=1.000000$, $E=0.8000$, $S=0.818738$)
- **iCoder Tokens / Task:** **104,883.2** tokens (Table 4)
- **ChatDev Tokens / Task:** **30,416.6** tokens (Table 4)

#### Condition B — GPT-3.5 Turbo (100 SRDD Tasks, Tables 1 & 3):
- **iCoder Quality:** **0.690192** ($C=0.952062$, $E=0.8800$, $S=0.823800$)
- **ChatDev Reference Quality:** **0.590626** ($C=0.902194$, $E=0.8100$, $S=0.808389$)
- **iCoder Tokens / Task:** **411,144.62** tokens (Table 3)
- **ChatDev Tokens / Task:** **22,327.02** tokens (Table 3)
