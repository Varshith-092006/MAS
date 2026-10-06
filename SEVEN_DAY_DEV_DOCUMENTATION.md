# MAS — 7-Day MVP Research & Development Retrospective Documentation

This document records the retrospective Day 1 through Day 7 engineering trajectory for **MAS (Multi-Agent Software Engineering Team)**, structuring the delivery of the complete, reproducible research system.

---

## Executive Summary

MAS addresses the computational and token overhead identified in multi-agent software engineering baselines (such as iCoder and ChatDev). Over the 7-day sprint, an end-to-end multi-agent architecture was developed featuring conditional complexity routing, deterministic AST-based dependency analysis, token-efficient context slicing, adaptive stopping, and an isolated neutral evaluation battery.

---

## Day 1: Contracts, Repository Foundation, Configuration, State, Provider Abstraction & Database

### Objectives & Built Components
- **Repository Setup**: Initialized directory layout, pyproject.toml package configuration, `.env.example`, and versioned `config.yaml`.
- **Inter-Agent Artifact Contracts (`mas/core/schemas.py`)**: Defined canonical Pydantic models with automated JSON Schema export for:
  - `TaskPlan`
  - `UserStory`
  - `Architecture`
  - `CodePatch`
  - `ReviewReport`
  - `TestReport`
  - `ReflectionDecision`
- **Workflow State (`mas/core/state.py`)**: Built `MASState` TypedDict specifying all metadata, artifacts, AST reports, and token counters.
- **LLM Provider Abstraction (`mas/core/llm.py`)**:
  - Implemented `LLMProvider` interface.
  - Implemented deterministic `FakeLLMProvider` for offline unit and integration testing.
  - Implemented `OpenAIProvider` routing through an OpenAI-compatible local logging proxy.
  - Implemented `TokenLogger` tracking provider usage fields only (`input_tokens`, `output_tokens`, `total_tokens`, `latency_ms`, `cost`) with a 60,000 hard token cap per run.
- **Database Schema (`mas/db/models.py`, `mas/db/session.py`)**:
  - Implemented all 9 LLD tables: `tasks`, `evaluations`, `runs`, `agent_events` (append-only), `artifacts`, `checkpoints`, `model_calls`, `metrics` (split into `neutral` vs `internal`), and `config_snapshots`.
  - Excluded `users`, `roles`, and JWT to maintain single-user research focus.

### Validation & Milestones
- Verified schema validation on valid and invalid payloads.
- Verified database initialization under SQLite and PostgreSQL.
- Verified token cap violation raising `TokenCapExceededError`.

---

## Day 2: Manager, Deterministic Router, Architect, Developer, Workflow Orchestration & Validation

### Objectives & Built Components
- **Deterministic Complexity Router (`mas/agents/router.py`)**:
  - Zero LLM calls.
  - Evaluates regex features: persistence, authentication, roles, APIs/integrations, analytics, and workflows.
  - Evaluates separator counts ($\ge 4 \implies +1$, $\ge 7 \implies +2$) and word count length ($>80 \implies +1$).
  - Routes score $0\text{--}3$ to `SIMPLE` and $4+$ to `STRUCTURED`.
  - Created `evaluation/router_labels.json` with 10 diagnostic requirements marked with `needs_human_review: true`.
- **Manager Agent (`mas/agents/manager.py`)**: Normalizes requirements and coordinates router execution to produce `TaskPlan`.
- **Architect Agent (`mas/agents/architect.py`)**: Triggered exclusively for `STRUCTURED` path; produces `Architecture` (with UML class diagram) and `UserStory`. Provides UML slicing.
- **Developer Agent (`mas/agents/developer.py`)**: Emits `CodePatch` containing source code and writes files to the target workspace.
- **Workflow Orchestrator (`mas/core/workflow.py`)**: Coordinates Manager $\to$ Router $\to$ (Architect) $\to$ Developer.
- **CLI Baseline (`mas/cli/main.py`)**: Implemented `mas run --model fake`, `mas status`, `mas logs`, and `mas results`.

### Validation & Milestones
- **CP1 Checkpoint Passed**:
  - End-to-end execution of `SIMPLE` task (verified Architect omitted).
  - End-to-end execution of `STRUCTURED` task (verified Architect invoked).
  - Verified 100% accuracy on draft router diagnostic cases.

---

## Day 3: Docker Sandbox, AST Dependency Analyzer & Static Quality Tools

### Objectives & Built Components
- **Docker Sandbox Runner (`mas/analysis/sandbox.py`)**:
  - Enforced security boundaries: `--network none`, 512 MB memory limit, 1 CPU, 64 PIDs limit, read-only base filesystem, writable `/workspace` mount only, and 30–60s timeout.
  - Added clean subprocess fallback for environments without active Docker daemons.
  - Implemented entrypoint `smoke_run`.
- **Deterministic AST Analyzer (`mas/analysis/ast_analyzer.py`)**:
  - Replaced LLM structural calls with Python `ast` module parsing.
  - Built directed dependency graph and local module resolution.
  - Implemented 3-color DFS cycle detection.
  - Implemented reverse-dependency graph and transitive impact set calculator.
- **Static Quality Tools (`mas/analysis/quality_tools.py`)**:
  - Wrapped `Ruff` (linting violations).
  - Wrapped `Bandit` (security severity: High, Medium, Low).
  - Wrapped `Radon` (Maintainability Index).

### Validation & Milestones
- Verified synthetic circular dependency detection on $A \to B \to C \to A$.
- Verified detection of unresolved imports.
- Verified transitive impact set calculation.

---

## Day 4: Semantic Reviewer, Reflection, Adaptive Stopping, Rollback & Fault Recovery

### Objectives & Built Components
- **Semantic Reviewer (`mas/agents/reviewer.py`)**: Configured with cheap model (`gpt-4o-mini`) to review requirement alignment without performing graph analysis.
- **Internal Tester Agent (`mas/agents/tester.py`)**: Generates internal diagnostic pytest reports (`scope = 'internal'`).
- **Reflection Agent & Adaptive Stopper (`mas/agents/reflection.py`)**:
  - Computes internal score:
    $$S_t = 0.30\cdot\text{InternalTest} + 0.10\cdot\text{Ruff} + 0.15\cdot\text{Bandit} + 0.10\cdot\text{Radon} + 0.15\cdot\text{Reviewer} + 0.20\cdot CE$$
    where $CE = 0.5 \cdot (\text{Completeness} + \text{Executability})$.
  - Evaluates stopping conditions:
    1. Clean result: no critical defects and internal tests pass.
    2. Low marginal gain: $\Delta < 0.02$ for 2 consecutive iterations.
    3. Reached maximum iterations ($3$).
  - Strictly isolated from neutral evaluation metrics.
- **Git Checkpoint Manager & Rollback (`mas/core/checkpoints.py`, `mas/agents/base.py`)**:
  - Checkpoints workspace prior to producer calls.
  - Invalid artifact policy: retry once with error feedback $\to$ rollback to last valid checkpoint $\to$ rerun producer $\to$ fail run if permanently invalid.
- **Context Slicing (`mas/core/context.py`)**:
  - Iteration 1: planned files.
  - Later iterations: $\text{changed\_files} \cup \text{AST impact set}$, plus sliced UML.

### Validation & Milestones
- Fault recovery integration test verified: invalid artifact $\to$ retry once $\to$ rollback to checkpoint $\to$ rerun recovery.
- Context slicer verified avoiding full project resubmission.

---

## Day 5: SRDD Loader, Neutral Evaluator, Scorers, ChatDev Adapter & Evaluation Runner

### Objectives & Built Components
- **SRDD Benchmark Task Loader (`eval/srdd_loader.py`)**:
  - Seed 42 deterministically samples 4 tasks each across Education, Work, Life, Games, and Creation (20 tasks total).
  - Saved to `eval/tasks.json` and persisted in database `tasks` table.
- **Hidden Neutral Evaluator (`eval/neutral_evaluator.py`, `eval/scorers/`)**:
  - Positioned entirely outside `mas/` package.
  - Evaluates both MAS and ChatDev outputs identically.
  - Metrics: Completeness, Executability, Consistency (`all-MiniLM-L6-v2`), Quality ($Q_i = C \times E \times Sim$).
  - Shared Fixed Test Harness (`eval/scorers/shared_test.py`): Level 1 smoke check + Level 2 checks (`eval/checks/level2_checks.json`).
  - Computed and recorded SHA-256 hash of checks file in every run snapshot.
- **ChatDev Adapter (`eval/chatdev_adapter.py`)**:
  - Pinned commit `836f32e6584c3600f6c268a719c8f0f074d0ef9b` (v1.0.0).
  - Routes OpenAI API calls through local logging proxy to capture provider-reported usage.
  - Normalizes workspace output for neutral evaluator.
- **Evaluation Runner (`eval/runner.py`)**:
  - Supports `--dry-run`: outputs 300 core experimental runs and 8.4M engineering planning token envelope with 0 model calls.
  - Supports 1-task pilot for MAS and ChatDev.

### Validation & Milestones
- Executed `eval/runner.py --dry-run` and verified exact 300-run matrix.
- Executed 1-task pilot on Task 1 (`Flashcard Quiz System`):
  - MAS: Tokens=1,168, Quality=0.550, Quality/1k=0.4709
  - ChatDev: Tokens=3,000, Quality=0.546, Quality/1k=0.1822

---

## Day 6: Change Request Flow, Fault Injection, Benchmark Infrastructure & Full Stack API/UI

### Objectives & Built Components
- **Change Request Manager (`mas/core/change_request.py`)**:
  - Computes requirement diff.
  - Identifies seed modules and computes AST transitive impact set.
  - Updates only affected files.
  - Detects obsolete/deprecated functions.
  - Runs regression tests and neutral evaluation.
- **Fault Injection Suite (`tests/test_fault_injection.py`)**:
  - F1: Malformed UML/Architecture artifact.
  - F2: Incomplete UserStory artifact.
  - Verified detection, retry, rollback, and recovery metrics.
- **FastAPI REST API & WebSockets (`mas/api/`)**:
  - Implemented `POST /runs`, `GET /runs/{id}`, `GET /runs/{id}/results`, `GET /runs/{id}/events`, `POST /runs/{id}/change`, `POST /runs/{id}/cancel`, `GET /evaluations/{id}`, and `WS /ws/runs/{id}`.
- **Single-Route React Frontend (`frontend/`)**:
  - Route: `/runs/:runId`.
  - Built `RunHeader`, `StatusBanner`, `AgentLog`, `MetricsTable` (neutral vs internal), and `TokenCostChart` (60,000 cap).
- **Docker Compose (`docker-compose.yml`, `Dockerfile`, `frontend/Dockerfile`)**:
  - Multi-service deployment containing PostgreSQL, FastAPI backend, and React frontend.

### Validation & Milestones
- Verified F1 and F2 fault tests pass with recovery.
- Verified change request flow identifies seeds and updates affected files.
- Verified FastAPI test endpoints pass with `httpx.AsyncClient`.

---

## Day 7: Statistics Engine, Reporting, Final Validation & Reproducibility

### Objectives & Built Components
- **Statistics Engine (`eval/stats.py`)**:
  - Implemented two-sided paired permutation test ($\alpha=0.05$, 10,000 trials).
  - Implemented Cohen's $d$ effect size, 95% confidence intervals, mean, SD, and median.
  - Primary metrics: Quality and Quality per 1,000 tokens.
- **Reporting Generator (`eval/reports.py`)**:
  - Exports standardized `results.csv`.
  - Formats experimental comparison markdown report.
- **CLI Finalization (`mas/cli/main.py`)**:
  - Implemented `mas run`, `mas status`, `mas logs`, `mas results`, `mas change`, `mas evaluate`, and `mas ablate`.
- **Architectural Documentation**:
  - Finalized `DECISIONS.md` containing decisions DEC-001 through DEC-016.
  - Finalized `README.md` with complete installation, CLI, testing, and Docker instructions.

### Validation & Final System Verification
- Ran full test suite across entire repository:
  - **41 of 41 unit and integration tests PASSED** in 23.6s.
- Verified zero secrets committed, `.env.example` in place.
- Verified strict neutrality and metric scope isolation.
