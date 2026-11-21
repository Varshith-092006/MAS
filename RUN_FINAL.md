# Operator Run Guide: MAS vs. ChatDev Final Benchmark

This document provides the exact, step-by-step procedure to execute the empirical comparison between **MAS** and **ChatDev** on the SRDD-20 dataset using the **Google Gemini API free tier**.

> [!IMPORTANT]
> The official benchmark provider is **Google Gemini API** (aistudio.google.com). OpenRouter is not permitted for official results (see DECISIONS.md DEC-013). All commands below target the Gemini endpoint.

---

## Step 0: Set Up Provider Environment

### 0a. Copy and fill in `.env`

```powershell
Copy-Item .env.example .env
# Then open .env in a text editor and fill in:
#   PROVIDER_API_KEY  — your Google AI Studio key (starts with AIza)
#   PROVIDER_BASE_URL — already set in the example (keep the trailing slash)
#   BENCH_MODEL       — leave blank for now; fill after running list_models
```

### 0b. Discover the exact model ID

```powershell
$env:PYTHONUTF8 = "1"
python scripts/list_models.py
```

The script prints `Provider: gemini (generativelanguage.googleapis.com)` at the top, then lists all available models. Identify the Flash Lite row (e.g. `gemini-3.5-flash-lite`) and set it in `.env`:

```
BENCH_MODEL=gemini-3.5-flash-lite
```

> [!CAUTION]
> Do NOT copy the `google/` prefix. The Gemini endpoint uses bare IDs like `gemini-3.5-flash-lite`, not `google/gemini-3.5-flash-lite`. The preflight will warn you if the prefix is present.

---

## Step 1: Preflight Verification

Run the offline preflight verification. Zero model calls, zero quota consumed:

```powershell
python -m eval.runner --preflight
```

**Expected Output** (all lines should show `[PASS]`):

```
======================================================================
MAS BENCHMARK PREFLIGHT VERIFICATION (OFFLINE CHECKLIST)
======================================================================
[INFO] Provider type:            gemini (generativelanguage.googleapis.com)
[INFO] Base URL:                 https://generativelanguage.googleapis.com/v1beta/openai
[INFO] BENCH_MODEL:              gemini-3.5-flash-lite
[INFO] Settings source:          PROVIDER
[PASS] ChatDev Submodule:        Pinned at commit c1c31e2886
[PASS] Provider API Key:         Configured (length=39, looks like a Google key ✓)
[PASS] Pinned Benchmark Model:   gemini-3.5-flash-lite
[PASS] Embedder Engine:          Operational offline (dimension=384)
[PASS] Logging Proxy:            Can start and stop cleanly on port 8089
[PASS] Daily Quota Remaining:    450 requests (>= 15 required)
----------------------------------------------------------------------
PREFLIGHT STATUS: ALL CHECKS PASSED — READY FOR BENCHMARK
======================================================================
```

If any line shows `[FAIL]`, fix that issue before continuing. `[WARN]` lines are non-fatal.

---

## Step 2: Smoke Test (one task, all systems, live)

The smoke test runs the **first task only** with both systems against the real API. It prints token counts, requests used, and the exact model name the provider confirmed.

**You must run this yourself** (the agent will not run live calls):

```powershell
python -m eval.runner --smoke --live --systems mas,chatdev,single --model $env:BENCH_MODEL --tasks-file eval/tasks_v2.json
```

Confirm the summary output shows the correct model name and reasonable token counts before proceeding to the full benchmark.

---

## Step 3: Day 1 Benchmark Execution

Start the official Day 1 benchmark run across 20 tasks with `--repeats 1`, `--systems mas,chatdev,single`, and `--require-embeddings`. The runner automatically stops cleanly when daily budget headroom is reached:

```powershell
python -m eval.runner --benchmark --live --systems mas,chatdev,single --model $env:BENCH_MODEL --tasks-file eval/tasks_v2.json --repeats 1 --require-embeddings --resume --stop-at-budget
```

### What to Expect:
- Runs tasks sequentially through MAS, then ChatDev.
- Delimiter block parsing ensures robust code generation.
- The Tester is deterministic (0 LLM calls); the Reviewer runs once per run, so a clean MAS run is 3 LLM calls (Manager, Developer, Reviewer). The single-agent baseline is 1 call per task.
- When daily allowance reaches the governor safety threshold (< 12 transmissions remaining), the runner prints:
  ```
  [BUDGET GOVERNOR] Daily allowance ceiling reached (438 / 450 transmissions).
  [RESUMABLE STOP] Stopping cleanly before daily quota breach.
  ```
- All progress is saved immediately in `eval/benchmark_manifest.json` and `results.csv`.

---

## Step 3: Day 2 Benchmark Execution

After midnight Pacific Time (America/Los_Angeles), the quota ledger automatically rolls over to the new day.

Run the exact same command to resume where Day 1 stopped:

```powershell
python -m eval.runner --benchmark --live --systems mas,chatdev,single --model $env:BENCH_MODEL --tasks-file eval/tasks_v2.json --repeats 1 --require-embeddings --resume --stop-at-budget
```

### Why Resume is Safe:
- `--resume` inspects existing official rows in `eval/benchmark_manifest.json`.
- Completed tasks are skipped instantly with `[SKIPPED] Task already has official row on resume`.
- Any interrupted or stopped run from Day 1 is re-executed fresh from scratch.
- Zero completed work is duplicated.

---

## Step 4: Optional Ablation Runs (A1–A4)

To evaluate the specific modular architectural contributions of MAS (for thesis Section 5), execute ablations:

```powershell
# A1: Always Architect (No Complexity Router)
python -m eval.runner --benchmark --live --model $env:BENCH_MODEL --tasks-file eval/tasks_v2.json --tasks 10 --repeats 1 --ablation A1 --resume --stop-at-budget

# A2: Full Repo Context (No AST Slicing)
python -m eval.runner --benchmark --live --model $env:BENCH_MODEL --tasks-file eval/tasks_v2.json --tasks 10 --repeats 1 --ablation A2 --resume --stop-at-budget

# A3: No Evidence Review (No AST/Ruff/Bandit deterministic checks)
python -m eval.runner --benchmark --live --model $env:BENCH_MODEL --tasks-file eval/tasks_v2.json --tasks 10 --repeats 1 --ablation A3 --resume --stop-at-budget

# A4: Single Iteration (No Reflection Loop)
python -m eval.runner --benchmark --live --model $env:BENCH_MODEL --tasks-file eval/tasks_v2.json --tasks 10 --repeats 1 --ablation A4 --resume --stop-at-budget
```

---

## Step 5: Report Generation

Once all tasks have completed, generate all tables, statistics, figures, and LaTeX documents:

```powershell
python scripts/make_report.py --results results.csv --manifest eval/benchmark_manifest.json --output-dir reports
```

### Generated Outputs:
- **Terminal output**: Full Markdown tables (Tables 1 to 6).
- `reports/benchmark_report.md`: Markdown document ready for GitHub / reading.
- `reports/tables.tex`: Valid LaTeX tables ready to `\input{...}` into your LaTeX thesis.
- `reports/summary.csv`: Machine-readable summary statistics.
- `reports/figures/quality_boxplot.png`: Quality distribution boxplot (if matplotlib installed).
- `reports/figures/quality_vs_tokens.png`: Quality vs. token overhead scatter (if matplotlib installed).

---

### 5b. Results dashboard (offline, zero model calls)

```powershell
python scripts/make_dashboard.py
```

Writes `reports/dashboard.html` (open it in any browser, no internet needed) and `reports/dashboard_data.json`.
It has three separated tiers: **OFFICIAL** (official live Gemini runs: MAS vs ChatDev vs single-agent,
bootstrap CIs, % change, paired Wilcoxon, per-agent tokens and latency, ablations), **EXPLORATORY**
(older real calls recorded in `mas.db`, labelled and never shown as results) and the paper's
**published** numbers (indicative only). Empty official tables show NOT RUN.

> The `single` system is a one-call, single-agent baseline (1 request per task). It costs almost
> nothing on the free tier and shows what the extra agents add. Drop it from `--systems` if you only
> want MAS vs ChatDev.

---

## Step 6: Git Commit of Results

Commit the empirical results:

```powershell
git add results.csv eval/benchmark_manifest.json eval/outbound_transmission_ledger.json reports/
git commit -m "Benchmark: Completed official empirical comparison on SRDD-20"
```

---

## Troubleshooting & Maintenance

### 1. What happens if HTTP 429 occurs?
- The `SlidingWindowRateLimiter` enforces 12 RPM / 200k TPM. If upstream still returns HTTP 429, the governor catches it, records it in the ledger, and halts the run gracefully as `STOPPED_PROVIDER_QUOTA`.
- **Action**: Wait 1–2 minutes (for per-minute resets) or wait until midnight Pacific (for daily resets), then re-run with `--resume`.

### 2. How to verify spend is strictly $0.00?
- Run:
  ```powershell
  python -c "import json; m=json.load(open('eval/benchmark_manifest.json')); costs=[r.get('cost',0) for r in m.get('runs',[])]; print('Total Spend: $' + str(sum(costs)))"
  ```
- Output must be: `Total Spend: $0.0`.

### 3. How to check remaining daily quota without spending requests?
- Run:
  ```powershell
  python -c "from mas.core.governor import global_governor; print(global_governor.get_ledger_stats())"
  ```
- Shows total attributable attempts, successful calls, and remaining quota for the active Pacific calendar day.

### 4. How to re-run a single failed task?
- To re-run only a single task (e.g. `srdd_educ_01` repeat 1):
  ```powershell
  python -m eval.runner --task-id srdd_educ_01 --repeat-no 1 --live --model $env:BENCH_MODEL
  ```
- The runner resolves the next sequential attempt ID (e.g. `attempt2`) without overwriting previous historical logs.

