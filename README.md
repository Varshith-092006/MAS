# MAS — Multi-Agent Software Engineering Team

MAS is a cost-aware multi-agent software engineering research platform designed to reduce token overhead while retaining high software generation quality.

> 🎓 **Final Year Project Submission Bundle:**  
> Complete documentation, architecture diagrams, testing evidence, and dissertation report are available in the **[`submission/`](./submission/README.md)** directory:
> - [Project Overview & Problem Statement](./submission/PROJECT_OVERVIEW.md)
> - [System Architecture & Workflow Specification](./submission/SYSTEM_ARCHITECTURE.md)
> - [Agent Roles & Responsibilities](./submission/AGENT_RESPONSIBILITIES.md)
> - [Installation & Operations Manual](./submission/INSTALLATION_AND_OPERATIONS.md)
> - [Testing Methodology & 201-Test Verification Report](./submission/TESTING_AND_VERIFICATION.md)
> - [Benchmark Methodology & Empirical Results](./submission/BENCHMARK_METHODOLOGY_AND_RESULTS.md)
> - [Final Project Report / Dissertation](./submission/FINAL_PROJECT_REPORT.md)

---

## 1. Research Objective & System Architecture

MAS implements conditional routing, deterministic structural analysis, token-efficient context slicing, and adaptive stopping:

```
Requirement
    │
    ▼
 Manager ──► Deterministic Complexity Router (0 LLM calls)
                 │
                 ├──[Score 0–3: SIMPLE]──────────────┐
                 │                                   │
                 └──[Score 4+: STRUCTURED]          │
                           │                         │
                           ▼                         │
                       Architect                     │
                    (Minimal UML + UserStory)        │
                           │                         │
                           ▼                         │
                      Developer ◄────────────────────┘
                           │
                           ▼
                 CodePatch Generated
                           │
                           ▼
                  Schema Validation (Retry + Rollback)
                           │
                           ▼
                 AST Dependency Analyzer (Cycles & Impact)
                           │
                           ▼
                 MAS Diagnostic Tests (Internal Scope)
                           │
                           ▼
                 Quality Tools (Ruff, Bandit, Radon)
                           │
                           ▼
                 GPT-4o-mini Reviewer (Semantic Only)
                           │
                           ▼
                 Adaptive Stopper (Reflection)
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
        [CONTINUE]                    [STOP]
      (Context Sliced)             Finalize Run
                                         │
                                         ▼
                            Hidden Neutral Evaluator
                      (Completeness, Executability, Consistency)
```

---

## 2. Setup & Installation

### Local Python Environment (Python 3.11)
```bash
# Clone and enter directory
cd "Final Year Project"

# Install editable package and dependencies
pip install -e .

# Configure environment variables
cp .env.example .env
# Set OPENROUTER_API_KEY in .env (Free model 'openrouter/free' enabled by default)
```

### Docker Compose Startup (Full Stack: PostgreSQL + API + Frontend)
```bash
docker compose up -d
```
Services started:
- **API Server & Logging Proxy**: `http://localhost:8000` (Proxy on port `8089`)
- **PostgreSQL Database**: `localhost:5432` (`mas_db`)
- **React Run Visualizer Frontend**: `http://localhost:3000`

---

## 3. CLI Commands

### A. Run Single Tasks (Deterministic Fake Model)
```bash
# Simple task (bypasses Architect)
mas run --model fake --task "Write a python calculator that adds two integers"

# Structured task (invokes Architect with UML & User Stories)
mas run --model fake --task "Build a multi-user inventory system with a SQLite database, user login authentication, admin and staff roles, REST API endpoints, analytics metrics reporting, and an approval workflow lifecycle."

# Run from file
mas run --model fake --file requirement.txt
```

### B. Run Single Tasks (OpenRouter Models & Free Models)
```bash
# Free model arm (Default: openrouter/free, zero API cost)
mas run --model openrouter/free --task "Build a task manager CLI"

# Specific free model on OpenRouter (e.g., Gemma 4, Llama 3.3, Qwen 2.5 Coder)
mas run --model google/gemma-4-31b-it:free --task "Build a task manager CLI"
mas run --model meta-llama/llama-3.3-70b-instruct:free --task "Build a task manager CLI"

# OpenAI models via OpenRouter
mas run --model openai/gpt-4o --task "Build a task manager CLI"
mas run --model openai/gpt-4o-mini --task "Build a task manager CLI"
```

### C. Inspect Runs, Event Logs, and Metrics
```bash
# View run status
mas status <RUN_ID>

# Stream/view append-only audit event logs
mas logs <RUN_ID>

# View recorded metrics (Neutral vs Internal scope)
mas results <RUN_ID>
```

### D. Requirement Change Requests
```bash
mas change <RUN_ID> --request "Add discount calculation logic and deprecate the old tax method"
```

### E. Evaluation Benchmark, Dry Run & Pilot
```bash
# Dry run: prints 300 core runs & 8.4M token envelope (0 model calls)
mas evaluate --dry-run
# or
python eval/runner.py --dry-run

# Run 1-Task Pilot (MAS vs ChatDev baseline under identical conditions)
python eval/runner.py --pilot --model fake
# Real model pilot:
# python eval/runner.py --pilot --model gpt-4o

# Main benchmark evaluation (20 tasks x 3 repeats x 2 systems = 120 runs)
mas evaluate --benchmark srdd20 --system mas --model gpt-4o --repeats 3
mas evaluate --benchmark srdd20 --system chatdev --model gpt-4o --repeats 3

# Cheaper MAS arm (20 tasks x 3 repeats = 60 runs)
mas evaluate --benchmark srdd20 --system mas --model gpt-4o-mini --repeats 3

# Ablation experiment (A1–A6 configurations on GPT-4o-mini)
mas ablate --feature router
mas ablate --feature ast
mas ablate --feature context_slicing
mas ablate --feature cheap_reviewer
mas ablate --feature adaptive_stop
mas ablate --feature uml_always_on
```

---

## 4. Running the Test Suite
All 41 unit and integration tests run deterministically with `FakeLLMProvider` without requiring an OpenAI API key:

```bash
python -m pytest tests -v
```

Test coverage includes:
- **ComplexityRouter**: 0 LLM calls, regex features, separator rule, word count, 10 draft diagnostics.
- **Artifact Schemas & Validator**: All 7 Pydantic schemas, validation error reporting.
- **Token Logger**: 60,000 hard token cap, cost calculation, provider usage preservation.
- **AST Analyzer**: DFS cycle detection, synthetic circular dependency ($A \to B \to C \to A$), unresolved imports, transitive reverse-dependency impact set.
- **Context Slicer**: Planned files in Iteration 1, $\text{changed} \cup \text{impact set}$ in Iteration 2+.
- **Fault Recovery**: Invalid artifact $\to$ retry once $\to$ rollback $\to$ rerun recovery.
- **Fault Injection**: F1 malformed UML, F2 incomplete UserStory.
- **Neutral Evaluator & Scorers**: Completeness, executability, MiniLM embedding consistency, quality product, shared fixed test harness.
- **Statistics Engine**: Two-sided paired permutation test ($\alpha=0.05$), Cohen's $d$, confidence intervals.
- **FastAPI Endpoints**: REST endpoints and WebSocket event streaming.
- **ChatDev Adapter**: Pinned commit adapter through local proxy.

---

## 5. React Frontend Visualizer

Access `/runs/:runId` on `http://localhost:3000` to inspect:
- **RunHeader**: Run ID, system, model, provider tokens, estimated cost.
- **StatusBanner**: Status badge (`COMPLETED`, `RUNNING`, `FAILED`, `CANCELLED`), complexity route, iteration counter, stop reason.
- **AgentLog**: Live append-only sequence of agent actions and redactions.
- **TokenCostChart**: Progress against the 60,000 hard token cap.
- **MetricsTable**:
  - **Neutral cross-system metrics**: Quality ($C \times E \times Sim$), Quality per 1k tokens, Completeness, Executability, Consistency, Shared Fixed Test, Ruff, Bandit, Radon.
  - **MAS internal diagnostics**: pytest pass rate, coverage, adaptive score ($S_t$).

---

## 6. Security & Reproducibility Guarantees
- **No Committed Secrets**: `.env.example` provided; API keys and secrets redacted from event logs.
- **Isolated Sandbox**: Docker container execution with `--network none`, 512 MB memory limit, 1 CPU, 64 PIDs, read-only base image, writable `/workspace` only, and 30–60s timeout.
- **Audit Logging**: `agent_events` table is append-only.
- **Reproducibility**: Run config snapshots store model version, seed 42, temperature 0, library versions, Docker image tag, and SHA-256 hash of `eval/checks/level2_checks.json`.
