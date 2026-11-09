# Operator Run Guide: MAS vs. ChatDev Final Benchmark

This document provides the exact, step-by-step procedure to execute the empirical comparison between **MAS** and **ChatDev** on the SRDD-20 dataset using free-tier resources under Google Gemini / OpenRouter constraints.

---

## Before You Start Checklist

1. **Operating Environment**:
   - Windows 11 with PowerShell.
   - Python 3.11 with virtual environment activated.
   - Set UTF-8 encoding:
     ```powershell
     $env:PYTHONUTF8 = "1"
     $env:PYTHONIOENCODING = "utf-8"
     ```

2. **Environment Variables**:
   - Confirm your provider API key is set in environment (never commit `.env` or log keys):
     ```powershell
     # For Google AI Studio (Gemini)
     $env:PROVIDER_API_KEY = "your-api-key-here"
     $env:PROVIDER_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
     
     # Do NOT guess model IDs. Run list_models.py to inspect exact available models:
     python scripts/list_models.py
     
     # Set BENCH_MODEL to the exact Flash Lite model ID reported (e.g. gemini-2.5-flash-lite or exact listed model)
     $env:BENCH_MODEL = "<exact-model-id-from-list_models>"
     ```
   - If using OpenRouter:
     ```powershell
     $env:PROVIDER_API_KEY = "your-openrouter-key-here"
     $env:PROVIDER_BASE_URL = "https://openrouter.ai/api/v1"
     $env:BENCH_MODEL = "cohere/north-mini-code:free"
     ```

3. **Rate Limits & Spending Constraints**:
   - Authorized Spend: **$0.00**.
   - Governor Cap: 450 requests/day (10% safety margin below 500 free daily limit).
   - Rate Limits: 12 requests per minute, 200,000 tokens per minute.
   - Quota Reset Time: Midnight Pacific Time (America/Los_Angeles).

---

## Step 1: Preflight Verification Check

Run the offline preflight verification tool. This executes zero model calls and consumes 0 quota:

```powershell
python -m eval.runner --preflight
```

**Expected Output**:
```
======================================================================
MAS BENCHMARK PREFLIGHT VERIFICATION (OFFLINE CHECKLIST)
======================================================================
[PASS] ChatDev Submodule:        Pinned at commit c1c31e2886
[PASS] Provider API Key:         Configured (length=..., non-empty)
[PASS] Pinned Benchmark Model:   <your model ID>
[PASS/WARN] Embedder Engine:     Operational offline / Lexical fallback
[PASS] Logging Proxy:            Can start and stop cleanly on port 8089
[PASS] Daily Quota Remaining:    450 requests (>= 15 required)
----------------------------------------------------------------------
PREFLIGHT STATUS: ALL CHECKS PASSED — READY FOR BENCHMARK
======================================================================
```
If any check reports `[FAIL]`, resolve it before proceeding.

---

## Step 2: Day 1 Benchmark Execution

Start the official Day 1 benchmark run across 20 tasks with `--repeats 1`, `--systems mas,chatdev`, and `--require-embeddings`. The runner automatically stops cleanly when daily budget headroom is reached:

```powershell
python -m eval.runner --benchmark --live --systems mas,chatdev --model $env:BENCH_MODEL --tasks-file eval/tasks_v2.json --repeats 1 --require-embeddings --resume --stop-at-budget
```

### What to Expect:
- Runs tasks sequentially through MAS, then ChatDev.
- Delimiter block parsing ensures robust code generation.
- Reviewer is skipped on clean runs to minimize API calls (<= 3 LLM calls on clean runs).
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
python -m eval.runner --benchmark --live --systems mas,chatdev --model $env:BENCH_MODEL --tasks-file eval/tasks_v2.json --repeats 1 --require-embeddings --resume --stop-at-budget
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

