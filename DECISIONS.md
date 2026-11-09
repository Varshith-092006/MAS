# Architecture and Design Decisions (DECISIONS.md)

This document tracks architectural decisions, source precedence, specification conflicts, chosen defaults, model configurations, evaluation constraints, and security policies for **MAS (Multi-Agent Software Engineering Team)**.

---

### Record: Provider Config Safety, Precedence, and OpenRouter Exclusion

- **ID**: DEC-013
- **Date**: 2026-11-10
- **Decision**: Google Gemini API is the sole authorized provider for official benchmark results. OpenRouter is explicitly excluded. A new module `eval/provider_config.py` enforces this.
- **Context & Reason**:
  - The previous `.env.example` and preflight were OpenRouter-centric, letting an OpenRouter key pass the key check and OpenRouter model IDs (e.g. `google/gemini-3.5-flash-lite` with the owner prefix) pass the model check. This made it possible to run the benchmark on the wrong provider without any error.
  - The free-tier constraint (AGENTS.md) pins the provider to **Google AI Studio** (aistudio.google.com) because:
    1. OpenRouter imposes a free-tier daily cap of ~50 requests on its proxy layer, far below the Gemini free tier's 500/day.
    2. OpenRouter results cannot be reproduced independently (the router may change which model serves a request), violating the benchmark reproducibility requirement.
    3. The Gemini API provides a direct, deterministic, rate-limited endpoint that is stable across days.
  - Safety rules added in `eval/provider_config.py` and `eval/runner.py`:
    1. `PROVIDER_*` vars take precedence over `OPENROUTER_*` when any `PROVIDER_*` var is non-empty.
    2. Live/benchmark runs refuse to start if `BENCH_MODEL` is empty, `openrouter/free`, or a placeholder.
    3. Provider type is detected from `PROVIDER_BASE_URL` host only.
    4. For the Gemini provider: the key must start with `AIza`; a `sk-or-` key is immediately rejected; the `google/` model prefix is a warning that is normalized away.
    5. For the OpenRouter provider: benchmark runs are blocked unless `--allow-openrouter` is passed (in which case results rows are labeled `provider=openrouter` and excluded from official tables).
    6. `scripts/list_models.py` now prints `Provider: <type> (<host>)` at the top.
    7. `scripts/make_report.py` checks that all official rows share the same provider and model and aborts if they differ, naming the conflicting values.
- **Impact**: Running `--preflight` or `--benchmark --live` with an OpenRouter key on the Gemini URL (or vice versa) now produces a clear `[FAIL]` error before any quota is spent.
- **Evaluator frozen**: eval/neutral_evaluator.py unchanged.

---

### Record: Source Precedence and Input Limitation

- **ID**: DEC-001
- **Date**: 2026-10-06
- **Decision**: Precedence hierarchy and input limitation handling.
- **Source**: System instructions and Workspace inventory.
- **Context & Reason**:
  - Expected primary document: `MAS_Documentation_v3.md`.
  - Directory search confirmed `MAS_Documentation_v3.md` is **missing** from the workspace.
  - Workspace contains `Documentation for Building.pdf` ("MAS Multi-Agent Software Engineering Team 7-Day MVP Research Documentation — Revised", 7 pages), `LLD.pdf` (Low Level Design, 42 pages), `HLD.pdf` (High Level Design, 19 pages), and `iCoder` research paper.
  - **Input Limitation Recorded**: In accordance with system instructions ("if MAS_Documentation_v3.md is missing, report that as an input limitation before proceeding"), `Documentation for Building.pdf` is adopted as the primary revised specification of truth, followed by `LLD.pdf` (Priority 2 for classes, algorithms, schema, APIs) and `HLD.pdf` (Priority 3 for system boundaries and architecture).
- **Impact**: All specifications adhere strictly to `Documentation for Building.pdf` and `LLD.pdf`.

---

### Record: Deterministic Complexity Router Rules and Thresholds

- **ID**: DEC-002
- **Date**: 2026-10-06
- **Decision**: Zero LLM calls in Router; score 0–3 is `SIMPLE`, score 4+ is `STRUCTURED`.
- **Source**: `Documentation for Building.pdf` (Doc 2, Sec 5), `LLD.pdf` (Sec 7.1).
- **Context & Reason**:
  - The Router must not call any language model.
  - Regex rules detect:
    1. Persistence / database
    2. Authentication / login / accounts
    3. Multiple roles / permissions
    4. External integrations / APIs / HTTP
    5. Analytics / metrics / reporting
    6. Workflow / state machine
  - Structural separators: `,`, ` and `, `;`, bullet points (`•`, `-`, `*`, `\d+\.`).
    - Count $\ge 7 \implies +2$
    - Count $\ge 4 \implies +1$
  - Requirement length: word count $> 80 \implies +1$.
- **Impact**: Fast, zero-token routing between simple single-shot developer flow and structured architect-driven flow.

---

### Record: Inter-Agent Artifact Contracts and JSON Schema Validation

- **ID**: DEC-003
- **Date**: 2026-10-06
- **Decision**: Canonical Pydantic models with exported JSON Schemas for 7 core artifacts.
- **Source**: `Documentation for Building.pdf` (Doc 2, Sec 4), `LLD.pdf` (Sec 7.5).
- **Context & Reason**:
  - Required artifacts: `TaskPlan`, `UserStory`, `Architecture`, `CodePatch`, `ReviewReport`, `TestReport`, `ReflectionDecision`.
  - Pydantic models are canonical. JSON Schema is exported and checked at runtime.
  - On validation error:
    1. Producer agent is retried once with validation error feedback.
    2. If retry fails: rollback workspace to last valid Git checkpoint.
    3. Rerun producer from rolled-back state.
    4. If still invalid: fail the run with reason `ARTIFACT_INVALID`.
- **Impact**: Malformed artifacts are never passed downstream; all validation errors, retries, and rollbacks are recorded in append-only events.

---

### Record: Database Schema and Scope Separation

- **ID**: DEC-004
- **Date**: 2026-10-06
- **Decision**: 9 tables according to LLD Section 4.2; strict separation between `neutral` and `internal` metrics.
- **Source**: `LLD.pdf` (Sec 4.2, 4.4), `Documentation for Building.pdf` (Doc 2, Sec 10).
- **Context & Reason**:
  - Tables: `tasks`, `evaluations`, `runs`, `agent_events`, `artifacts`, `checkpoints`, `model_calls`, `metrics`, `config_snapshots`.
  - `agent_events` is append-only.
  - `metrics` has a `scope` column:
    - `neutral`: metrics for direct cross-system comparison with ChatDev (Completeness, Executability, Consistency, Quality, Shared test, Ruff, Bandit, Radon).
    - `internal`: MAS diagnostic metrics (MAS pytest pass rate, pytest coverage, adaptive score).
  - Explicitly excluded: `users`, `roles`, `audit_logs`, JWT authentication.
  - Supports SQLite for lightweight local testing and PostgreSQL for production Docker deployment.
- **Impact**: Zero contamination of cross-system comparison from MAS internal diagnostics.

---

### Record: LLM Provider, Logging Proxy, and Token Measurement

- **ID**: DEC-005
- **Date**: 2026-10-06
- **Decision**: Single `LLMProvider` interface; measured tokens derived solely from provider API usage fields.
- **Source**: `Documentation for Building.pdf` (Doc 2, Sec 12, Doc 3, Sec 5), `LLD.pdf` (Sec 3.2.9).
- **Context & Reason**:
  - `LLMProvider.generate(...)` implemented by `OpenAIProvider` and `FakeLLMProvider`.
  - All calls (MAS and ChatDev) go through a local logging proxy.
  - Proxy and provider record: `input_tokens`, `output_tokens`, `total_tokens`, `latency_ms`, `request_id`, `estimated_cost`.
  - Under no circumstances are token counts derived from character length or local tokenizers.
  - Per-run engineering token cap: 60,000 tokens. If exceeded, run is marked `FAILED` with `TOKEN_CAP_EXCEEDED` and preserved in results.
- **Impact**: Strict experimental validity and reproducible token auditing.

---

### Record: Adaptive Stopping Policy

- **ID**: DEC-006
- **Date**: 2026-10-06
- **Decision**: Stopping rule uses internal MAS signals only; neutral evaluator is never imported or called.
- **Source**: `Documentation for Building.pdf` (Doc 2, Sec 8), `LLD.pdf` (Sec 7.4).
- **Context & Reason**:
  - Formula:
    $CE_t = 0.5 \times (\text{Completeness}_t + \text{Executability}_t)$
    $S_t = 0.30 \times \text{InternalTest}_t + 0.10 \times \text{Ruff}_t + 0.15 \times \text{Bandit}_t + 0.10 \times \text{Radon}_t + 0.15 \times \text{Reviewer}_t + 0.20 \times CE_t$
    $\Delta_t = S_t - S_{t-1}$
  - Defaults: $\text{STOP\_EPSILON} = 0.02$, $\text{PATIENCE} = 2$, $\text{MAX\_ITERATIONS} = 3$.
  - Stop conditions:
    1. Clean result (no critical defects and internal tests pass).
    2. Marginal gain $\Delta_t < 0.02$ for 2 consecutive iterations.
    3. Reached maximum iterations (3).
- **Impact**: Token efficiency without premature termination on broken code.

---

### Record: Docker Sandbox Design and Isolated Execution

- **ID**: DEC-007
- **Date**: 2026-10-06
- **Decision**: Disposable container execution with `--network none`, 512 MB RAM, 1 CPU, 64 PIDs, read-only base image, writable `/workspace` mount only, and 30–60s execution timeout.
- **Source**: `Documentation for Building.pdf` (Doc 3, Sec 3), `LLD.pdf` (Sec 8.4).
- **Context & Reason**:
  - Host safety prevents generated code from making external network calls, modifying host systems, or installing arbitrary packages during evaluation.
  - Disposable container ensures isolated state.
  - Local subprocess sandbox fallback with clean environment and strict timeouts is provided for environments without active Docker daemons.
- **Impact**: Total host environment protection and reproducible sandbox execution.

---

### Record: AST Structural Review vs LLM Semantic Review Separation

- **ID**: DEC-008
- **Date**: 2026-10-06
- **Decision**: Deterministic Python `ast` module performs all structural analysis; GPT-4o-mini is restricted strictly to semantic review.
- **Source**: `Documentation for Building.pdf` (Doc 2, Sec 6), `LLD.pdf` (Sec 7.2).
- **Context & Reason**:
  - LLMs are unreliable and token-expensive at computing graph cycles, resolving local modules, and finding reverse dependencies.
  - ASTAnalyzer builds directed dependency graph, runs 3-color DFS cycle detection, resolves local modules, identifies unresolved imports, and calculates transitive reverse-dependency impact sets with 0 tokens.
  - GPT-4o-mini performs only requirement-to-code semantic alignment.
- **Impact**: Substantial token cost savings and 100% deterministic structural cycle detection.

---

### Record: Context Slicing Policy

- **ID**: DEC-009
- **Date**: 2026-10-06
- **Decision**: Iteration 1 sends planned files; subsequent iterations send only $\text{changed\_files} \cup \text{AST impact set}$, plus sliced UML.
- **Source**: `LLD.pdf` (Sec 7.3).
- **Context & Reason**:
  - Resending the entire codebase every round causes quadratic token growth as repository size expands.
  - ContextSlicer isolates only directly modified files and modules that depend transitively on those modifications.
- **Impact**: Keeps prompt token overhead minimal across iterative development rounds.

---

### Record: Isolation of Neutral Evaluator

- **ID**: DEC-010
- **Date**: 2026-10-06
- **Decision**: Neutral evaluator is situated entirely in `eval/` outside `mas/` package, and is never called during MAS runtime loops.
- **Source**: `Documentation for Building.pdf` (Doc 2, Sec 7), `LLD.pdf` (Sec 7.7).
- **Context & Reason**:
  - Prevents target metric leakage into agent prompt optimizations.
  - Evaluates both MAS and ChatDev outputs identically using:
    - Completeness
    - Executability
    - Consistency (`all-MiniLM-L6-v2`)
    - Shared Fixed Test (Level 1 + Level 2 checks)
    - Ruff, Bandit, Radon
- **Impact**: Unbiased empirical benchmarking and scientific validity.

---

### Record: SRDD Task Set Selection Policy

- **ID**: DEC-011
- **Date**: 2026-10-06
- **Decision**: Fixed seed 42 selects exactly 4 tasks per category across Education, Work, Life, Games, and Creation (20 tasks total).
- **Source**: `Documentation for Building.pdf` (Doc 2, Sec 13, Doc 5, Sec 1).
- **Context & Reason**:
  - The 20 tasks are saved to `eval/tasks.json` and persisted in the database `tasks` table once, remaining fixed for all benchmark runs.
- **Impact**: Consistent task baseline for all 3 repeats across MAS and ChatDev.

---

### Record: Pinned ChatDev Commit

- **ID**: DEC-012
- **Date**: 2026-10-06
- **Decision**: Pinned ChatDev commit `836f32e6584c3600f6c268a719c8f0f074d0ef9b` (v1.0.0 release).
- **Source**: System instructions and `Documentation for Building.pdf`.
- **Context & Reason**:
  - Eliminates variability caused by ongoing commits in ChatDev main branch.
  - Routes OpenAI API base URL to MAS local logging proxy to capture provider-reported token usage identically.
- **Impact**: Controlled, reproducible comparison against the primary baseline.

---

### Record: Core Benchmark Experiment Matrix & Planning Token Envelope

- **ID**: DEC-013
- **Date**: 2026-10-06
- **Decision**: 300 core model runs total (120 Main GPT-4o, 60 Cheaper MAS GPT-4o-mini, 120 Ablations A1–A6 on GPT-4o-mini). A0 is reference row from existing MAS repeats.
- **Source**: `Documentation for Building.pdf` (Doc 2, Sec 13, Doc 5).
- **Context & Reason**:
  - Engineering planning token envelope is 8.4M tokens (4.8M + 1.2M + 2.4M).
  - Explicitly labeled as an *engineering planning envelope*, not measured benchmark data.
  - `--dry-run` prints the matrix and token envelope with 0 model calls.
- **Impact**: Predictable token resource budgeting and clear ablation boundaries.

---

### Record: Statistical Methodology

- **ID**: DEC-014
- **Date**: 2026-10-06
- **Decision**: Two-sided paired permutation test ($\alpha = 0.05$, 10,000 trials) on task-level paired means across 3 repeats.
- **Source**: `Documentation for Building.pdf` (Doc 2, Sec 13), `LLD.pdf` (Sec 7.8).
- **Context & Reason**:
  - Non-parametric permutation test avoids distributional assumptions for code generation metrics.
  - Primary metrics: Quality and Quality per 1,000 tokens.
  - Reports: mean $\pm$ SD, median, Cohen's $d$, 95% confidence interval, and two-sided $p$-value.
- **Impact**: Rigorous statistical inference for academic publication standards.

---

### Record: Requirement Change Request and Obsolete Code Handling

- **ID**: DEC-015
- **Date**: 2026-10-06
- **Decision**: Change request flow computes requirement diff, finds seed modules, computes AST transitive impact set, updates only affected files, runs regression tests, and flags obsolete code.
- **Source**: `LLD.pdf` (Sec 6.3, 7.6).
- **Context & Reason**:
  - Eliminates full project rewriting on specification changes.
  - Preserves regression test verification and tracks unused functions.
- **Impact**: High token efficiency and backward compatibility during iterative requirements evolution.

---

### Record: Single-Route React Frontend Architecture

- **ID**: DEC-016
- **Date**: 2026-10-06
- **Decision**: Single route `/runs/:runId` built with React + Tailwind CSS, containing RunHeader, StatusBanner, AgentLog, MetricsTable, and TokenCostChart.
- **Source**: `Documentation for Building.pdf` (Doc 4, Sec 3-4).
- **Context & Reason**:
  - Excludes complex administrative dashboards or authentication pages.
  - Connects to REST API and WebSocket for live event streaming.
- **Impact**: Minimalist, high-performance UI tailored specifically for run inspection.

---

### Record: Canonical Task Identity Reconciliation & Diagnostic Pilot Status

- **ID**: DEC-017
- **Date**: 2026-10-11
- **Decision**: Canonical task `srdd_educ_01` is strictly anchored to `eval/tasks.json` as "Science Question Solver" (Requirement: *"Step-by-step science question solver providing explanations and solutions."*, SHA-256: `15b83bd79330fcf4a79de4ad9cbc725ffeba2a695f1b76bf4d1ca567c4740012`). The previous live pilot runs (`mas_srdd_educ_01_live` and `cd_srdd_educ_01_live`) are marked as `DIAGNOSTIC_RUN` due to dataset-integrity unalignment (they executed the non-canonical QuickStudy prompt) and are retained solely for audit history.
- **Source**: Fairness gate pre-benchmark audit.
- **Context & Reason**:
  - The string `"eval/tasks.json"` was accidentally passed as the `seed` argument to `load_srdd_benchmark_tasks()`, sampling row 716 (`QuickStudy`) instead of canonical row 606 (`Science Question Solver`, seed 42).
  - Canonical dataset is preserved intact; old reports are reconciled.
- **Impact**: Strict task identity integrity and byte-for-byte identical requirement dispatch across systems.

---

### Record: Unified Benchmark Software-Generation Contract

- **ID**: DEC-018
- **Date**: 2026-10-11
- **Decision**: Both MAS and ChatDev must adhere to a single unified software-generation contract (`BENCHMARK_TASK_CONTRACT.md`): Python 3.11+ executable artifacts with a standard entry point (`main.py`), Python standard library / bundled dependencies, and strict execution sandbox bounds (1 CPU, 512MB RAM, 45s timeout).
- **Source**: iCoder comparative protocol (*IST*, 2026).
- **Context & Reason**:
  - Eliminates language mismatch (MAS generating HTML/JS vs. ChatDev generating Python Tkinter).
  - Enforces identical expectations across both systems without special-case scoring exceptions.
- **Impact**: Standardized output expectations for fair, symmetrical benchmark execution.

---

### Record: Symmetric Neutral Evaluation & Fixed Behavioral Testing

- **ID**: DEC-019
- **Date**: 2026-10-11
- **Decision**: All candidate systems are evaluated using external, frozen neutral tests (`eval/checks/test_srdd_educ_01.py` and `NeutralEvaluator`). Smoke tests must exercise actual module imports, object instantiation, domain solving logic, and clean lifecycle termination, rather than passing solely by bypassing UI mainloop stubs.
- **Source**: Evaluator symmetry audit.
- **Context & Reason**:
  - ChatDev previously received $E=1.0$ because `tk.Tk.mainloop` was stubbed out without verifying domain functionality, while MAS received $E=0.0$ because only `.py` files were inspected.
  - Frozen primary metric $Q_i = C_i \times E_i \times S_i$ remains unchanged.
  - Level 2 neutral tests verify actual physics, chemistry, and biology queries before awarding passing marks.
- **Impact**: Rigorous, symmetric behavioral verification preventing superficial smoke passes.

---

### Record: Strict Model Routing Enforcement & Fallback Prohibition for Research Integrity

- **ID**: DEC-020
- **Date**: 2026-10-11
- **Decision**: Strict model condition enforcement and explicit prohibition of provider fallbacks for all benchmark runs. If a run or agent requests `openai/gpt-4o`, `openai/gpt-4o-mini`, or `openai/gpt-3.5-turbo`, the upstream provider response must be strictly verified against the requested condition (`is_model_match`). Upstream payloads explicitly disable fallbacks (`"provider": {"allow_fallbacks": false}`). If a mismatched model is returned or model metadata is omitted, `ModelMismatchError` is raised, the run is flagged as `MODEL_MISMATCH_DIAGNOSTIC`, and it is strictly quarantined and excluded from all valid empirical research aggregates. Usage-based cost is derived strictly from the verified actual serving model's pricing catalog (or marked `None` / unavailable if uncataloged), never fabricated from the requested model.
- **Source**: MAS Critical Model-Routing Audit.
- **Context & Reason**:
  - Audit of historical runs revealed that `ReviewerAgent` had a hardcoded default to `openrouter/free`, which OpenRouter routed to free models (`liquid/lfm-2.5-2.6b:free`, `cohere/north-mini-code:free`). This contaminated the run-level label when `actual_model` was overwritten with the reviewer's model.
  - Previous claims of a matched GPT-4o comparison were therefore invalid.
  - Historical records are preserved in `mas.db` for complete auditability with status `MODEL_MISMATCH_DIAGNOSTIC` or `DIAGNOSTIC_RUN`, but excluded from comparative benchmark aggregates.
  - `model_calls` table is updated with `requested_model`, `actual_model`, `request_id`, and secret-redacted `raw_metadata` columns.
- **Impact**: Zero silent model substitution, guaranteed parity between requested and evaluated conditions, auditable model metadata, and honest provenance tracking.

---

### Record: Explicit Model Allowlist & Rejection of Variant Prefixes

- **ID**: DEC-021
- **Date**: 2026-10-11
- **Decision**: Replaced permissive family-prefix model matching in `is_model_match()` with an explicit allowlist mapping canonical requested models directly to their verified, documented dated snapshots (`VERIFIED_MODEL_SNAPSHOTS`).
- **Source**: Final Model Identity Verification Audit.
- **Context & Reason**:
  - Permissive string prefix matching (`r_canon.startswith(...)`) risked accepting unauthorized variants such as audio (`gpt-4o-audio-preview`), realtime (`gpt-4o-realtime-preview`), search-preview (`gpt-4o-search-preview`), instruct (`gpt-3.5-turbo-instruct`), or free-tier substitutions.
  - Strict allowlist explicitly bounds `openai/gpt-4o` to `{"openai/gpt-4o", "openai/gpt-4o-2024-05-13", "openai/gpt-4o-2024-08-06", "openai/gpt-4o-2024-11-20"}`.
  - `openai/gpt-4o-mini` is explicitly bounded to `{"openai/gpt-4o-mini", "openai/gpt-4o-mini-2024-07-18"}`.
  - `openai/gpt-3.5-turbo` is bounded to documented snapshots (`0125`, `1106`, `0613`, `16k`) and strictly excludes `-instruct`.
  - Missing or unverified model identity triggers immediate `ModelMismatchError`.
- **Impact**: Absolute identity certainty for LLM calls across all agents, preventing subtle variant substitution or pricing distortions.

---

### Record: Canonical Workspace Confirmation and Local Development Authorization

- **ID**: DEC-022
- **Date**: 2026-10-17
- **Decision**: Final workspace authorization for local development on desktop host `VARSHITH` at `C:\Users\The Mighty King\Desktop\Final Year Project`. Cross-machine transfer to external host `lenovo` is formally superseded and no longer required.
- **Source**: User Phase 2C explicit authorization.
- **Context & Reason**:
  - The legacy codebase, datasets (`data_attribute_format.csv`, `eval/tasks.json`), research PDFs (`Documentation for Building.pdf`, `HLD.pdf`, `LLD.pdf`, `iCoder_...pdf`), database run histories (`mas.db`), and 77-test offline test suite all physically reside and are fully verified on `C:\Users\The Mighty King\Desktop\Final Year Project`.
  - The workspace status transitions from `BLOCKED_PENDING_LEGACY_TRANSFER_VERIFICATION` to `AUTHORIZED_LOCAL_DEVELOPMENT`.
  - Development proceeds directly within the verified canonical repository without greenfield replacement or Git history reset.
- **Impact**: Unblocks Phase 2C to focus directly on agent quality, collaboration, and objective performance optimization using verified free OpenRouter models.

---

### Record: Level 1 Evaluator Protocol Versioning (v1.3) & CLI Multi-Invocation Smoke Verification

- **ID**: DEC-023
- **Date**: 2026-10-17
- **Decision**: Enhanced Level 1 entry-point smoke protocol from Evaluator `v1.2` to `v1.3`. When an application's entry point exits with standard argument usage requirements (e.g. `argparse` code 2 with usage notice), the smoke check verifies startup via `--help` (exit code 0) and controlled temporary file fixtures. Clean usage error exits from incomplete invocations are no longer mislabeled as functional breakage ($E=0$). True negatives (syntax errors, import failures, unhandled exceptions) strictly preserve $E=0$. The legacy methodology is preserved under `v1.2` and `calculate_executability_v1_2` to prevent silent drift or historical score invalidation. Level 2 behavioral suite pass rate remains the primary domain correctness metric.
- **Source**: Phase 2F Evaluator Validation Audit.
- **Context & Reason**:
  - In Phase 2E, the CSV Sales CLI achieved 100% (4/4) on Level 2 behavioral tests, but was assigned $E=0$ by Level 1 smoke because zero-argument invocation triggered `argparse`'s required file argument error.
  - Zero-argument invocation cannot distinguish a working CLI from broken code unless `--help` and valid inputs are exercised.
  - Symmetrical protocol applies identically to any future CLI or script candidate.
- **Impact**: Eliminates false executability rejections for argument-driven tools while preventing premature declaration of full domain correctness from `--help` alone.

---

### Record: Adaptive Stopping Quality Gate Distinction & Review Grounding

- **ID**: DEC-024
- **Date**: 2026-10-17
- **Decision**: Explicitly bifurcated multi-agent loop stopping status into `COMPLETED_QUALITY_GATE` and `STOPPED_MAX_ITERATIONS_WITH_OPEN_FINDINGS`. Reaching `max_iterations` alone never implies successful quality validation. Reflection stopping policy strictly enforces that executed behavioral tests outweigh self-assessment, and positive marginal score gain ($\Delta > 0$) cannot hide open critical findings. Reviewer findings claiming syntax errors, missing entry points, or missing stdout are cross-checked against deterministic AST parsers and execution logs; unsupported findings are tagged as dispositioned false positives rather than driving false revision cycles.
- **Source**: Phase 2F Defect Closure & Quality Gate Verification.
- **Context & Reason**:
  - In Phase 2E, run `mas_dev_csv_sales_1792211689` reached 3 iterations with 2 open critical findings reported by the Reviewer, yet was stamped `COMPLETED`.
  - Reviewer findings claiming syntax errors were false positives triggered by zero-argument smoke failures.
  - Honest research accounting demands clear distinction between runs that passed quality validation and runs bounded by iteration ceilings with unresolved findings.
- **Impact**: Complete transparency in audit history, preventing artificial inflation of system success rates.

---

### Record: Phase 2G Multi-Task Development Pilot Series & Daily Budget Ceilings

- **ID**: DEC-025
- **Date**: 2026-10-17
- **Decision**: Established a bounded 4-run multi-task development pilot series (`dev_markdown_toc_01` [SIMPLE], `dev_inventory_system_01` [STRUCTURED, invoking real ArchitectAgent], `dev_log_analyzer_01` [Data-Processing], and `dev_markdown_toc_01_repeat` [Repeat for consistency assessment]) completely outside the locked benchmark dataset (`eval/tasks.json`). Explicitly defined conservative ceilings: max 15 logical calls per run, max 60,000 provider-reported tokens per run, max 45 outbound HTTP transmissions per UTC day, and strict zero-cost enforcement on `cohere/north-mini-code:free` (`allow_fallbacks=False`). When OpenRouter returns HTTP 429 (`limit_source: openrouter_free_tier_daily`, `free-models-per-day`), runs checkpoint safely as `STOPPED_BUDGET_CEILING` without tight retry loops or silent paid model substitution.
- **Source**: Phase 2G Multi-Task Pilot Series & Generalization Specification.
- **Context & Reason**:
  - Confirmatory benchmark dataset must remain locked and pristine; multi-agent generalization must be proven on independent development tasks first.
  - Free tier quota limits must be strictly respected; exhausting daily limits must stop execution safely rather than falling back to unverified models or paid keys.
- **Impact**: Total cost containment ($0.00), deterministic quota governance, and absolute separation of development tuning from confirmatory evaluation.

---

### Record: Non-Masking of Upstream Infrastructure and Quota Errors in Agent Artifact Production Loop

- **ID**: DEC-026
- **Date**: 2026-10-17
- **Decision**: Updated `BaseAgent.produce_valid_artifact` to immediately propagate upstream infrastructure, quota, and rate-limit exceptions (`OpenRouterAPIError`, `ModelMismatchError`, `TokenCapExceededError`, `DispatchCeilingExceededError`, `DailyTransmissionsCeilingExceededError`) rather than catching them as candidate dictionary exceptions and triggering 3 futile retry/rollback loops. Infrastructure errors now bubble directly to the orchestrator workflow to halt and checkpoint runs safely with the true root cause recorded.
- **Source**: Phase 2G Error Handling & Quota Preservation Audit.
- **Context & Reason**:
  - Previously, when an HTTP 429 rate limit error occurred, `candidate = {"__producer_exception__": str(e)}` caused the validator to fail for missing artifact fields, prompting the agent to retry generation twice more, spamming the rate-limited provider and masking a quota error into a schema validation failure.
  - Distinguishing upstream provider errors from downstream artifact schema non-conformance prevents wasted model calls and guarantees honest telemetry.
- **Impact**: Eliminates futile retry loops on HTTP 429/quota limits, preserves provider goodwill, and records accurate failure causes in the run database.

---

### Record: Provider Quota Governor, Reconciled Accounting Ledger, and Exact Terminal State Taxonomy

- **ID**: DEC-027
- **Date**: 2026-10-17
- **Decision**: Implemented `ProviderQuotaGovernor` in `mas/core/governor.py` and integrated it with `MASWorkflow` and `OpenRouterProvider` to enforce:
  1. Reconciled provider quota checking via non-intrusive `/api/v1/auth/key` endpoint without consuming generation tokens.
  2. Global stop on the first daily-quota HTTP 429 (`limit_source: openrouter_free_tier_daily`, `free-models-per-day`) or when provider reports 0 remaining requests, immediately halting remaining tasks in the pilot series for that UTC day.
  3. Strict internal cap of 45 outbound HTTP transmissions per UTC day, counting every outbound attempt (successful calls, failed requests, and diagnostic probes).
  4. Exact terminal state taxonomy:
     - `COMPLETED_QUALITY_GATE`: all independent behavioral tests pass, no open critical findings, all evidence present.
     - `STOPPED_MAX_ITERATIONS_WITH_OPEN_FINDINGS`: iteration or marginal gain limit reached with unresolved issues.
     - `STOPPED_BUDGET_CEILING`: internal call dispatch (15) or token (60,000) ceiling reached.
     - `STOPPED_PROVIDER_QUOTA`: upstream provider free-model daily quota unavailable (`remaining: 0`).
     - `FAILED_INFRASTRUCTURE`: genuine network, connection, or server (5xx) infrastructure failure.
     - `FAILED_QUALITY_GATE`: generated software failed acceptance criteria or Level 2 behavioral suite.
- **Source**: Phase 2H Quota Reconciliation & Controlled Live Pilot Specification.
- **Impact**: Zero wasted generation tokens, 100% accurate attribution of provider errors, and safe automated pause until provider daily reset (00:00:00 UTC).

---

### Record: Unified Outbound Transmission Ledger, Scratch Script Isolation, and Resumption Governor Enforcement

- **ID**: DEC-028
- **Date**: 2026-10-17
- **Decision**: 
  1. Established an authoritative persistent outbound transmission ledger in `eval/outbound_transmission_ledger.json` that records every outbound HTTP request (generation calls, retry transmissions, 429 probe attempts, `/api/v1/auth/key` metadata queries, and scratch diagnostics).
  2. Permanently recorded the historical 2026-10-17 internal transmission cap breach (54 outbound attempts vs. 45 ceiling, excess = 9) without retroactive reclassification.
  3. Wrapped and secured all standalone diagnostic scripts in `scratch/` with `ProviderQuotaGovernor` dispatch permission checks, preventing unmonitored requests.
  4. Enforced counter reset strictly at 00:00:00 UTC, counting the single required preflight metadata query as 1 HTTP transmission against the new day's 45-request ceiling (leaving 44 available).
  5. Mandated strict paused state while upstream free-model quota remains exhausted (`free_model_daily_requests.remaining == 0`) and reset time has not arrived.
- **Source**: Phase 2J Safe Post-Reset Resumption and Live Development Pilot Completion Mandate.
- **Context & Reason**:
  - Transparent research integrity requires recording cap breaches openly rather than silently excluding diagnostic or failed requests.
  - Diagnostic scripts operating independently of the workflow caused unmetered traffic that contributed to provider rate-limit exhaustion.
  - Ensuring the counter resets only on a true UTC day boundary and counting metadata checks guarantees compliance with the 45-transmission budget.
- **Impact**: Zero unmetered outbound requests, persistent historical auditability, and deterministic adherence to provider reset boundaries.

---

### Record: Instrumented HTTP Client Wrapper (GovernedHTTPClient), Universal Outbound Transmission Accounting, and Quota Reset Resumption Protocol

- **ID**: DEC-029
- **Date**: 2026-10-17
- **Decision**:
  1. Built and integrated `GovernedHTTPClient` in `mas/core/governor.py`, a shared instrumented transport/client wrapper routing every outbound HTTP request across the repository.
  2. Enforced that EVERY outbound transmission (completion generation, schema retries, network retries, HTTP 429 attempts, key-metadata requests, and diagnostic calls) increments the persistent ledger counter exactly once.
  3. Pre-transmission cap enforcement: before any request transmits bytes over the wire, `GovernedHTTPClient` evaluates the daily transmission ceiling; if exhausted, `DailyTransmissionsCeilingExceededError` rejects the request before transmission.
  4. Failed network transmissions (e.g. `ConnectError`, `TimeoutException`) and HTTP 429/5xx responses are recorded in the ledger with their diagnostic status and exceptions without double counting in error handlers.
  5. Closed all direct HTTP client bypasses across `scratch/` (`test_or.py`, `check_catalog.py`, `verify_openrouter_auth.py`, `diagnose_reasoning.py`, `test_dev_token_budget.py`, `test_dev_effort_low.py`, `test_live_codepatch.py`).
  6. Added 8 comprehensive offline unit tests (`tests/test_transmission_governor_audit.py`) proving all governance invariants without live network calls.
  7. Test suite isolated from the production ledger via `MAS_LEDGER_PATH` in `tests/conftest.py`, ensuring offline testing never pollutes production audit records.
  8. Preserved the historical 2026-10-17 cap breach (54 transmissions / 45 cap) and maintained strictly paused live generation while current UTC time precedes the 00:00:00 UTC daily reset boundary.
- **Source**: Phase 2K Verified Quota Reset, Transmission Governance, and Live Pilot Resumption Mandate.
- **Context & Reason**:
  - Independent diagnostic scripts and schema retry paths could potentially bypass high-level workflow checks if not governed at the HTTP client layer.
  - A universal instrumented wrapper guarantees 100% accounting fidelity: every single TCP/HTTP transmission is persistently accounted for before or at transmission time.
- **Impact**: Absolute transmission governance coverage, full offline regression suite expanded to 140 passing tests, and deterministic quota safety across all development pilots.

---

### Record: Race-Safe Interprocess Governance, Atomic Two-Phase Transmission Reservations, Crash Consistency, and Controlled Pilot Resumption Protocol

- **ID**: DEC-030
- **Date**: 2026-10-17
- **Decision**:
  1. **Interprocess Concurrency Safety (`InterprocessLedgerLock`)**: Implemented platform-aware cross-process advisory file locking (`msvcrt.locking` on Windows, `fcntl.flock` on POSIX) targeting `eval/outbound_transmission_ledger.json.lock`. Multiple processes sharing the ledger cannot oversubscribe or race the daily transmission cap.
  2. **Two-Phase Reservation State Machine**:
     - Phase 1 (`reserve_transmission`): Atomically verifies remaining daily budget under the cap, increments `total_outbound_http_transmissions` by exactly 1, writes a persistent attempt record in state `RESERVED` to disk, and returns a unique `attempt_id`. If cap reached, raises `DailyTransmissionsCeilingExceededError` before any wire transport.
     - Phase 2 (`finalize_transmission`): Upon transport completion, updates the attempt record with HTTP status or network exception (`SUCCEEDED`, `HTTP_ERROR`, `NETWORK_ERROR`). Invariant: finalization is strictly idempotent and NEVER increments `total_outbound_http_transmissions`.
  3. **Crash Consistency**: Ledger persistence utilizes atomic temporary write, `flush()`, `os.fsync()`, and `os.replace()`. Any unfinalized `RESERVED` attempt remains counted against the daily allowance across crashes or restarts.
  4. **Universal Bypass Closure**: Closed all raw `httpx`/`requests` entry points across `mas/core/proxy.py`, `scripts/test_models.py`, and all diagnostic scripts under `scratch/`.
  5. **11 Offline Governance Verification Tests**: Built comprehensive offline verification suite in `tests/test_transmission_governor_audit.py` (concurrency stress, cap rejection before transport, reservation persistence, crash recovery, idempotency, retry allocation, failed attempt accounting, multi-governor oversubscription, UTC date rollover, bypass closure, and test ledger isolation).
  6. **Strict Network Restriction Enforcement**: Enforced mandatory pause prior to `2026-10-18 00:00:00 UTC` with 0 calls to OpenRouter (no auth/key, catalog, or generation). Preserved historical 2026-10-17 ledger record (54 transmissions / 45 cap).
- **Source**: Phase 2L Race-Safe Transmission Governance and Controlled Live Pilot Resumption Mandate.
- **Context & Reason**:
  - Outbound accounting must be robust against concurrent worker processes and sudden process termination or unhandled exceptions after network dispatch.
  - Pre-dispatch reservation ensures that even if a network timeout or crash occurs mid-flight, the transmission allowance is already accurately accounted for.
- **Impact**: Zero cap races, crash-resilient accounting, 143 passed offline regression tests, and ironclad adherence to daily transmission limits.

---

### Record: Programmatic Reset Boundary Verification, Strict Pre-Reset Network Freeze, and Controlled Post-Reset Live Pilot Protocol

- **ID**: DEC-031
- **Date**: 2026-10-17
- **Decision**:
  1. **Programmatic Reset Boundary Enforcement**: Mandated that all pilot execution checks the system UTC timestamp programmatically against `2026-10-18 00:00:00 UTC` at startup. If the boundary has not passed, execution stops immediately with zero outbound OpenRouter requests (no `/api/v1/auth/key` queries, model catalog queries, diagnostic probes, or generation dispatches).
  2. **No Unverified Auto-Resumption**: Clarified that automated polling or phantom resumption must not be assumed without a dedicated scheduler/persistent daemon. All pilot tasks remain checkpointed in `STOPPED_PROVIDER_QUOTA` and require human-initiated or scheduled re-execution post-reset.
  3. **Post-Reset Single-Preflight Gate**: Once UTC time >= `2026-10-18 00:00:00 UTC`, the coordinator performs exactly ONE governed `/api/v1/auth/key` preflight, accounted as Transmission 1 of 45 in the new day's ledger. A non-positive or ambiguous quota response halts the run immediately with no retries.
  4. **Strict Architectural Sequencing**: Task B (`dev_inventory_system_01`) requires concrete database and event evidence that `ArchitectAgent` generates the architecture before developer generation begins.
  5. **Independent Level 2 Quality Gates**: Only mark tasks `COMPLETED_QUALITY_GATE` upon passing all independent Level 2 behavioral assertions without open critical reviewer findings.
- **Source**: Phase 2M Post-Reset Live Pilot Execution and Quality Validation Mandate.
- **Context & Reason**:
  - Outbound quota calls prior to the documented reset boundary waste daily allowances and violate provider constraints.
  - Transparent research requires explicit programmatic boundary gates and verifiable offline artifacts.
- **Impact**: Zero network leakage, persistent audit preservation, deterministic boundary adherence, and strict quality verification.
- **Supersession Note (Phase 2O Reconciliation)**: The endpoint reference to `/api/v1/auth/key` in item 3 above is explicitly superseded by **DEC-032** for all active implementation purposes, which establishes OpenRouter's documented `GET https://openrouter.ai/api/v1/key` endpoint. The historical text of DEC-031 is preserved unmodified for audit trail fidelity.

---

### Record: Preflight Endpoint Audit, Fail-Closed Quota Parsing, and Model Availability Decoupling

- **ID**: DEC-032
- **Date**: 2026-10-17
- **Supersedes**: Supersedes the deprecated `/api/v1/auth/key` endpoint references in **DEC-031** (item 3) for all active implementation purposes.
- **Decision**:
  1. **Documented Endpoint Correction**: Reconciled active quota-check implementation and preflight inspection in `mas/core/llm.py` (`OpenRouterProvider.check_key_metadata`) and `mas/core/governor.py` (`ProviderQuotaGovernor.check_upstream_key_status`) to query OpenRouter's documented key information endpoint `GET https://openrouter.ai/api/v1/key` (replacing deprecated `/api/v1/auth/key`).
  2. **Fail-Closed Quota Parsing**: Replaced permissive defaulting with strict validation of `data.free_model_daily_requests.remaining`. Execution halts safely (`can_proceed=False`, `is_quota_exhausted=True`) on zero quota (`remaining <= 0`), missing `free_model_daily_requests` object, missing or non-numeric `remaining` field, malformed/non-dict JSON responses, or authentication/HTTP errors. Unknown quota is never silently treated as available.
  3. **Decoupled Model Availability**: Do not claim the key-information endpoint confirms model availability. Retain configured inference model fixed at `cohere/north-mini-code:free` with `allow_fallbacks: False`. Validate served-model identity (`is_model_match`), availability, and $0.00 cost strictly on the first generation response. If model mismatch occurs, raise `ModelMismatchError` and halt cleanly without switching models.
  4. **Exact-Once Transmission Accounting**: Ensure exactly one internal HTTP transmission is reserved and finalized for one actual preflight transmission (Transmission 1/45 on a fresh UTC day), with no automated retries and no duplicate metadata requests during task dispatches (`provider=None`).
  5. **Historical Ledger Immutability**: Preserved the historical 2026-10-17 ledger record unchanged at 54 transmissions (45 ceiling, 9 excess) without altering past endpoint strings.
- **Source**: Phase 2N Final Preflight Endpoint Audit Mandate.
- **Context & Reason**:
  - The OpenRouter documentation specifies `GET /api/v1/key` for key metadata and rate limit inspection.
  - Speculative quota calculations (e.g. `limit - used` fallback) risked silent execution during ambiguous upstream states.
  - Transparent research requires verifiable served-model identity rather than inferring availability from key tokens.
- **Impact**: 148/148 passed regression tests, zero unverified network dispatches, robust fail-closed quota gating, and verified readiness for Task A.

---

### Record: Phase 0 Baseline Test Status and Governance Audit

- **ID**: DEC-033
- **Date**: 2026-11-09
- **Decision**: Established pre-change baseline verification, ChatDev submodule pin audit, and AGENTS.md governance contract.
- **Source**: Free-tier benchmark realignment mandate.
- **Baseline test status**:
  - Full test suite execution: `python -m pytest tests/ -q`
  - Results: **224 passed in 29.20s**, 0 failed, 0 errors.
  - Baseline failing or erroring tests: None.
  - Submodule audit:
    - `git -C external/ChatDev log -1 --format=%H`: `c1c31e28864df6b8b0394683b8286436ce41b5ce` (matches pinned base commit)
    - `git -C external/ChatDev status --short`: clean (no local edits in tracked files)
- **Impact**: Baseline integrity confirmed. Ready to execute Phase 1.

---

### Record: Phase 1 Validity Fixes and Discrepancy Audit

- **ID**: DEC-034
- **Date**: 2026-11-09
- **Decision**:
  1. **Problem A (Generic Prompts)**: Purged all task-specific hardcoded keywords (`ScienceQuestionSolver`, `photosynthesis`, `atomic numbers`, `speed/velocity`, `Multi-Domain Requirements`) from `mas/agents/developer.py`. Retained strictly generic Python engineering instructions.
  2. **Problem B (Symmetric CLI Contract)**: Created shared `CLI_CONTRACT_SUFFIX` in `eval/task_text.py` and wrapped requirement formulation via `get_augmented_requirement()`. Both MAS and ChatDev now receive byte-for-byte identical requirement text appending the CLI contract. Removed hardcoded `--help`/0-arguments hints from MAS Developer prompts so no asymmetrical information advantage exists.
  3. **Problem C (Reliable Consistency & Embedder Limits)**:
     - Updated `pyproject.toml` dependencies with `numpy`, `sentence-transformers`, `tiktoken`, `ruff`, `bandit`, `radon`, `scipy`, and `pyyaml`.
     - Added `consistency_method` (`embedding` vs `lexical_fallback`) tracking across scorers, `NeutralEvaluator`, `results.csv`, and reports.
     - Enforced `eval.consistency_max_code_chars` (default 2000) in `config.yaml` and `eval/scorers/icoder_metrics.py` to prevent OOM/divergence on large codebases while preserving deliberate configuration.
     - Added `--require-embeddings` flag in `eval/runner.py` CLI to abort before live runs if sentence-transformers is unavailable.
  4. **Problem D (Score Audit via `scripts/audit_scores.py`)**:
     - Audited all 32 runs in `results.csv` against on-disk workspaces.
     - Found 30 workspaces intact, 2 workspaces absent (pre-workspace aborts).
     - Verified that all completed live runs matched stored scores within 0.01. Exactly 1 discrepancy was identified (`sim_cd_srdd_educ_01_r1_attempt2`, where metrics were stored as None in CSV for a simulation run despite valid generated files). No data was rewritten.
- **Source**: Phase 1 Validity & Benchmark Integrity Mandate.
- **Impact**: 231/231 passing regression tests, strict parity between systems, and verifiable consistency metrics.

---

### Record: Phase 2 Free-Tier Multi-Day Benchmark Architecture

- **ID**: DEC-035
- **Date**: 2026-11-09
- **Decision**:
  1. **Provider-Agnostic Client**: Added `PROVIDER_BASE_URL`, `PROVIDER_API_KEY`, and `BENCH_MODEL` environment settings across `mas/core/llm.py` and `mas/core/proxy.py`, falling back to `OPENROUTER_*` vars. Defaulted Gemini base URL to `https://generativelanguage.googleapis.com/v1beta/openai/`. Stripped OpenRouter-only fields (`provider.allow_fallbacks`) for non-OpenRouter providers.
  2. **Model Pinning**: Configured `__SET_BENCH_MODEL_IN_ENV__` placeholder in `config.yaml`. The runner and LLM client refuse to start live generation without `BENCH_MODEL` set. Handled optional `models/` prefix gracefully in `is_model_match`.
  3. **Configurable Daily Budget Governor & Sliding Window Rate Limiter**:
     - Configured `provider.daily_request_limit: 500`, `requests_per_minute: 12`, `tokens_per_minute: 200000`, `safety_margin: 0.10` (effective daily cap: 450 requests), `quota_timezone: "America/Los_Angeles"` in `config.yaml`.
     - Built `SlidingWindowRateLimiter` enforcing both RPM (12) and TPM (200k) with a sliding 60-second window, preventing 429 errors.
     - Rolled over ledger at local midnight of `provider.quota_timezone` rather than UTC.
     - Updated `tests/test_provider_quota_governor.py` assertion to dynamically check `governor.internal_daily_cap - 1` reflecting the configured cap.
  4. **Multi-Day Resumability**: Added `--resume` and `--stop-at-budget` flags to `eval/runner.py`. `--resume` reads manifest to skip official runs while re-running `INTERRUPTED` runs from scratch. `--stop-at-budget` exits cleanly before daily quota breach.
  5. **Failure Classification**: Implemented `classify_failure()` categorizing runs into `INFRA_ERROR` (retried up to twice) or `QUALITY_FAILURE` (Quality = 0 in official results).
  6. **Estimator**: Added `python -m eval.runner --estimate` projecting 18 pairs/day and 2 days for 20 tasks under the 450 effective daily request cap.
  7. **Scripts**: Created `scripts/list_models.py` to inspect available provider model IDs securely without disclosing keys.
- **Source**: Phase 2 Free-Tier Benchmark Alignment Mandate.
- **Impact**: 239/239 passing unit and regression tests, zero unverified live calls, and safe multi-day execution capability.

---

### Record: Phase 4 Quality Improvement and Call Reduction (Generic Only)

- **ID**: DEC-037
- **Date**: 2026-11-09
- **Decision**:
  1. **Unified Token Cap (100,000 tokens)**:
     - Unified `limits.max_tokens_per_run: 100000` in `config.yaml`.
     - Removed hardcoded 60,000 token defaults from `mas/core/llm.py`, `mas/core/governor.py`, and `eval/runner.py`.
     - Parameterized token boundary test suites (`test_phase2aa_budget_and_chatdev.py`, `test_phase2y_token_budget_and_evidence.py`) to dynamically test against `token_logger.max_tokens_per_run`.
  2. **Delimiter Blocks Format for Developer**:
     - Switched Developer code generation prompt to structured delimiter blocks (`=== FILE: <filename> ===\n<code>\n=== END FILE ===`) with robust parsing handling markdown preambles, missing end markers, and raw code text without escaping errors. Maintained JSON parsing as backward-compatible fallback.
  3. **Deterministic Repair & Smoke Check (`mas/analysis/deterministic_checker.py`)**:
     - Implemented `DeterministicRepairChecker.run_checks` inspecting code for missing `main.py`, AST syntax errors, stub implementations (`NotImplementedError`, lone `pass`, ellipsis `...`), and smoke execution crashes.
     - Added targeted repair loop in `DeveloperAgent.targeted_repair` to fix deterministic issues without spending a full multi-agent iteration.
  4. **Skip Reviewer on Clean Execution**:
     - In `mas/core/workflow.py`, when deterministic checks pass, smoke run passes, and internal tests pass with zero failures, skipped calling the Reviewer LLM. Emits a synthetic `ReviewReport(status="PASSED", critical_issues=0)`. Saves 1 LLM call per run.
  5. **Tester Assertion Truncation**:
     - In `mas/agents/tester.py`, truncated test failure traceback and output details to at most 40 lines and max 5 test failure details to prevent prompt bloat.
  6. **Prompt Hygiene & Token Cap Management**:
     - Capped prompt lists (subtasks, architecture files, review findings, reflection items) to the latest 5 entries.
  7. **Call Tracking & Efficiency Verification**:
     - Added `llm_calls` accounting to `TokenLogger`, persisted across `results.csv` and manifest summaries.
     - On clean first-try execution, total LLM calls $\le 3$ (Manager 1, Developer 1, Tester 1).
- **Source**: Phase 4 Quality Improvement and Call Reduction Mandate.
- **Impact**: 260/260 passing unit and regression tests (9 new tests in `tests/test_phase4_quality_and_call_reduction.py`).
- **Risks**: Skipping Reviewer on clean runs could miss subtle domain logic discrepancies if internal tests are shallow; mitigated by triggering Reviewer whenever any smoke test or assertion fails.


- **ID**: DEC-036
- **Date**: 2026-11-09
- **Decision**:
  1. **New Task Selection (`scripts/select_tasks.py`)**:
     - Mapped all 40 SRDD subcategories from `data_attribute_format.csv` to the iCoder paper's 5 major categories (Education, Work, Life, Games, Creation) and wrote `eval/category_map.json`.
     - *Categorization judgments noted*: `News` mapped to `Education` (knowledge/informational reference), `Budgeting` mapped to `Work` (financial management), `Notebook` mapped to `Life` (personal notes), `Data` mapped to `Work` (analytics), `Entertainment` mapped to `Creation` (creative/multimedia).
     - Filtered candidate tasks with description lengths strictly between 40 and 80 words (724 candidates).
     - Deterministically sampled 4 tasks per major category (20 total) with random seed 42 and no duplicate names into `eval/tasks_v2.json`.
     - SHA-256 (`aa902c027cfb0a137ca220d1db03f73ce94b9d3bfd6b7da9f8bfd83b83baf5b3`) verified and recorded in `eval/benchmark_manifest.json` under `tasks_v2_sha256`. Preserved `eval/tasks.json`.
     - Added `--tasks-file` option to `eval/runner.py`.
  2. **Honest Counting & No Cherry-Picking**:
     - Designated official row per `(task_id, system, repeat_no, ablation)` as the FIRST attempt that is not an `INFRA_ERROR`.
     - `QUALITY_FAILURE` runs are officially retained and count as Quality = 0.0.
     - Only `INFRA_ERROR` runs (e.g., 429, daily quota ceiling, timeouts) may be retried.
     - Added `official` (true/false) and `retry_reason` columns to `results.csv` and `eval/benchmark_manifest.json`.
     - Simulation-only runs (`SIMULATION_ONLY`) are strictly labeled and excluded from official stats.
     - `--resume` skips tasks that already possess an official row.
  3. **Advanced Hypothesis Testing & Distribution Statistics (`eval/stats.py`)**:
     - Added `wilcoxon_signed_rank_test` using `scipy.stats.wilcoxon`, safely handling small n, identical pairs, and zero differences without crashing.
     - Added `bootstrap_ci` computing 95% percentile confidence intervals with 10,000 resamples and fixed seed 42.
     - Added `calculate_success_rate` reporting the share of official finished runs per system in `eval/reports.py`.
     - Preserved paired permutation test and Cohen's d effect size.
  4. **Ablation Matrix Implementation (A0-A4)**:
     - Implemented `--ablation` switches across `mas/core/workflow.py`, `mas/core/context.py`, `mas/agents/reviewer.py`, and `config.yaml`:
       - `A0`: Full MAS (default).
       - `A1`: No complexity router (forces ArchitectAgent execution even on SIMPLE tasks).
       - `A2`: No AST impact slicing (sends full repository file set every iteration).
       - `A3`: No evidence-grounded review (ReviewerAgent skips deterministic AST cycles, Ruff, Bandit, and Sandbox outputs).
       - `A4`: No reflection loop (forces loop termination at iteration 1).
     - Recorded `ablation` ID across all results.csv rows, Evaluation records, and manifest run entries.
- **Source**: Phase 3 Benchmark Scope, Fairness, and Ablation Architecture.
- **Impact**: 251/251 passing unit tests (12 new tests in `tests/test_phase3_tasks_stats_ablations.py`).

---

### Record: Phase 5 Fair ChatDev Baseline, Simulation Guard, and Reproducible Patch

- **ID**: DEC-038
- **Date**: 2026-11-09
- **Decision**:
  1. **ChatDev Simulation Guard**:
     - Labeled all simulated ChatDev execution runs strictly as `SIMULATION_ONLY` (`status`, `execution_mode`, `token_provenance`) in `eval/chatdev_adapter.py`.
     - Hardened `eval/reports.py` and `eval/stats.py` to exclude `SIMULATION_ONLY` and `SIMULATED` rows from all markdown tables, aggregate metric distributions, and success rate calculations.
  2. **Experimental Fairness Enforcement**:
     - Pinned logging proxy default URL to `http://127.0.0.1:8089/v1`.
     - In `mas/core/proxy.py`, enforced `temperature=0.0` and `seed=42` on every forwarded model request for both MAS and ChatDev.
     - Verified both systems receive identical requirement text augmented via `eval/task_text.py`.
  3. **Windows Subprocess Compatibility**:
     - Configured ChatDev subprocess execution with `sys.executable`, `PYTHONIOENCODING=utf-8`, `PYTHONUTF8=1`, `encoding="utf-8"`, `errors="replace"`, and 900s timeout.
  4. **Preflight Verification CLI (`python -m eval.runner --preflight`)**:
     - Implemented offline checklist inspecting: ChatDev pinned commit (`c1c31e2886`), non-empty API key, valid `BENCH_MODEL`, offline embedder/lexical status, proxy start/stop clean cycle on port 8089, and remaining governor quota (>= 15 requests).
  5. **Extended Efficiency Metrics**:
     - Added `wall_clock_seconds`, `loc` (lines of non-empty, non-comment code in `*.py` excluding tests), and `llm_calls` across `rec` dictionary and `results.csv` export for both systems.
  6. **Daily Transmission Ledger Integration**:
     - ChatDev requests routed through `mas/core/proxy.py` are counted in the daily governor ledger via `GovernedHTTPClient`. If a live run produces zero proxy tokens, the runner flags the run as `INFRA_ERROR` (`FAILED`).
  7. **Reproducible ChatDev Setup**:
     - Exported `patches/chatdev_local.patch` (SHA-256 `bf239f6157240df3ffed505e0e1f05e8c4e84f7c70006d51fc62e70d8105584b`) capturing local fixes against upstream `v1.0.0` (`5defde31792346e0cc302f672a33e766ef955dd8`).
     - Created `scripts/setup_chatdev.py` automating repository cloning, checkout, and clean patch application.
- **Source**: Phase 5 Fair Baseline and Reproducibility Mandate.
- **Impact**: 267/267 passing unit tests (7 new tests in `tests/test_phase5_chatdev_and_simulation_guard.py`).

---

### Record: Phase 6 Reporting and Run Guide

- **ID**: DEC-039
- **Date**: 2026-11-09
- **Decision**:
  1. **Unified Reporting Engine (`scripts/make_report.py`)**:
     - Built single offline reporting script reading `results.csv` or `eval/benchmark_manifest.json` and exporting Tables 1–6 in Markdown to stdout and `reports/benchmark_report.md`.
     - Exported thesis-ready LaTeX tabular tables to `reports/tables.tex` with escaped text characters and standard tabular environments.
     - Exported machine-readable summary statistics to `reports/summary.csv`.
     - Added optional matplotlib visualization generation to `reports/figures/` (quality boxplot and quality vs. tokens scatter plot) with graceful fallback when uninstalled.
     - Implemented "NOT RUN" fallback when benchmark data is absent to uphold Rule 1.
  2. **Optional Dependencies Specification (`pyproject.toml`)**:
     - Defined `report = ["matplotlib>=3.7.0", "pandas>=2.0.0"]` under `[project.optional-dependencies]` without bloating core runtime requirements.
  3. **Comprehensive Run Guide (`RUN_FINAL.md`)**:
     - Created detailed, step-by-step operator guide covering environment setup, preflight verification, multi-day execution (`--resume --stop-at-budget`), ablation runs (A1–A4), report generation, and troubleshooting (429 handling, $0.00 verification, ledger status inspection, single-task re-runs).
- **Source**: Phase 6 Reporting and Run Guide Mandate.
- **Impact**: 269/269 passing unit tests (2 new tests in `tests/test_phase6_make_report.py`).

---

### Record: Phase 7 Clean Up and Repository Hygiene

- **ID**: DEC-040
- **Date**: 2026-11-09
- **Decision**:
  1. **Archive Directory Creation & File Movement (Zero Deletions)**:
     - Established `archive/` directory preserving full git history without any file deletions.
     - Moved legacy scratch exploration scripts into `archive/scratch/`.
     - Moved historical experiment backup snapshots into `archive/backups/`.
     - Moved 22 legacy phase reports (`PHASE_2*.md`), legacy methodology documents, and transfer verification files into `archive/`. Preserved `submission/` directory intact.
  2. **README Overhaul**:
     - Modernized `README.md` to reflect the current architecture, complete repository layout, 100% offline test suite instructions (269 tests), and reference to `RUN_FINAL.md` for benchmark operations.
     - Documented free-tier Google Gemini rate limits (500 daily requests, 12 RPM, 200k TPM, Midnight Pacific rollover) and core research integrity guarantees.
- **Source**: Phase 7 Clean Up Mandate.
- **Impact**: 269/269 passing unit tests; clean, professional repository layout.







