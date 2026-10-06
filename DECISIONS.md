# Architecture and Design Decisions (DECISIONS.md)

This document tracks architectural decisions, source precedence, specification conflicts, chosen defaults, model configurations, evaluation constraints, and security policies for **MAS (Multi-Agent Software Engineering Team)**.

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
