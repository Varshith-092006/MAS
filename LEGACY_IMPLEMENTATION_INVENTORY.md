# LEGACY IMPLEMENTATION INVENTORY
## Comprehensive Codebase, Architecture, and Empirical Asset Inventory

**Date of Audit:** October 17, 2026  
**Audited Location:** `C:\Users\The Mighty King\Desktop\Final Year Project`  
**Git HEAD:** `36888d2` (branch: `master`)  
**Document Purpose:** Baseline technical inventory of all existing agents, orchestration workflows, evaluation metrics, databases, frontend components, and research assets prior to implementation.

---

## 1. Agent Architecture & Orchestration (`mas/agents/` & `mas/core/`)

The MAS codebase implements a modular multi-agent software engineering pipeline adhering to the Low-Level Design (LLD) specifications.

### 1.1 Agent Implementations
- **`ManagerAgent` ([mas/agents/manager.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/mas/agents/manager.py)):**
  - Evaluates user requirements, determines project complexity via `ComplexityRouter`, generates structured `TaskPlan` artifacts (sprint goals, file allocation, complexity labeling).
  - Emits JSON strictly validating against Pydantic schema `TaskPlan`.
- **`ArchitectAgent` ([mas/agents/architect.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/mas/agents/architect.py)):**
  - Activated for `STRUCTURED` tasks. Generates system component breakdown, Mermaid UML class diagrams, module dependencies, and `UserStory` specifications.
  - Emits `Architecture` and `UserStory` schema-compliant artifacts.
- **`DeveloperAgent` ([mas/agents/developer.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/mas/agents/developer.py)):**
  - Generates full source code files adhering to the unified software generation contract (`BENCHMARK_TASK_CONTRACT.md`).
  - Injects target file structures into a single `CodePatch` artifact mapping relative file paths to non-truncated source code strings.
- **`TesterAgent` ([mas/agents/tester.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/mas/agents/tester.py)):**
  - Formulates verification cases, executes sandboxed test suites via `SandboxRunner`, and generates structured `TestReport` artifacts (pass rates, test counts, logs).
- **`ReviewerAgent` ([mas/agents/reviewer.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/mas/agents/reviewer.py)):**
  - Performs code review across maintainability, correctness, and security. Generates `ReviewReport` artifacts approving or rejecting code for iterative refinement.
- **`ComplexityRouter` ([mas/agents/router.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/mas/agents/router.py)):**
  - Fast, deterministic regex-based rule engine. Incurs **zero LLM token overhead**. Routes tasks with scores 0–3 to `SIMPLE` (skipping `ArchitectAgent`) and scores $\ge 4$ to `STRUCTURED`.
- **`BaseAgent` & Artifact Validation ([mas/agents/base.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/mas/agents/base.py)):**
  - Implements the 5-step artifact lifecycle contract: production, Pydantic validation, retry with error feedback, git-based rollback, and database persistence (`_record_artifact`).

### 1.2 Core Orchestration & Execution State
- **Workflow Engine ([mas/core/workflow.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/mas/core/workflow.py)):**
  - Controls lifecycle transitions: `manager -> architect -> developer -> tester -> reviewer -> manager (reflection)`.
  - Supports adaptive stopping policy (stops when all tests pass, review approved, or max iterations reached).
  - Maintains `generate_artifacts_manifest()` creating SHA-256 manifests of all written source files.
- **State Schema ([mas/core/state.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/mas/core/state.py)):**
  - Typed dictionary `MASState` tracking `run_id`, `task_id`, `iteration`, `changed_files`, `artifacts`, `metrics`, `logs`.
- **LLM Abstraction & Routing ([mas/core/llm.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/mas/core/llm.py)):**
  - `OpenRouterProvider`: Connects to OpenRouter (`https://openrouter.ai/api/v1`).
  - Strict fallback prohibition: Enforces `provider: { allow_fallbacks: False }`.
  - Allowlist verification: `is_model_match()` validates serving models against `VERIFIED_MODEL_SNAPSHOTS`.
  - Secret redaction: `redact_sensitive_string()` and `sanitize_headers_dict()` protect credentials.
  - `TokenLogger`: Records provider-reported token usage and enforces per-run engineering caps (60,000 tokens).

---

## 2. Baseline Comparative Integration (`eval/`)

- **ChatDev Adapter ([eval/chatdev_adapter.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/eval/chatdev_adapter.py)):**
  - Interfaces with the external ChatDev submodule located in `external/ChatDev`.
  - Generates phase and role configurations, initiates ChatDev chains, isolates workspaces, and extracts generated source code.
- **Logging Proxy ([mas/core/proxy.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/mas/core/proxy.py)):**
  - Local FastAPI proxy intercepting external OpenAI-compatible requests from ChatDev.
  - Injects `allow_fallbacks: false`, verifies requested vs. returned models, logs usage to `TokenLogger`, and returns HTTP 502 on model mismatches.

---

## 3. Evaluation Engine & Metrics (`eval/scorers/` & `eval/`)

- **Neutral Evaluator ([eval/neutral_evaluator.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/eval/neutral_evaluator.py)):**
  - Independent evaluator decoupled from MAS agent feedback loops.
  - Evaluates generated software against standardized metrics and stores records in `mas.db` under scope `neutral`.
- **Primary Quality Metric ($Q = C \times E \times S$) ([eval/scorers/icoder_metrics.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/eval/scorers/icoder_metrics.py)):**
  - **Completeness ($C$):** $1 - (\text{unimplemented\_functions} / \text{total\_functions})$ via AST parsing.
  - **Executability ($E$):** Process-level smoke execution under sandbox limits (clean import and returncode 0).
  - **Consistency ($S$):** Cosine semantic similarity between requirement prompt and aggregated code.
- **Shared Test Harness ([eval/scorers/shared_test.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/eval/scorers/shared_test.py)):**
  - Calculates $\text{SharedTest} = 0.5 \times \text{Level1\_Smoke} + 0.5 \times \text{Level2\_Checks}$.
- **Frozen Level 2 Neutral Behavioral Suite ([eval/checks/test_srdd_educ_01.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/eval/checks/test_srdd_educ_01.py)):**
  - Independent 4-assertion suite verifying module imports, object instantiation, multi-domain science problem solving (Physics, Chemistry, Biology), and clean termination.
- **Static Quality Tools ([mas/analysis/quality_tools.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/mas/analysis/quality_tools.py)):**
  - Runs Ruff (linting), Bandit (security AST analysis), and Radon (cyclomatic complexity & maintainability index).

---

## 4. Benchmark Datasets & Specifications

- **Canonical Task Catalog ([eval/tasks.json](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/eval/tasks.json)):**
  - Exactly 20 tasks evenly divided across 5 domains: Education (4), Work (4), Life (4), Games (4), and Utility/Creation (4).
  - SHA-256: `5ea3c4cb04848e9f009f596b3d059fc6e67b96e00675f7e796eaab5486afec55`.
- **Full Source Dataset ([data_attribute_format.csv](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/data_attribute_format.csv)):**
  - Complete 1,201-row SRDD dataset (501,992 bytes).
- **Task Contract ([BENCHMARK_TASK_CONTRACT.md](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/BENCHMARK_TASK_CONTRACT.md)):**
  - Unified software contract: Python 3.11+, standard entry point (`main.py` / `app.py`), 1 CPU, 512MB RAM, 45-second execution timeout, isolated network.

---

## 5. Database & Experimental Records (`mas.db`)

SQLite database `mas.db` contains 9 core tables:
- **`tasks` (20 rows):** The canonical SRDD-20 task definitions.
- **`runs` (7 rows):**
  1. `live_pilot_mas_1791691672` — Quarantined (`MODEL_MISMATCH_DIAGNOSTIC`).
  2. `mas_srdd_educ_01_live` — Quarantined (`MODEL_MISMATCH_DIAGNOSTIC`).
  3. `cd_srdd_educ_01_live` — Quarantined (`DIAGNOSTIC_RUN`).
  4. `mas_srdd_educ_01_canonical` — Halted at fairness gate (`FAILED`, HTTP 402 Insufficient Credits).
  5. `SKIPPED_DUE_TO_MAS_FAILURE` — ChatDev Stage 1 matched skip (`SKIPPED`).
  6. `mas_srdd_educ_01_free_exp` — Completed under `cohere/north-mini-code:free` ($Q = 0.8500$).
  7. `cd_srdd_educ_01_free_exp` — Completed under `cohere/north-mini-code:free` ($Q = 0.0000$).
- **`metrics` (88 rows):** Scope-separated metrics (`neutral` vs. `internal`).
- **`model_calls` (65 rows):** Telemetry including `requested_model`, `actual_model`, `request_id`, tokens, latency, cost.
- **`artifacts` (40 rows):** Pydantic-validated intermediate agent artifacts.
- **`agent_events` (161 rows):** Append-only audit log of agent state transitions and tool executions.

---

## 6. Automated Test Suites (`tests/`)

The repository contains 17 test files and a global pytest configuration fixture (`tests/conftest.py`) routing test DB operations to `test_mas.db`:
- `test_research_validity.py` (29 tests): Proves fallback prohibition, model mismatch quarantining, token provenance, and pricing integrity.
- `test_openrouter_error_handling.py` (6 tests): Validates HTTP 401, 402, 429 status code preservation, header sanitization, and secret redaction.
- `test_neutral_evaluator.py` (6 tests): Validates $C, E, S, Q$ calculations and check hashes.
- `test_ast_analysis.py` (3 tests): Validates circular dependencies and AST transitive impact slicing.
- `test_change_request.py` (2 tests): Tests change diffs and obsolete code detection.
- `test_context_slicer.py` (2 tests): Verifies context reduction across iterations.
- `test_end_to_end_cp1.py` (2 tests): Full multi-agent workflow validation.
- `test_evaluation_runner.py` (2 tests): Dry-run zero token calls and ChatDev adapter tests.
- `test_fault_injection.py` (2 tests): Malformed artifact recovery tests.
- `test_fault_recovery.py` (1 test): Rollback recovery verification.
- `test_quality_tools.py` (3 tests): Static tool integration tests.
- `test_router.py` (5 tests): Regex complexity routing rules.
- `test_schemas.py` (7 tests): JSON Schema exports and validation for all 7 artifacts.
- `test_statistics.py` (3 tests): Non-parametric statistical distribution tests.
- `test_token_logger.py` (2 tests): Token accumulation and cap enforcement.
- `test_api.py` (1 test): REST API route tests.

**Execution Status:** **77 passed, 0 failed, 2 warnings** in 6.78 seconds.

---

## 7. Frontend Research Dashboard (`frontend/`)

- Built with **React 18**, **Tailwind CSS**, and **Vite 5.4.21**.
- Key Views & Components:
  - `DashboardOverview.jsx`: System status, active models, quick run metrics.
  - `AnalyticsDashboard.jsx`: Statistical comparisons ($Q, C, E, S$, tokens, cost) and audit provenance quarantine card.
  - `RunsTable.jsx`: Full sortable/filterable ledger with browser CSV export.
  - `RunHeader.jsx`: Visual provenance banners (Emerald for Live GPT-4o, Cyan for Free Model Exploratory, Amber for Simulated).
  - `RunVisualizer.jsx`: Live Gantt chart, agent timeline, and file inspector.
  - `ICoderReference.jsx`: Published literature values from You et al. (*IST*, 2026).
- **Production Build:** Passes cleanly (`npm run build` completed in 38.64s with 0 errors).

---

## 8. Known Deficiencies & Roadmap Alignment

1. **Semantic Consistency Fallback Calibration:**
   - In `eval/scorers/icoder_metrics.py`, the fallback consistency heuristic has an artificial base floor of $0.85$, awarding $S = 0.8500$ even on zero keyword recall. This requires recalibration in the next methodology revision.
2. **Process Executability vs. Domain Behavioral Correctness:**
   - $E = 1.0000$ currently measures process-level import/execution success rather than domain problem solving. Domain assertions must be surfaced as an explicit separate metric ($Q_{\text{behavioral}}$).
3. **OpenRouter Rate Limits:**
   - Free models are constrained by a 50 requests/day account quota.
4. **Account Credit Balance:**
   - Paid OpenAI/GPT-4o benchmark is halted due to $0.00 credit balance on OpenRouter.
