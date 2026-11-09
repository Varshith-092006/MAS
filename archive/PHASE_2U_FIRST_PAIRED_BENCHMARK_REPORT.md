# PHASE 2U: FIRST PAIRED BENCHMARK REPORT

**Status**: One-Repeat CLI Implemented, Offline Batch Validated, Live Batch Scheduled Post-Reset  
**Date**: October 19, 2026  
**Environment**: Windows, Python 3.12, SQLite `mas.db`, Governed HTTP Client (45 attempts/day ceiling)

---

## 1. Batch-Size Correction & CLI Implementation

To prevent catastrophic ceiling breach caused by multi-repeat batch forecasts (53+ attempts), [eval/runner.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/eval/runner.py) was enhanced to support granular, single-repeat execution:

```bash
python eval/runner.py --task-id srdd_educ_01 --repeats 1 --systems mas,chatdev
```

### Enhancements Implemented in `eval/runner.py`:
1. **Targeted Task Filtering (`--task-id`)**:
   - Filters the locked 20-task dataset from [eval/tasks.json](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/eval/tasks.json) to exactly the specified task (e.g. `srdd_educ_01`).
   - Validates that the requested task ID exists in the authoritative canonical specification.
2. **Selective Multi-Agent Execution (`--systems`)**:
   - Accepts comma-separated systems (e.g. `mas,chatdev`, `mas`, or `chatdev`).
3. **Explicit Repeat Numbering (`--repeats`, `--repeat-no`)**:
   - Allows fine-grained control over repeat indices (`r1`, `r2`, `r3`) so batches across UTC days accumulate under unique, non-colliding run IDs without overwriting historical runs.
4. **Resumable Persistent Manifest (`eval/benchmark_manifest.json`)**:
   - Maintains an append-and-update JSON ledger tracking `task_id`, `repeat_no`, `system`, `run_id`, `model`, `status`, token telemetry, cost, quality components, and explicit counterpart pairing status (`paired_counterpart_run_id`, `is_paired_complete`).
5. **Pre-Execution Governor Guard**:
   - Live runs (`--model cohere/north-mini-code:free`) inspect the internal transmission ledger prior to wire transmission; if the remaining daily allowance is below the safety threshold (25 attempts for a paired MAS+ChatDev batch), execution stops safely without dispatching network calls.

---

## 2. Offline Batch Validation Results

Controlled execution was verified offline using simulated models (`--model fake`):

```bash
python eval/runner.py --task-id srdd_educ_01 --repeats 1 --systems mas,chatdev
```

- **Task**: `srdd_educ_01` ("Science Question Solver")
- **Exit Code**: `0`
- **Network Calls**: `0` (ledger remains unchanged at 25 consumed / 20 remaining)
- **Regression Suite**: `150 passed, 0 failed` in 18.18s

### Measured Batch Telemetry (Recorded in `eval/benchmark_manifest.json`):

| Framework | Run ID | Status | Tokens (Prompt/Compl/Total) | Cost (USD) | Completeness | Executability | Consistency | Quality ($Q$) | Paired Counterpart | Paired Complete |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **MAS** | `mas_srdd_educ_01_r1` | `COMPLETED` | 1,420 / 206 / 1,626 | $0.00 | 1.000 | 1.000 | 0.000 | 0.0000 | `cd_srdd_educ_01_r1` | `True` |
| **ChatDev** | `cd_srdd_educ_01_r1` | `COMPLETED` | 2,100 / 900 / 3,000 | $0.015 | 1.000 | 1.000 | 0.4286 | 0.4286 | `mas_srdd_educ_01_r1` | `True` |

> [!NOTE]
> In accordance with scientific integrity guidelines, this single-repeat batch is a mechanical verification run. No comparative superiority or inferiority claim can be drawn from a single repeat ($N=1$, paired permutation test $p=1.000$).

---

## 3. Budget Analysis & Governor Gating for Live Run

### Current Daily Transmission Ledger State (`2026-10-19`):
- **Total Transmissions Consumed Today**: **25 attempts**
  - Metadata queries: 2
  - Live model generation calls: 23 (Task B initial: 6, Task B relaunch: 6, Task C: 8, Task D: 3)
- **Internal Daily Ceiling**: **45 attempts**
- **Remaining Daily Allowance**: **20 attempts**

### Live Paired Workload Forecast for Task 1 (`srdd_educ_01`):
1. **Metadata Preflight**: 1 HTTP request (`GET /api/v1/key`).
2. **MAS Generation**:
   - `srdd_educ_01` routes deterministically to `SIMPLE` (Router score = 0).
   - Pipeline: Manager (1) + Developer (1) + Tester (1) + Reviewer (1) = **4–6 generation requests**.
3. **ChatDev Generation**:
   - Pinned ChatDev execution involves multi-stage roleplay: DemandAnalysis $\rightarrow$ LanguageChoose $\rightarrow$ Coding $\rightarrow$ CodeCompleteAll $\rightarrow$ CodeReview $\rightarrow$ Test.
   - Forecast: **15–25 generation requests**.
4. **Total Forecast Workload**: **20–32 outbound HTTP attempts**.

### Safety Assessment & Decision:
Starting live execution with only **20 attempts remaining** provides **zero safety margin** and carries a near-certain probability of hitting the 45-attempt ceiling during ChatDev's multi-turn dialogue, which would halt execution with an incomplete, unpaired repeat.

**Action Taken**:
Live API dispatch is safely held until the UTC daily reset (`2026-10-20 00:00:00 UTC`), when the daily budget resets to 45 fresh attempts.

---

## 4. Experimental Parity & Statistical Protocol Alignment

1. **Dataset Integrity**:
   - [eval/tasks.json](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/eval/tasks.json) is unmodified (SHA-256: `5ea3c4cb04848e9f009f596b3d059fc6e67b96e00675f7e796eaab5486afec55`).
   - Both frameworks receive identical canonical prompts.
2. **Statistical Protocol (DEC-014)**:
   - Primary hypothesis testing uses the **two-sided paired permutation test** ($\alpha = 0.05$, 10,000 trials) on task-level paired means across 3 repeats, as implemented in [eval/stats.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/eval/stats.py).
   - Independent-samples Mann-Whitney U test is strictly avoided for paired benchmark outputs.
3. **Literature Baseline Distinction**:
   - iCoder metrics ($Q = 0.7924$, 104,883 tokens) are maintained as a published reference baseline from You et al. (*Information and Software Technology*, 2026) in [eval/published_references.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/eval/published_references.py), strictly distinguished from local live execution.
4. **Historical Pilot Preservation**:
   - All four development pilots (Tasks A, B, C, D) remain preserved in database `mas.db` with status `COMPLETED_QUALITY_GATE` (39/39 assertions passed).

---

## 5. Next Executable Action

Immediately following the `2026-10-20 00:00:00 UTC` reset boundary, launch the first live paired benchmark batch:

```bash
python eval/runner.py --task-id srdd_educ_01 --repeats 1 --repeat-no 1 --systems mas,chatdev --model cohere/north-mini-code:free
```
