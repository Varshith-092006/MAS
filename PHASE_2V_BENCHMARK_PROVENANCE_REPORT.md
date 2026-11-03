# PHASE 2V: BENCHMARK PROVENANCE AND SIMULATION ISOLATION REPORT

**Status**: READY_FOR_LIVE_PAIRED_RUN (Scheduled for execution at `2026-10-20 00:00:00 UTC`)  
**Date**: October 19, 2026  
**Environment**: Windows, Python 3.12, SQLite `mas.db`, OpenRouter Free-Tier (`cohere/north-mini-code:free`)  
**Network Activity in Phase 2V**: Exactly 0 outbound HTTP requests (Ledger remains 25 / 45)

---

## 1. Separation of Offline Simulation from Live Benchmark Data

A forensic inspection of the Phase 2U offline test output identified that simulated runs (`--model fake`) generated synthetic metrics, tokens, and a mock ChatDev cost ($0.015) that were initially recorded under non-prefixed run IDs (`mas_srdd_educ_01_r1`, `cd_srdd_educ_01_r1`) with status `COMPLETED`.

To protect scientific integrity and ensure that simulated test fixtures can never be conflated with live experimental data or cause primary key collisions:

### Remediation Implemented in Code & Records:
1. **Dedicated Run ID Prefixing (`sim_`)**:
   - In [eval/runner.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/eval/runner.py), all simulated runs (`use_fake=True` or `--model fake`) automatically prefix run IDs with `sim_` (`sim_mas_{t_id}_r{r_num}`, `sim_cd_{t_id}_r{r_num}`).
   - Live runs reserve the canonical IDs (`mas_{t_id}_r{r_num}`, `cd_{t_id}_r{r_num}`).
2. **Explicit Excluded Status (`SIMULATION_ONLY`)**:
   - Simulated runs are tagged with `status: "SIMULATION_ONLY"`, `execution_mode: "SIMULATED"`, `token_provenance: "SIMULATED"`, and `cost: 0.0`.
   - The database table `runs` and [results.csv](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/results.csv) were reconciled to reflect `SIMULATION_ONLY`.
3. **Manifest Live-Gating (`eval/benchmark_manifest.json`)**:
   - Only runs with `status == "COMPLETED"` **and** `execution_mode == "LIVE_API"` can qualify for `is_paired_complete: True` and increment `completed_paired_repeats`.
   - Simulated runs are retained in the audit history under `simulation_runs_excluded: 2`, with `completed_paired_repeats: 0`.
4. **Statistical Report Protection (`eval/stats_report.md`)**:
   - [eval/reports.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/eval/reports.py) was updated to strictly filter out any non-live runs (`execution_mode != "LIVE_API"`).
   - [eval/stats_report.md](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/eval/stats_report.md) now explicitly reports `N=0` live runs, preventing simulated numbers from contaminating permutation tests or superiority tables.

---

## 2. Live-Run Provenance and Research Parity Verification

The following controls have been verified offline across codebase and configurations:

| Dimension | Multi-Agent System (MAS) | ChatDev (Baseline) | Verification Source |
| :--- | :--- | :--- | :--- |
| **Model Condition** | `cohere/north-mini-code:free` | `cohere/north-mini-code:free` | Configured via `resolve_openrouter_model` in `mas/core/llm.py` |
| **Fallback Prohibition** | `"provider": {"allow_fallbacks": false}` | `"provider": {"allow_fallbacks": false}` | Explicit in `mas/core/llm.py` (L258) and `mas/core/proxy.py` (L39) |
| **Task Prompt** | Exact raw canonical description from `tasks.json` | Exact raw canonical description from `tasks.json` | Dispatched identically from `eval/runner.py` |
| **Network Ledger Accounting** | Routed through `GovernedHTTPClient` | Routed via `mas/core/proxy.py` to `GovernedHTTPClient` | Every request counted toward 45-call ceiling in `outbound_transmission_ledger.json` |
| **Serving Identity Verification** | Response model verified against `cohere/north-mini-code:free` | Proxy verifies `actual_model` via `is_model_match` | Mismatch triggers `ModelMismatchError` / HTTP 502; no fallback allowed |
| **Cost & Telemetry** | Derived from provider `usage` block ($0.00 verified) | Derived from proxy-logged provider `usage` ($0.00 verified) | Zero estimated cost for free tier |
| **Dataset SHA-256** | `5ea3c4cb04848e9f009f596b3d059fc6e67b96e00675f7e796eaab5486afec55` | `5ea3c4cb04848e9f009f596b3d059fc6e67b96e00675f7e796eaab5486afec55` | Byte-for-byte identical, strictly unmodified |

---

## 3. Offline Validation of One-Repeat Execution & Governor Budget Gate

### Test 1: Governor Budget Gate on Live Request Command
Command:
```bash
python eval/runner.py --task-id srdd_educ_01 --repeats 1 --repeat-no 1 --systems mas,chatdev --model cohere/north-mini-code:free
```
**Observed Execution Output**:
```
======================================================================
STARTING EMPIRICAL BENCHMARK: SRDD20
Tasks: 1 | Systems: ['mas', 'chatdev'] | Repeats: 1 (Start Repeat: 1) | Model: cohere/north-mini-code:free
======================================================================

[GOVERNOR HALT] Insufficient remaining daily transmissions for benchmark batch:
  Current UTC date: 2026-10-19
  Used attempts today: 25 / 45
  Remaining attempts: 20 (Minimum required with safety margin: 25)
  Execution safely stopped before ceiling breach.
  Scheduled next execution after UTC reset: 00:00:00 UTC
```
- **Result**: **PASSED**. The runner verified that the remaining allowance (20) was below the minimum safe threshold (25) for a paired batch (forecast 20–32 attempts), halting immediately without sending any network request.

### Test 2: Offline Simulation Execution (`--model fake`)
Command:
```bash
python eval/runner.py --task-id srdd_educ_01 --repeats 1 --repeat-no 1 --systems mas,chatdev --model fake
```
**Observed Execution Output**:
```
======================================================================
STARTING EMPIRICAL BENCHMARK: SRDD20
Tasks: 1 | Systems: ['mas', 'chatdev'] | Repeats: 1 (Start Repeat: 1) | Model: fake
======================================================================

[1/1] Evaluating Task: Science Question Solver (srdd_educ_01) [Education]
   [SIMULATION_ONLY] MAS:     Quality=0.0000 | Tokens=1626 | Quality/1k=0.0000
   [SIMULATION_ONLY] ChatDev: Quality=0.4286 | Tokens=3000 | Quality/1k=0.1429

Manifest Updated: eval\benchmark_manifest.json (Completed Paired Repeats: 0)
```
- **Result**: **PASSED**. Correctly tagged as `SIMULATION_ONLY`, zero network calls made, `completed_paired_repeats` remained `0`.

### Test 3: Offline Regression Suite
- Ran `pytest tests/ -q` $\rightarrow$ **150 passed, 0 failed, 2 warnings** in 16.90s.

---

## 4. Transmission Accounting & Reset Boundary

- **UTC Date**: `2026-10-19`
- **Total HTTP Transmissions Consumed Today**: **25 attempts**
  - Metadata queries: 2
  - Model generation calls: 23 (Tasks B, C, D development pilots)
- **Remaining Daily Allowance**: **20 attempts**
- **Internal Daily Ceiling**: **45 attempts**
- **Next UTC Reset Boundary**: `2026-10-20 00:00:00 UTC` (5:30 AM IST)

Following the reset boundary, the transmission counter will reset to 0, providing the full 45-request quota.

---

## 5. Live Launch Procedure (Post-Reset)

Immediately following `2026-10-20 00:00:00 UTC`, execute the single paired repeat:

```bash
python eval/runner.py --task-id srdd_educ_01 --repeats 1 --repeat-no 1 --systems mas,chatdev --model cohere/north-mini-code:free
```

### Safety Rules for Live Execution:
1. One paired repeat at a time (`--repeats 1 --repeat-no 1`).
2. Single metadata preflight (`GET /api/v1/key`) counts as transmission #1.
3. If MAS encounters an error, stop immediately before ChatDev (ChatDev marked `SKIPPED`).
4. Inspect tokens, latency, cost ($0.00), and Level 2 neutral evaluation results before initiating repeat 2.

---

## 6. Readiness Declaration

**READY_FOR_LIVE_PAIRED_RUN**

The single-repeat execution pipeline, provenance verification, governor pre-execution safety gate, and simulation isolation mechanisms are verified and ready for live execution following the `2026-10-20 00:00:00 UTC` reset boundary.
