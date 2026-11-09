# MAS — Multi-Agent Software Engineering Team

MAS is a cost-aware multi-agent software engineering research platform designed to minimize language-model invocation and token overhead while maintaining high software generation quality. It is empirically evaluated against ChatDev on the SRDD-20 benchmark using the metrics of the iCoder paper (You et al., *Information and Software Technology* 198 (2026) 108224).

---

## 1. Repository Layout

```
.
├── mas/                    # Core MAS implementation
│   ├── agents/             # Manager, Router, Architect, Developer, Tester, Reviewer
│   ├── analysis/           # AST cycle/impact analyzer, deterministic repair checker, sandbox runner
│   ├── core/               # Workflow state machine, governor, rate limiter, proxy, context slicer
│   └── db/                 # SQLite/PostgreSQL models, session manager, schema
├── eval/                   # Benchmark evaluation harness
│   ├── tasks_v2.json       # Pinned 20 canonical SRDD tasks (4 per major category)
│   ├── category_map.json   # Mapping of 40 SRDD subcategories to 5 iCoder categories
│   ├── runner.py           # Evaluation runner with preflight, estimation, resume, stop-at-budget
│   ├── neutral_evaluator.py# Evaluator measuring Completeness, Executability, Consistency, Quality
│   ├── chatdev_adapter.py  # Pinned ChatDev adapter with Windows UTF-8 and proxy routing
│   ├── reports.py          # Results CSV exporter and statistics markdown generator
│   └── stats.py            # Wilcoxon signed-rank, permutation test, bootstrap 95% CIs, Cohen's d
├── external/
│   └── ChatDev/            # Pinned ChatDev baseline submodule (commit c1c31e2)
├── patches/
│   └── chatdev_local.patch # Clean reproducibility patch for ChatDev against upstream v1.0.0
├── scripts/
│   ├── make_report.py      # Unified reporting script (Tables 1-6 in Markdown, LaTeX, CSV, and figures)
│   ├── setup_chatdev.py    # Automated ChatDev repository setup and patch application
│   ├── select_tasks.py     # Deterministic task selection and category mapping tool
│   ├── audit_scores.py     # Historical audit and score validation tool
│   └── list_models.py      # Available model inspection tool
├── tests/                  # 269 comprehensive unit and integration tests (100% offline, $0 spend)
├── archive/                # Archived legacy pilot logs, exploratory reports, and one-off scratch scripts
├── results.csv             # Official benchmark runs and evaluation metrics
├── RUN_FINAL.md            # Step-by-step benchmark operator run guide
├── DECISIONS.md            # Complete architecture and research decision log (DEC-001 through DEC-039)
├── AGENTS.md               # Strict operational rules and hard constraints for AI agents
└── config.yaml             # Centralized runtime configuration, rate limits, and token caps
```

---

## 2. Research Objective & System Architecture

MAS turns natural-language requirements into working Python software using a token-efficient, quality-gated multi-agent workflow:

1. **Deterministic Complexity Router (Score 0–3: SIMPLE, 4+: STRUCTURED)**: Zero LLM calls. Bypasses the Architect agent on simple tasks.
2. **Architect Agent (STRUCTURED path only)**: Generates minimal UML class models and structured user stories.
3. **Developer Agent**: Implements modular Python code formatted with delimiter blocks (`=== FILE: <name> ===\n<code>\n=== END FILE ===`) for resilient parsing.
4. **Deterministic Repair & Smoke Check**: Inspects AST for syntax errors, stub code (`pass`, `NotImplementedError`, `...`), and smoke test execution before calling other agents.
5. **Tester Agent**: Generates diagnostic pytest suites; tracebacks are capped to 40 lines and 5 failures to prevent context window blowout.
6. **Reviewer Agent & Call Reduction**: Performs semantic review against requirements. When deterministic checks, smoke runs, and internal tests pass cleanly on iteration 1, the Reviewer LLM call is safely skipped, reducing clean first-try execution to $\le 3$ LLM calls.
7. **Adaptive Reflection Loop**: Decides whether to continue refinement or finalize.
8. **Neutral Evaluator**: Measures software quality externally without leaking task-specific hints:
   $$\text{Completeness} = 1 - \frac{\text{unimplemented functions}}{\text{total functions}}$$
   $$\text{Executability} = \text{share of projects running without error}$$
   $$\text{Consistency} = \text{cosine similarity of requirement and code embeddings}$$
   $$\text{Quality} = \text{Completeness} \times \text{Executability} \times \text{Consistency}$$

---

## 3. Free-Tier Google Gemini Benchmark Constraints

This project is constrained to free-tier cloud resources with an authorized spend of **$0.00**:

- **Provider**: Google Gemini API via its OpenAI-compatible endpoint (Google AI Studio).
- **Pinned Model**: Pinned via the `BENCH_MODEL` environment variable (e.g., a Gemini Flash Lite model).
- **Hard Quotas & Governor Enforcement**:
  - Daily Request Limit: 500 requests / day (Governor cap: 450 requests / day with a 10% safety margin).
  - Rate Limits: 12 requests / minute, 200,000 tokens / minute via `SlidingWindowRateLimiter`.
  - Quota Reset Time: Midnight Pacific Time (`America/Los_Angeles`).
  - Per-Run Token Cap: 100,000 provider tokens (fail-closed pre-call gate).
- **Fair Baseline**:
  - Both MAS and ChatDev use the identical model, `temperature=0.0`, `seed=42`, and logging proxy on port 8089.
  - ChatDev requests pass through the same governor and count towards the daily transmission ledger.

---

## 4. Running the Tests

All unit, integration, and regression tests run deterministically with `FakeLLMProvider` without network calls or API usage:

```powershell
# Set UTF-8 encoding (Windows PowerShell)
$env:PYTHONUTF8 = "1"

# Run the complete test suite
python -m pytest tests/ -q
```

All **269 tests** pass cleanly offline.

---

## 5. Running the Final Benchmark

For complete, step-by-step instructions on preflight verification, Day 1 and Day 2 execution, optional ablations (A1–A4), and report generation, refer to **[`RUN_FINAL.md`](./RUN_FINAL.md)**.

### Quick Commands Summary:

```powershell
# 1. Preflight Verification (Offline check, 0 quota used)
python -m eval.runner --preflight

# 2. Estimate Resources and Timeline (0 quota used)
python -m eval.runner --estimate --tasks-file eval/tasks_v2.json --tasks 20 --repeats 3

# 3. Execute Resumable Benchmark (Day 1 / Day 2)
python -m eval.runner --benchmark --live --model $env:BENCH_MODEL --tasks-file eval/tasks_v2.json --repeats 3 --resume --stop-at-budget

# 4. Generate Reports (Tables 1-6 in Markdown, LaTeX, CSV, and figures)
python scripts/make_report.py --results results.csv --manifest eval/benchmark_manifest.json --output-dir reports
```

---

## 6. Reproducibility & Research Integrity Guarantees

- **Rule 1 (Zero Fabricated Results)**: If an experimental table cell has no empirical data, it strictly displays "NOT RUN".
- **Rule 2 (No Task-Specific Prompts)**: Agent prompts work generically for any requirement without domain keywords from any specific SRDD task.
- **Rule 3 (No Metric Inflation)**: Requirement text is never copied into comments or docstrings to artificially inflate consistency.
- **Rule 4 (Honest Counting)**: The first non-infra attempt is official; quality failures count as Quality = 0.0. Retries are permitted only for infrastructure errors (HTTP 429, daily quota ceiling).
- **Rule 5 (Simulation Guard)**: Simulated and fake-provider runs are strictly labeled `SIMULATION_ONLY` and are excluded from all empirical tables, summaries, and hypothesis tests.
