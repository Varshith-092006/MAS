# MAS: Benchmark Methodology & Empirical Evidence
## Final Year Project Submission — Comparative Evaluation Report

---

## 1. Benchmark Specification & Dataset

Comparative benchmarking is conducted against the **SRDD-20 (Software Requirement Decomposition Dataset)** canonical benchmark suite. The dataset comprises 20 canonical software engineering tasks distributed across five operational domains:

- **Education (4 tasks):** Science Question Solver (`srdd_educ_01`), Math Helper, Language Quiz, History Flashcards.
- **Work (4 tasks):** Task Tracker, Meeting Scheduler, Expense Logger, Resume Builder.
- **Life (4 tasks):** Habit Tracker, Recipe Organizer, Fitness Planner, Budget Tracker.
- **Games (4 tasks):** Text Adventure, Sudoku Solver, Tic-Tac-Toe AI, Blackjack Game.
- **Creation (4 tasks):** Markdown Editor, Diagram Generator, ASCII Art Creator, Static Site Generator.

### Dataset Integrity & Freezing
The canonical task specification file [`eval/tasks.json`](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/eval/tasks.json) is frozen prior to evaluation. Its integrity is verified by SHA-256 hash:

```text
5ea3c4cb04848e9f009f596b3d059fc6e67b96e00675f7e796eaab5486afec55
```
*(Verified matching via `python -c "import hashlib; assert hashlib.sha256(open('eval/tasks.json', 'rb').read()).hexdigest() == '5ea3c4cb04848e9f009f596b3d059fc6e67b96e00675f7e796eaab5486afec55'"`).*

---

## 2. Independent Evaluation Metrics

Generated software repositories are evaluated outside the agent generation loop by the **Hidden Neutral Evaluator** ([`eval/neutral_evaluator.py`](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/eval/neutral_evaluator.py)) using standardized, published metrics:

1. **Completeness ($C \in [0.0, 1.0]$):**
   Ratio of planned modules present in the workspace that are non-empty and non-trivial ($C = \frac{|F_{\text{actual}}|}{|F_{\text{planned}}|}$).
2. **Executability ($E \in \{0.0, 1.0\}$):**
   Level 1 smoke execution test within an isolated disposable sandbox. A project achieves $E = 1.0$ if the primary entry point (`main.py`) initializes cleanly, handles `--help` with exit code 0, or executes without unhandled exceptions or syntax errors.
3. **Semantic Consistency ($Sim \in [0.0, 1.0]$):**
   Sentence-transformer embedding cosine similarity between the natural language requirement and aggregate source code representation using `all-MiniLM-L6-v2`.
4. **Software Quality ($Q \in [0.0, 1.0]$):**
   Compound product: $Q = C \times E \times Sim$. If the application fails to execute ($E = 0.0$), $Q$ evaluates strictly to $0.0$.
5. **Quality per 1,000 Tokens ($Q_{1k}$):**
   Token efficiency metric: $Q_{1k} = \frac{Q}{\text{Total Provider Tokens} / 1000}$.
6. **Shared Fixed Tests ($T \in [0.0, 1.0]$):**
   Level 2 frozen test harness exercising domain-specific assertions (Physics, Chemistry, Biology queries for `srdd_educ_01`).

---

## 3. Governance Policies & Resource Bounds

| Parameter | Bound | Enforcement Mechanism |
| :--- | :--- | :--- |
| **Per-Run Token Budget** | 60,000 tokens | Atomic pre-dispatch budget gate (`TokenLogger.reserve_budget`). Blocks request fail-closed if remaining budget $< 50$ completion tokens. |
| **Daily Outbound HTTP Limit** | 45 transmissions / UTC day | File-locked persistent ledger (`eval/outbound_transmission_ledger.json`). Halts execution fail-closed on cap breach. |
| **Minimum Batch Threshold** | 33 transmissions | A live paired run requires at least 33 remaining transmissions after preflight. Runs are deferred if allowance $< 33$. |
| **Model Policy** | `cohere/north-mini-code:free` | Exact match verification (`is_model_match`). Substring variants and free-tier substitutions are strictly rejected. |
| **Fallback Policy** | Disabled | Payload strictly enforces `"provider": {"allow_fallbacks": false}`. |
| **Authorized Spend** | $0.00 | Enforced via `MAS_STAGE_MAX_SPEND=0.00`. |

---

## 4. Complete Historical Empirical Record

In accordance with scientific integrity standards, every historical benchmark attempt is fully preserved in the database, results ledger, and manifest. Historical runs are never purged or altered to artificially improve statistics:

| Run ID | Task ID | System | Model | Tokens | Cost (USD) | Status | Executability ($E$) | Quality ($Q$) | Notes / Failure Diagnosis |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `sim_mas_srdd_educ_01_r1` | `srdd_educ_01` | MAS | `fake` | 1,626 | $0.00 | `SIMULATION_ONLY` | 1.0 | 0.0000 | Deterministic mock simulation for harness validation. |
| `sim_cd_srdd_educ_01_r1` | `srdd_educ_01` | ChatDev | `fake` | 3,000 | $0.00 | `SIMULATION_ONLY` | 1.0 | 0.4286 | Baseline mock simulation for harness validation. |
| `mas_srdd_educ_01_r1` | `srdd_educ_01` | MAS | `cohere/...` | 51,682 | $0.00 | `FAILED` | 0.0 | 0.0000 | Reviewer schema retry loop; unhandled Pydantic validation error. |
| `mas_srdd_educ_01_r1_attempt2` | `srdd_educ_01` | MAS | `cohere/...` | 62,871 | $0.00 | `STOPPED_BUDGET_CEILING` | 1.0 | 0.4286 | Post-hoc cap breach (pre-dispatch gate was not yet atomic). |
| `cd_srdd_educ_01_r1` | `srdd_educ_01` | ChatDev | `cohere/...` | 5,228 | $0.00 | `FAILED` | 0.0 | 0.0000 | Parser exception; WareHouse directory contaminated with mock files. |
| `mas_srdd_educ_01_r2` | `srdd_educ_01` | MAS | `cohere/...` | 62,178 | $0.00 | `STOPPED_BUDGET_CEILING` | 0.0 | 0.0000 | Post-hoc cap breach; halted cleanly. |
| `cd_srdd_educ_01_r2` | `srdd_educ_01` | ChatDev | `cohere/...` | 4,290 | $0.00 | `FAILED` | 0.0 | 0.0000 | Parser failed to extract codes; `main.py` missing. |
| `mas_srdd_educ_01_r1_attempt3` | `srdd_educ_01` | MAS | `cohere/...` | 58,690 | $0.00 | `STOPPED_BUDGET_CEILING` | 0.0 | 0.0000 | Generated `main.py` rejected `--help` (exit code 1); gate blocked Call 12 within 60k limit. |
| `cd_srdd_educ_01_r1_attempt2` | `srdd_educ_01` | ChatDev | `cohere/...` | 4,385 | $0.00 | `FAILED` | 0.0 | 0.0000 | `ValueError: No Valid Codes.`; reasoning token depletion & `<INFO>` stripping. |

### Canonical Benchmark Status
- **Canonical Completed Live MAS Runs:** 0 (all historical attempts halted at budget ceiling or failed prior to fix).
- **Canonical Completed Live ChatDev Runs:** 0 (all historical attempts failed prior to parser and proxy fixes).
- **Completed Paired Benchmark Observations:** **0**.

---

## 5. Known Limitations & Research Transparency

1. **Free-Tier Model Rate Limits:** Public free-tier model providers impose stringent request and transmission throttles (e.g., 45 requests per rolling day on OpenRouter). Full 300-run evaluations require staged multi-day execution or dedicated enterprise provisioned throughput.
2. **Reasoning Token Overhead:** Modern reasoning/code models allocate output tokens dynamically between hidden reasoning and visible completion. Without explicit `"reasoning": {"max_tokens": 0}` suppression, code generation is vulnerable to truncation.
3. **Absence of Fabricated Claims:** In accordance with academic honesty standards, MAS does **not** claim empirical superiority over ChatDev on live benchmarks until the first valid paired observation is executed and verified under the frozen evaluator.
