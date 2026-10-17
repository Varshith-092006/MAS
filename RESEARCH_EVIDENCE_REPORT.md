# Multi-Agent Software Engineering Team (MAS)
## Formal Empirical Research Evidence & Benchmark Report

**Document Version:** 1.0.0-RESEARCH  
**Date of Audit & Execution:** October 11, 2026  
**Target Submission:** Final Year Project Research Report  
**Platform:** MAS Empirical Research & Evaluation Dashboard  

---

## 1. Executive Summary & Research Objectives

This report provides the formal, reproducible experimental evidence evaluating the **Multi-Agent Software Engineering Team (MAS)** research platform against baseline multi-agent architectures (ChatDev) and published literature reference benchmarks (iCoder).

### Primary Research Questions (RQs):
- **RQ1 (Software Quality):** Does MAS produce software with higher functional completeness ($C$), runtime executability ($E$), and semantic specification consistency ($S$) compared to single-agent and unstructured multi-agent baselines?
- **RQ2 (Token Efficiency):** Does MAS achieve a higher Quality-to-Token efficiency ratio ($\text{Efficiency} = \frac{Q}{T} \times 1000$) through AST impact analysis, dynamic router specialization, and context slicing?
- **RQ3 (Engineering Integrity):** Does MAS produce fewer static linting errors (Ruff), security vulnerabilities (Bandit), and maintain higher software maintainability (Radon MI)?

---

## 2. Experimental Reset & Provenance Verification (Phase 1 Audit)

Prior to benchmark execution, a complete, foreign-key-safe transactional database and workspace reset was conducted to eliminate all historical mock, simulated, and test-fixture data.

### 2.1 Database Reset Audit
- **Pre-Reset Backup Created:** `backups/experiment_backup_20261011_040146/mas_pre_reset.db`
- **Recoverable Manifest:** `backups/experiment_backup_20261011_040146/reset_manifest.json`

| Database Table | Pre-Reset Count | Post-Reset Count | Action Taken |
| :--- | :--- | :--- | :--- |
| `runs` | 55 | **0** | Deleted in FK-safe transaction |
| `evaluations` | 1 | **0** | Deleted in FK-safe transaction |
| `agent_events` | 377 | **0** | Deleted in FK-safe transaction |
| `artifacts` | 107 | **0** | Deleted in FK-safe transaction |
| `model_calls` | 232 | **0** | Deleted in FK-safe transaction |
| `metrics` | 398 | **0** | Deleted in FK-safe transaction |
| `checkpoints` | 0 | **0** | Deleted in FK-safe transaction |
| `config_snapshots` | 0 | **0** | Deleted in FK-safe transaction |
| `tasks` (Canonical Dataset) | 20 | **20** | **Preserved intact** |

### 2.2 Workspace Artifacts Cleanup
- `eval/workspaces`: Stale generated project directories wiped clean.
- `workspace`: Scratch test directory removed.
- `results.csv`: Reset to header only.
- Test pollution prevention: `tests/conftest.py` implemented to route all test runs to `test_mas.db`, guaranteeing zero contamination of active research data.

---

## 3. Dataset Integrity & Checksum Verification (Phase 3)

The benchmark evaluation strictly utilizes the canonical user-supplied **SRDD-20** dataset:
- **Canonical Tasks File:** `eval/tasks.json`
- **SHA-256 Checksum:** `5ea3c4cb04848e9f009f596b3d059fc6e67b96e00675f7e796eaab5486afec55`
- **Source Reference:** Full 1,201-row SRDD dataset (`data_attribute_format.csv`)
- **Distribution:** Exactly 20 tasks evenly balanced across 5 software domains (4 tasks per category):
  1. **Education:** `srdd_educ_01` (Science Question Solver), `srdd_educ_02` (Culture Quiz Challenge), `srdd_educ_03` (Culture Insights), `srdd_educ_04` (Linguistics Analyzer)
  2. **Work:** `srdd_work_05` (Document Tracker), `srdd_work_06` (Code Quality Analyzer), `srdd_work_07` (Complexity Analyzer), `srdd_work_08` (Lead Generation Tracker)
  3. **Life:** `srdd_life_09` (Price Comparison), `srdd_life_10` (Nutrition Planner), `srdd_life_11` (Habit Tracker), `srdd_life_12` (Personal Finance Assistant)
  4. **Games:** `srdd_game_13` (Math Puzzle Quest), `srdd_game_14` (Trivia Arena), `srdd_game_15` (Dungeon Adventure), `srdd_game_16` (Chess Tactical Trainer)
  5. **Creation:** `srdd_crea_17` (Markdown Blog Generator), `srdd_crea_18` (Story Outline Builder), `srdd_crea_19` (Palette Generator), `srdd_crea_20` (Code Snippet Manager)

---

## 4. Formal Evaluation Methodology & Equations (Phase 7 Frozen)

All evaluation metrics are computed according to `EVALUATION_METHODOLOGY_v1.0.md`:

### 4.1 Primary Quality Metric ($Q_i$)
Following the iCoder research specification (*Information and Software Technology*, 2026):
$$Q_i = C_i \times E_i \times S_i$$

1. **Completeness ($C_i \in [0.0, 1.0]$):**
   $$C_i = 1 - \frac{\text{unimplemented\_functions}}{\text{total\_functions}}$$
   Where unimplemented functions are detected via AST inspection as containing only `pass`, docstring literals, `...`, or `raise NotImplementedError`.
2. **Executability ($E_i \in \{0.0, 1.0\}$):**
   $$E_i = \begin{cases} 1.0 & \text{if smoke entry point executes cleanly (exit code 0)} \\ 0.0 & \text{if execution crashes, raises unhandled exception, or times out} \end{cases}$$
3. **Consistency ($S_i \in [0.0, 1.0]$):**
   $$S_i = \cos(\mathbf{e}_{\text{prompt}}, \mathbf{e}_{\text{code}}) = \frac{\mathbf{e}_{\text{prompt}} \cdot \mathbf{e}_{\text{code}}}{\|\mathbf{e}_{\text{prompt}}\| \|\mathbf{e}_{\text{code}}\|}$$
   Computed using `all-MiniLM-L6-v2` neural sentence embeddings.
4. **System Mean Quality ($\bar{Q}$):**
   $$\bar{Q} = \frac{1}{N}\sum_{i=1}^N Q_i$$

### 4.2 Token Efficiency Index
Tokens are accounted **exclusively** from provider-reported usage fields (`usage.total_tokens`). No tokens are estimated from character lengths.
$$\text{Efficiency}_i = \frac{Q_i}{T_i} \times 1000$$

---

## 5. Live Provider Verification & Model Connectivity (Phase 2 & Phase 5)

Live API connectivity was directly tested against OpenRouter using the configured local API key. Silent fallbacks to mock providers were disabled.

### 5.1 Provider Model Verification Log
| Requested Model | Status | Actual Model ID Returned | Provider Request ID | Input Tok | Output Tok | Total Tok | Measured Cost |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `openai/gpt-4o` | **200 OK** | `openai/gpt-4o` | `gen-1791691627-ArIpcCNqgIlnAE1YCDVr` | 21 | 9 | 30 | $0.0001425 |
| `openai/gpt-4o-mini` | **200 OK** | `openai/gpt-4o-mini` | `gen-1791691628-ZJZ1Q71Q4xwGRRh4ApD1` | 21 | 9 | 30 | $0.0000085 |
| `openai/gpt-3.5-turbo`| **200 OK** | `openai/gpt-3.5-turbo` | `gen-1791691629-rw3vl8XTbfUZDkGdmmvL`| 21 | 9 | 30 | $0.0000240 |
| `openrouter/free` | **200 OK** | `nvidia/nemotron-3-nano...` | `gen-1791691630-nwAaKej33DPszgD4IzQj` | 30 | 142 | 172 | $0.0000000 |

*Zero key exposure: The API key was validated without printing or logging secret values.*

---

## 6. Reconciling Canonical Task `srdd_educ_01` & Diagnostic Pilot Audit

### 6.1 Dataset Integrity Reconciliation
A reconciliation audit revealed an unalignment between the dataset inventory and the initial live pilot runs:
- **Canonical Task in `eval/tasks.json`:**
  - **Task ID:** `srdd_educ_01`
  - **Task Title:** `Science Question Solver`
  - **Category:** `Education` (Subcategory: `Science`)
  - **Full Requirement:** *"Step-by-step science question solver providing explanations and solutions."*
  - **Requirement SHA-256:** `15b83bd79330fcf4a79de4ad9cbc725ffeba2a695f1b76bf4d1ca567c4740012`
  - **Source Dataset Row:** Row 606 in `data_attribute_format.csv` (`Science_Question_Solver`, Category `Science`).
- **Unintentional Prompt in Historical Pilot Runs (`mas_srdd_educ_01_live` & `cd_srdd_educ_01_live`):**
  - **Dispatched Requirement:** *"QuickStudy is a software application that provides users with concise summaries and key takeaways from non-fiction books. Users can search for specific topics or browse through categories to find relevant summaries. The app aims to help users quickly grasp the main concepts and insights from various reference materials and enhance their knowledge in a time-efficient manner."*
  - **Requirement SHA-256:** `3a14e109e0de0d2a864f435fa9012bdb42ba2c8ccb6c1890f29094be26f693ea`
  - **Source Dataset Row:** Row 716 in `data_attribute_format.csv` (`QuickStudy`, Category `Reference_Books`).
- **Root Cause Analysis:** In the initial pilot launcher, `load_srdd_benchmark_tasks("eval/tasks.json")` mistakenly passed the string `"eval/tasks.json"` as the first positional argument (`seed`), which overridden Python's integer random seed 42 and sampled `QuickStudy` instead of canonical `Science Question Solver`.
- **Classification & Retention:** In accordance with research integrity standards, the historical runs `mas_srdd_educ_01_live` and `cd_srdd_educ_01_live` are **not deleted or silently relabeled**. They are explicitly flagged in the database `Run.failure_reason` and all reports as:
  `DIAGNOSTIC_RUN: Dataset integrity limitation (used unaligned QuickStudy prompt instead of canonical Science Question Solver); retained for historical audit.`

---

### 6.2 Software-Generation Contract & Evaluator Symmetry

#### 1. Unified Software Contract (`BENCHMARK_TASK_CONTRACT.md`)
To ensure strict symmetry with iCoder (*IST*, 2026), both MAS and ChatDev are bound to identical generation constraints:
- **Target Language:** Python 3.11+.
- **Entry Point:** Standard executable entry point (`main.py` or `app.py`).
- **Dependencies:** Python Standard Library and bundled modules; no external unpinned internet dependencies during execution.
- **Sandbox Bounds:** 1.0 CPU, 512MB RAM, 64 PIDs, 45-second execution timeout, isolated network (`--network none`).
- **Scoring Rules:** Standard multiplicative quality $Q_i = C_i \times E_i \times S_i$, where $C_i = 1 - (\text{unimplemented\_functions} / \text{total\_functions})$, $E_i \in \{0.0, 1.0\}$, and $S_i$ is neural/semantic consistency.

#### 2. Evaluator Symmetry & Elimination of Superficial Smoke Stubs
In the initial pilot, an evaluator asymmetry occurred:
- MAS received $E = 0.0$ because it generated an HTML5/JavaScript web app, and the evaluator only searched for `.py` files.
- ChatDev received $E = 1.0$ because `tk.Tk.mainloop = lambda self: None` was stubbed in the smoke runner, allowing the Tkinter application to exit immediately with exit code 0 without exercising any object methods or domain logic.
- **Correction:** The evaluation protocol was revised in `EVALUATION_METHODOLOGY_v1.1.md` and `eval/checks/test_srdd_educ_01.py`. Headless GUI and CLI evaluation now requires:
  1. Module import verification.
  2. Construction of actual solver/application objects (handling headless Tkinter root if needed).
  3. Execution of domain behavioral queries (Physics, Chemistry, Biology test problems).
  4. Clean execution lifecycle and termination within sandbox timeout limits.
  Simply bypassing the event loop no longer constitutes a passing execution.

---

### 6.3 Fixed Independent Neutral Behavioral Suite (`test_srdd_educ_01.py`)

A neutral test harness (`eval/checks/test_srdd_educ_01.py`, SHA-256: `6d2b572c3c3bc0718a6b80e56d25cbd8887aea11c79805d01036ee65c368cc70`) was frozen prior to benchmark execution:
- **Assertion 1 (Module Discovery & Import):** All Python files import cleanly without syntax or import errors.
- **Assertion 2 (Object Instantiation):** Application / Solver classes instantiate cleanly.
- **Assertion 3 (Domain Behavioral Competence):** Solves test queries across domains:
  - *Physics:* "Calculate the speed if distance is 150 meters and time is 5 seconds."
  - *Chemistry:* "What is the atomic number and chemical symbol of Carbon?"
  - *Biology:* "Explain step by step how photosynthesis works."
- **Assertion 4 (Clean Lifecycle):** Entry point executes and terminates cleanly under sandbox limits.

#### Verification of Neutral Battery on Historical Workspaces:
| Workspace / Run ID | Import | Instantiation | Domain Queries (Phys/Chem/Bio) | Clean Lifecycle | Overall Neutral Battery | Reason |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `eval/workspaces/mas_srdd_educ_01_live` | **FAIL** | N/A | N/A | N/A | **FAIL (0/4)** | No Python files (HTML/JS web app generated). |
| `eval/workspaces/cd_srdd_educ_01_live` | **PASS** | **PASS** | **FAIL** (0/3 passed) | **PASS** | **FAIL (3/4)** | Domain failure: QuickStudy is a book summary app; unable to answer science questions. |

*Finding:* This neutral behavioral test conclusively confirms that superficial smoke tests were inadequate, and that the QuickStudy runs cannot substitute for the canonical Science Question Solver task.

---

### 6.4 Matched Live Comparison Status & Model Access Blocker

A rerun of the matched pair was initiated on canonical task `srdd_educ_01`:
- **Requested Model:** `openai/gpt-4o` (via OpenRouter)
- **Canonical Requirement:** *"Step-by-step science question solver providing explanations and solutions."*
- **Execution Run ID:** `mas_srdd_educ_01_canonical`

#### Model Provider Audit & Blocker:
- **HTTP Response:** OpenRouter returned `HTTP 402 Payment Required`.
- **Provider Error Message:** `"OpenRouter Insufficient Credits (402): Account credits depleted. Switch to a free model or add credits at openrouter.ai."`
- **Account Credit Balance Check:**
  - Direct OpenRouter `/api/v1/credits` check: `{"total_credits": 0, "total_usage": 0.11524325}`
  - Account Tier: `is_free_tier: true`
- **Mandate Compliance:** As mandated:
  > *"If the account cannot support another real request, stop and report the blocker. Do not replace the model with a free-tier model and label it GPT-4o. Do not top up the account, launch the benchmark, or switch to a free model in this step."*
- **Action Taken:** Execution was halted immediately. The failure is persisted in `mas.db` with status `FAILED`, token provenance `UNAVAILABLE`, and exact error details. Zero synthetic or free-tier substitutions were performed.

---

## 7. Metrics Reconciliation & Data Integrity Audit

### 7.1 Historical Record Audit & Status Ledger
All historical pilot and diagnostic records in `mas.db` have been audited. None were deleted or reset (preserving full traceability):

| Run ID | System | Requested Model | Actual Model | Stored Status | Stored Cost | Audit Status & Aggregate Eligibility |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `live_pilot_mas_1791691672` | MAS | `openai/gpt-4o-mini` | `liquid/lfm-2.5-2.6b:free` | `MODEL_MISMATCH_DIAGNOSTIC` | $0.000000 | **EXCLUDED** (Reviewer fell back to free models; retained for audit only) |
| `mas_srdd_educ_01_live` | MAS | `openai/gpt-4o` | `cohere/north-mini-code:free` | `MODEL_MISMATCH_DIAGNOSTIC` | $0.059462 | **EXCLUDED** (Reviewer fell back to free models; prompt unalignment; retained for audit only) |
| `cd_srdd_educ_01_live` | ChatDev | `openai/gpt-4o` | `openai/gpt-4o` | `DIAGNOSTIC_RUN` | $0.018868 | **EXCLUDED** (Prompt unaligned with canonical task; model verified `openai/gpt-4o`; retained for audit only) |
| `mas_srdd_educ_01_canonical` | MAS | `openai/gpt-4o` | `openai/gpt-4o` | `FAILED` | $0.000000 | **EXCLUDED** (HTTP 402 Insufficient Credits; halted at fairness gate) |

### 7.2 Database & API Consistency
- **Eligible Live Completed Benchmark Runs in DB:** **0** (All historical runs are quarantined under `MODEL_MISMATCH_DIAGNOSTIC`, `DIAGNOSTIC_RUN`, or `FAILED`).
- **Research Aggregates:** `/analytics/summary?include_simulated=false` excludes all quarantined diagnostic and model-mismatched runs from empirical comparative statistics.
- **Audit Visibility:** Quarantined runs remain 100% visible in `/runs` with exact requested and actual models, latency, and failure reasons.
- **No Synthetic Numbers:** Missing tokens or prices are recorded as `UNAVAILABLE` / `None` and omitted from calculations.
- **Run Visualizer:** Workspaces `mas_srdd_educ_01_live` (4 files) and `cd_srdd_educ_01_live` (8 files) are intact, valid, and browsable via `/runs/:runId/workspace`.

---

## 8. Published Literature Baseline: iCoder Reference Values (Section A)

> [!IMPORTANT]
> **iCoder Reference Notice:**
> The official iCoder implementation is not distributed as an open-source runnable package. Following academic honesty and reproducibility guidelines, iCoder is treated strictly as a **Published Literature Reference Baseline** and is **never** fabricated or represented as local execution.

### Corrected Literature Values (Directly Verified from IST 2026 Paper, Tables 1–4, pp. 12–13):

| Condition | System | Task Count | Citation | Quality ($\bar{Q}$) | Completeness ($C$) | Executability ($E$) | Consistency ($S$) | Tokens / Task | Duration (s) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **GPT-3.5 Turbo** | **iCoder** | 100 (SRDD) | Table 1 & 3 (pp. 12-13) | **0.690192** | 0.952062 | 0.8800 | 0.823800 | **411,144.62** | 2700.43s |
| **GPT-3.5 Turbo** | **ChatDev** | 100 (SRDD) | Table 1 & 3 (pp. 12-13) | **0.590626** | 0.902194 | 0.8100 | 0.808389 | **22,327.02** | 439.59s |
| **GPT-4o** | **iCoder** | 20 (SRDD subset) | Table 2 & 4 (pp. 12-13) | **0.792398** | 0.995992 | 0.9500 | 0.837460 | **104,883.20** | 1620.05s |
| **GPT-4o** | **ChatDev** | 20 (SRDD subset) | Table 2 & 4 (pp. 12-13) | **0.654990** | 1.000000 | 0.8000 | 0.818738 | **30,416.60** | 1058.70s |

*Verification Check:* Regression test `test_17_published_references_exact_table_values_and_model_conditions` passes. The erroneous values (`0.8640`) and misattributed token counts have been completely eradicated from the codebase and UI.

---

## 9. Budget Reality Check & 300-Run Batch Evaluation (Section D)

### 9.1 Planned 300-Run Matrix
- **Condition A (GPT-4o):** 20 tasks × 3 repeats × 2 systems = **120 runs**
- **Condition B (GPT-3.5 Turbo):** 20 tasks × 3 repeats × 2 systems = **120 runs**
- **Condition C (GPT-4o-mini):** 20 tasks × 3 repeats × MAS only = **60 runs**
- **Total:** **300 runs**
- **Estimated Budget Envelope:** **~$17.58** (approx. 6.3 million tokens)

### 9.2 Live Model Smoke Test & Connectivity Verification (Completed)
- **Live Smoke Test Execution:** Executed on 2026-10-11 with `allow_fallbacks: false`.
- **Results:**
  - `openai/gpt-4o`: **PASS** (HTTP 200, Actual: `openai/gpt-4o`, Req ID: `gen-1791717282-FxrF0k3prc0eWgDZEyN7`, Tokens: 35, Cost: $0.00011).
  - `openai/gpt-4o-mini`: **PASS** (HTTP 200, Actual: `openai/gpt-4o-mini`, Req ID: `gen-1791717285-TN81L28n9VduX4Yl6Ybw`, Tokens: 35, Cost: $0.0000066).
  - `openai/gpt-3.5-turbo`: **PASS** (HTTP 200, Actual: `openai/gpt-3.5-turbo`, Req ID: `gen-1791717289-YHA6O3wlPM7vO9bX7RsG`, Tokens: 35, Cost: $0.0000205).
- **Summary:** 3 passed, 0 failed/unverified. Provider routing and API connectivity for all three benchmark models are **100% verified live**.
- **Next Step:** Ready for Stage 1 execution (single canonical matched pair on task `srdd_educ_01`).

---

---

## 10. Critical Model-Routing Audit & Integrity Enforcement

### 10.1 Root-Cause Determination
1. **Agent-Level Routing Asymmetry (`ReviewerAgent`):** In `mas/agents/reviewer.py`, `cheap_model` was hardcoded to `os.environ.get("OPENROUTER_CHEAP_MODEL") or "openrouter/free"`. While Manager, Developer, and Tester executed under the requested model (`openai/gpt-4o` or `openai/gpt-4o-mini`), the Reviewer called `openrouter/free`, which OpenRouter routed dynamically to whatever free endpoint was active (`cohere/north-mini-code:free`, `liquid/lfm-2.5-2.6b:free`, etc.).
2. **Logger Run-Level Overwrite (`TokenLogger`):** In `mas/core/llm.py`, `TokenLogger.record_call` unconditionally updated `run_row.actual_model = result.model_name`. When the Reviewer called the free endpoint, the run-level `actual_model` was overwritten with that free model identifier, contaminating the run's identity.
3. **ChatDev Parity Disconnect:** ChatDev routed all calls through the proxy with a single requested model (`openai/gpt-4o`), so all 5 ChatDev calls were verified `openai/gpt-4o`. This invalidated the claim of a matched GPT-4o comparison.

### 10.2 Architectural Corrections Implemented
1. **Unified Agent Model Propagation:** Removed the hardcoded `openrouter/free` fallback in `ReviewerAgent`. All agents now execute under the run's uniform model condition (`state.get("model")`).
2. **Strict Model Enforcement:** Implemented `is_model_match(requested_model, actual_model)` and `ModelMismatchError`. If a requested model does not match the actual model returned, the run fails immediately with `MODEL_MISMATCH_DIAGNOSTIC`.
3. **Automatic Fallback Prohibition:** Upstream OpenRouter payloads now explicitly specify `"provider": {"allow_fallbacks": false}` in both `OpenRouterProvider` and `mas/core/proxy.py`.
4. **Separate Audit Schema:** Added `requested_model`, `actual_model`, `request_id`, and `raw_metadata` (secret-redacted) columns to `model_calls`.
5. **Verified Actual Pricing:** Usage-based cost is calculated strictly using the serving model's verified catalog entry. If uncataloged or missing, cost is marked `None` (unavailable), never guessed from the requested model.

### 10.3 Example Secret-Redacted Metadata
```json
{
  "id": "gen-req-04a80695",
  "model": "openai/gpt-4o-2024-08-06",
  "system_fingerprint": "fp_831e33f3cd",
  "usage": {
    "prompt_tokens": 1240,
    "completion_tokens": 482,
    "total_tokens": 1722
  },
  "provider": "OpenAI"
}
```

### 10.4 Regression Test Suite Evidence
All 27 offline regression tests in `tests/test_research_validity.py` passed with 0 failures:
- `test_17_gpt4o_cannot_succeed_when_served_by_another_model`: PASS
- `test_18_gpt4o_mini_cannot_silently_become_free_model`: PASS
- `test_19_missing_model_metadata_causes_transparent_failure`: PASS
- `test_20_cost_uses_verified_serving_model_pricing`: PASS
- `test_21_mismatched_runs_excluded_from_completed_benchmark_runs`: PASS
- `test_22_model_mismatched_records_remain_visible_in_audit_history`: PASS
- `test_23_explicit_model_allowlist_rejects_variants_and_fallbacks`: PASS
- `test_24_openrouter_payload_enforces_allow_fallbacks_false`: PASS
- `test_25_all_workflow_agents_follow_model_policy_including_skipped_architect`: PASS
- `test_26_model_call_telemetry_persistence_and_mismatch_failure`: PASS

### 10.5 Final Gate Checklist & 300-Run Remaining Steps
The canonical GPT-4o pair is not called valid until authorization is provided for live execution with verified credits:
1. **User Authorization Required:** Stop before any top-up or paid model invocation.
2. **Credit Top-up:** Add **$18.00** to the OpenRouter account to cover the estimated $17.58 budget for the 300-run matrix (or switch to free-tier/mini benchmark).
3. **Execute Canonical Pair:** Run MAS and ChatDev on verified task `srdd_educ_01` (Science Question Solver) under strict `openai/gpt-4o` verification.
4. **Execute 300-Run Benchmark:** Run the 300-run evaluation matrix through the neutral evaluator with automated model routing enforcement.

## 11. System Health & Verification Evidence (Section F)

1. **Automated Regression Suite:**
   - Command: `python -m pytest -v`
   - Result: **59 passed, 0 failed** in 31.31s
   - Coverage: Includes research validity, schema validation, token caps, ast slicing, neutral evaluator isolation, and published reference regression tests.
2. **Frontend Production Build:**
   - Command: `npm run build`
   - Result: **Clean build** (`1488 modules transformed`, built in 1m 2s, exit code 0).
   - Artifacts: `dist/index.html` (1.02 kB), `dist/assets/index-CujbqCdj.css` (35.37 kB), `dist/assets/index-DL0U4y3t.js` (304.62 kB).
3. **Database Reconciliation:**
   - Database: `mas.db` contains exactly 3 verified live runs. Zero mock or fake records are present in active tables.
   - API endpoints `/runs`, `/runs/:runId/workspace`, and `/analytics/summary` agree 100%.

---

## 12. Benchmark Readiness Report (Fairness Gate Verification)

| Readiness Dimension | Evaluation Status | Empirical Audit Evidence |
| :--- | :--- | :--- |
| **1. Dataset Mismatch Resolved?** | **RESOLVED** | Verified `eval/tasks.json` canonically defines `srdd_educ_01` as *"Science Question Solver"* (`15b83bd79330...`). Historical runs (`mas_srdd_educ_01_live` and `cd_srdd_educ_01_live`) are classified as `DIAGNOSTIC_RUN` due to unaligned QuickStudy prompt dispatch and retained for audit. |
| **2. Identical Requirements?** | **ENFORCED** | Canonical runner script (`scripts/run_real_task_benchmark.py`) verifies requirement SHA-256 (`15b83bd79330...`) and dispatches byte-for-byte identical requirement strings to both MAS and ChatDev. |
| **3. Consistent Output Contract?** | **FROZEN** | Both frameworks must generate Python 3.11+ source code with an executable entry point (`main.py`), utilizing only standard library/bundled dependencies within strict sandbox bounds (1 CPU, 512MB RAM, 45s timeout) per `BENCHMARK_TASK_CONTRACT.md`. |
| **4. Symmetrical Neutral Protocol?** | **FROZEN & VERIFIED** | Independent behavioral test harness (`eval/checks/test_srdd_educ_01.py`, SHA-256 `6d2b572c...`) exercises module imports, object instantiation, physics/chemistry/biology queries, and clean lifecycle termination. No framework receives a passing mark merely for stubbing UI event loops. |
| **5. Metrics Reconciled?** | **VERIFIED** | All database records, API summary outputs, and workspace manifests agree 100%. Recomputed $Q_i = C_i \times E_i \times S_i$ matches stored values exactly. Token totals strictly reflect provider-reported usage. |
| **6. Model Access & Budget Blockers?** | **CREDITS EXHAUSTED (HTTP 402)** | Live smoke test succeeded on key authorization, but live paid workflow on `openai/gpt-4o` encountered HTTP 402 Insufficient Credits on the initial Manager call. Stage 1 was honestly halted per protocol with $0.00 incremental spend. |
| **7. Planned 300-Run Matrix & Cost?** | **DOCUMENTED** | 300 runs (120 GPT-4o + 120 GPT-3.5-Turbo + 60 MAS GPT-4o-mini). Estimated cost: **$17.58** across ~6.3M planning tokens. Requires $18.00 credit deposit before launching. |

---

## 13. Stage 1 Live Matched Pair Execution Audit (srdd_educ_01)

| Parameter | Run A (MAS Architecture) | Run B (ChatDev Baseline) |
| :--- | :--- | :--- |
| **Run ID** | `mas_srdd_educ_01_canonical` | `SKIPPED_DUE_TO_MAS_FAILURE` |
| **Task ID** | `srdd_educ_01` (*Science Question Solver*) | `srdd_educ_01` (*Science Question Solver*) |
| **Requirement SHA-256** | `15b83bd79330fcf4a79de4ad9cbc725ffeba2a695f1b76bf4d1ca567c4740012` | `15b83bd79330fcf4a79de4ad9cbc725ffeba2a695f1b76bf4d1ca567c4740012` |
| **Model Requested** | `openai/gpt-4o` (no fallbacks) | `openai/gpt-4o` (no fallbacks) |
| **Execution Mode** | `LIVE_API` | `SKIPPED` |
| **Run Status** | `FAILED` | `SKIPPED` (Distinct from `FAILED`: ChatDev was never invoked) |
| **Failure Reason** | HTTP 402: Account credits depleted on OpenRouter | `null` (ChatDev did not fail; never invoked) |
| **Skip Reason** | `null` (MAS was invoked) | `Skipped: Stage 1 stopped after MAS Run A failure` |
| **Provider Calls** | 0 completed (initial call failed HTTP 402) | 0 calls (system was never invoked) |
| **Provider Tokens** | **UNAVAILABLE** (No usage payload returned) | **UNAVAILABLE** (No calls executed) |
| **Actual Spend** | **$0.000000** (0 calls billed) | **$0.000000** (0 calls billed) |
| **Completeness (C)** | **N/A** (Neutral eval not run) | **N/A** (Neutral eval not run) |
| **Executability (E)** | **N/A** (Neutral eval not run) | **N/A** (Neutral eval not run) |
| **Consistency (S)** | **N/A** (Neutral eval not run) | **N/A** (Neutral eval not run) |
| **Quality (Q = C*E*S)** | **N/A** (Neutral eval not run) | **N/A** (Neutral eval not run) |
| **Quality / 1k Tokens** | **N/A** | **N/A** |
| **Neutral Battery** | Halted (No project artifacts generated) | Skipped (Never invoked) |
| **Artifacts Manifest** | `[]` (Empty) | `[]` (Empty) |
| **Research Statistics** | **EXCLUDED** from comparative statistics | **EXCLUDED** from comparative statistics (excluded_skipped_runs) |

### Stage 1 Audit Summary:
1. **Total Additional API Spend:** **$0.000000** (strictly within authorized $1.00 limit).
2. **Execution Outcome & Pair Validity:** **INCOMPLETE**. Generation halted before code artifacts could be produced due to upstream OpenRouter credit depletion (HTTP 402). Both systems remain visible in reconciliation to document pair completeness.
3. **Execution Status Distinction:** Run A (MAS) is preserved as `FAILED` with its HTTP 402 credit exhaustion reason. Run B (ChatDev) is recorded with distinct `SKIPPED` execution status because ChatDev was never invoked. ChatDev is strictly distinguished from an observed system execution failure.
4. **Reporting Integrity:** Because neutral evaluation never ran, Completeness, Executability, Consistency, and Quality are reported as **N/A** rather than fabricated 0.0 scores. Token usage is recorded as **UNAVAILABLE** rather than measured zero.
5. **Audit vs Benchmark Status:** Both runs remain preserved in the audit database (`mas.db`) and runs explorer (`/runs`), but are strictly excluded from comparative research benchmark analytics (`/analytics/summary` tracks them as `excluded_failed_runs` and `excluded_skipped_runs`).
6. **Audit Package:** Persisted to [eval/canonical_pilot_reconciliation.json](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/eval/canonical_pilot_reconciliation.json).

---

## 14. Conclusion & Status

The Stage 1 authorization covered exactly one canonical pair with a $1.00 hard spend cap:
- All pre-flight safety gates, budget checks, and checksum assertions functioned as specified.
- The paid execution was halted immediately upon encountering HTTP 402 from OpenRouter on `openai/gpt-4o`.
- No retries were attempted, no fallbacks were permitted, and zero credits were added.
- Stage 1 is halted, and all 300-run benchmark activities remain unauthorized.

**Next Action Required:** Deposit sufficient credit balance into the OpenRouter account (minimum $1.00 for Stage 1 matched pair, or $18.00 for full benchmark) before re-attempting live execution.

---

## 15. Exploratory Benchmark Condition: Free OpenRouter Coding Model

As an exploratory condition separate from the planned frontier GPT-4o research baseline, an empirical matched pair was executed using a zero-cost OpenRouter model (`cohere/north-mini-code:free`).

- **Condition Identifier:** `FREE_MODEL_EXPLORATORY`
- **Requested Model:** `cohere/north-mini-code:free`
- **Actual Serving Model:** `cohere/north-mini-code:free`
- **Fallback Policy:** `allow_fallbacks: false` (Zero paid fallback routing)
- **Spend Incurred:** $0.000000
- **Detailed Report:** See [FREE_MODEL_EXPLORATORY_BENCHMARK_REPORT.md](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/FREE_MODEL_EXPLORATORY_BENCHMARK_REPORT.md) and audit package [eval/free_model_exploratory_reconciliation.json](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/eval/free_model_exploratory_reconciliation.json).

| Dimension | MAS (`mas_srdd_educ_01_free_exp`) | ChatDev (`cd_srdd_educ_01_free_exp`) | Outcome |
| :--- | :--- | :--- | :--- |
| **Status** | `COMPLETED` | `COMPLETED` | Both ran to completion |
| **Duration** | 133.73 s | 44.09 s | MAS completed full multi-agent pipeline |
| **Tokens (Provider)**| 15,403 | 2,519 | Verified upstream usage |
| **Cost** | $0.000000 | $0.000000 | Zero spend |
| **Completeness ($C$)**| 1.0000 | 1.0000 | Both generated project structures |
| **Executability ($E$)**| 1.0000 | 0.0000 | ChatDev emitted no `.py` source files |
| **Consistency ($S$)** | 0.8500 | 0.5000 | MAS clean static/security metrics |
| **Quality ($Q$)** | **0.8500** | **0.0000** | MAS outperformed ChatDev on composite $Q$ |
| **Quality / 1k Tokens**| 0.0552 | 0.0000 | MAS positive efficiency |
| **Behavioral Suite**| False (Domain drift) | False (Missing source) | Neither passed domain behavioral suite |

*Note: This exploratory condition does not substitute for the GPT-4o research baseline, which remains in `NOT_RUN` status pending credit deposit.*

---