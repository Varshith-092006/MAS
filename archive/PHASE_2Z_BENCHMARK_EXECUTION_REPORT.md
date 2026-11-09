# Phase 2Z — Governed Live Paired Benchmark Execution Report

**Execution Timestamp**: 2026-10-21T14:48:44Z (UTC) / 20:18:44 IST  
**Task Evaluated**: `srdd_educ_01` (Science Question Solver, Education Category)  
**Repeat Number**: Repeat 2  
**Target & Served Model**: `cohere/north-mini-code:free`  
**Governed Transport**: `GovernedHTTPClient` with atomic file-lock reservations on `eval/outbound_transmission_ledger.json.lock`  
**Spend**: $0.00 (Zero-spend enforcement strictly maintained)  

---

## 1. Mandatory Preflight Audit Results

Before dispatching any generation call, all preflight gates were evaluated and verified:

| Dimension | Verification Requirement | Observed State | Gate Status |
| :--- | :--- | :--- | :--- |
| **UTC Calendar Day** | Confirm 00:00:00 UTC rollover has occurred | `2026-10-21T14:34:53Z` upstream response header; UTC date `2026-10-21` | **PASSED** |
| **Upstream Key Allowance** | `GET https://openrouter.ai/api/v1/key` | `50/50` free model daily requests remaining; `usage_daily_usd: 0.0` | **PASSED** |
| **Persistent Transmission Ledger** | Read reservations, active attempts, and cap | 0 attempts prior to preflight; 1 metadata check recorded; 44 remaining | **PASSED** |
| **Model Identity & Policy** | Strict serving identity & zero-cost policy | Model `cohere/north-mini-code:free`; `allow_fallbacks: False`; $0 spend | **PASSED** |
| **Hard 60,000-Token Cap Gate** | Active pre-dispatch & post-call gates | `OpenRouterProvider` and `proxy.py` pre-call check & output truncation | **PASSED** |
| **Regression Test Invariants** | Confirm test suite passing offline | 161/161 baseline tests passed; +1 new budget test added $\rightarrow$ **162/162 passed** | **PASSED** |
| **Canonical Dataset Integrity** | SHA-256 hash of `eval/tasks.json` | `5ea3c4cb04848e9f009f596b3d059fc6e67b96e00675f7e796eaab5486afec55` | **PASSED** |

---

## 2. Transmission Accounting Reconciliation (2026-10-20 Ledger)

The Phase 2Y report noted a total of 25 transmissions on 2026-10-20, but contained a typographic conflict in its narrative breakdown ("10 + 14 + 1"). A forensic event-by-event reconciliation was performed directly against the authoritative ledger in [eval/outbound_transmission_ledger.json](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/eval/outbound_transmission_ledger.json).

### Forensic Breakdown by Event ID and Event Type:

| Event ID | Event Type | State | HTTP Status | Source Identifier | Target / Endpoint |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `att_1792501760_11870e2c` | `KEY_METADATA` | `SUCCEEDED` | 200 | `check_key_metadata` | `/api/v1/key` |
| `att_1792501880_7124cb93` | `LIVE_GENERATION` | `SUCCEEDED` | 200 | `mas_srdd_educ_01_r1:manager` | `cohere/north-mini-code:free` |
| `att_1792501898_bfeac4ee` | `LIVE_GENERATION` | `SUCCEEDED` | 200 | `mas_srdd_educ_01_r1:developer` | `cohere/north-mini-code:free` |
| `att_1792502042_1260c092` | `LIVE_GENERATION` | `SUCCEEDED` | 200 | `mas_srdd_educ_01_r1:tester` | `cohere/north-mini-code:free` |
| `att_1792502052_b2b72dcd` | `LIVE_GENERATION` | `SUCCEEDED` | 200 | `mas_srdd_educ_01_r1:reviewer` | `cohere/north-mini-code:free` |
| `att_1792502152_e682a957` | `LIVE_GENERATION` | `SUCCEEDED` | 200 | `mas_srdd_educ_01_r1:reviewer` | `cohere/north-mini-code:free` |
| `att_1792502210_198174f4` | `LIVE_GENERATION` | `SUCCEEDED` | 200 | `mas_srdd_educ_01_r1:developer` | `cohere/north-mini-code:free` |
| `att_1792502364_d56abd0a` | `LIVE_GENERATION` | `SUCCEEDED` | 200 | `mas_srdd_educ_01_r1:tester` | `cohere/north-mini-code:free` |
| `att_1792502368_853fef4e` | `LIVE_GENERATION` | `SUCCEEDED` | 200 | `mas_srdd_educ_01_r1:reviewer` | `cohere/north-mini-code:free` |
| `att_1792502437_3888be9c` | `LIVE_GENERATION` | `SUCCEEDED` | 200 | `mas_srdd_educ_01_r1:reviewer` | `cohere/north-mini-code:free` |
| `att_1792502472_f1ea9fe3` | `LIVE_GENERATION` | `SUCCEEDED` | 200 | `mas_srdd_educ_01_r1:reviewer` | `cohere/north-mini-code:free` |
| `att_1792505546_1ec39841` | `KEY_METADATA` | `SUCCEEDED` | 200 | `check_key_metadata` | `/api/v1/key` |
| `att_1792505586_8dd81171` | `LIVE_GENERATION` | `SUCCEEDED` | 200 | `mas_srdd_educ_01_r1_attempt2:manager` | `cohere/north-mini-code:free` |
| `att_1792505597_14e8b3ac` | `LIVE_GENERATION` | `SUCCEEDED` | 200 | `mas_srdd_educ_01_r1_attempt2:developer` | `cohere/north-mini-code:free` |
| `att_1792505680_3af4449a` | `LIVE_GENERATION` | `SUCCEEDED` | 200 | `mas_srdd_educ_01_r1_attempt2:developer` | `cohere/north-mini-code:free` |
| `att_1792505806_33fea587` | `LIVE_GENERATION` | `SUCCEEDED` | 200 | `mas_srdd_educ_01_r1_attempt2:tester` | `cohere/north-mini-code:free` |
| `att_1792505817_4bb93b11` | `LIVE_GENERATION` | `SUCCEEDED` | 200 | `mas_srdd_educ_01_r1_attempt2:reviewer` | `cohere/north-mini-code:free` |
| `att_1792505862_3b10c689` | `LIVE_GENERATION` | `SUCCEEDED` | 200 | `mas_srdd_educ_01_r1_attempt2:reviewer` | `cohere/north-mini-code:free` |
| `att_1792505897_e9a2c310` | `LIVE_GENERATION` | `SUCCEEDED` | 200 | `mas_srdd_educ_01_r1_attempt2:reviewer` | `cohere/north-mini-code:free` |
| `att_1792505940_ea78162d` | `LIVE_GENERATION` | `SUCCEEDED` | 200 | `mas_srdd_educ_01_r1_attempt2:developer` | `cohere/north-mini-code:free` |
| `att_1792506032_83044dbc` | `LIVE_GENERATION` | `SUCCEEDED` | 200 | `mas_srdd_educ_01_r1_attempt2:tester` | `cohere/north-mini-code:free` |
| `att_1792506078_cf621e0d` | `LIVE_GENERATION` | `SUCCEEDED` | 200 | `mas_srdd_educ_01_r1_attempt2:reviewer` | `cohere/north-mini-code:free` |
| `att_1792506155_52d86b3c` | `LIVE_GENERATION` | `SUCCEEDED` | 200 | `cd_srdd_educ_01_r1:chatdev` | `cohere/north-mini-code:free` |
| `att_1792506175_b6419ccb` | `LIVE_GENERATION` | `SUCCEEDED` | 200 | `cd_srdd_educ_01_r1:chatdev` | `cohere/north-mini-code:free` |
| `att_1792506193_3890fd3a` | `LIVE_GENERATION` | `SUCCEEDED` | 200 | `cd_srdd_educ_01_r1:chatdev` | `cohere/north-mini-code:free` |

### Reconciliation Summary:
- **Total Outbound Transmissions**: Exactly **25** (0 dropped, 0 unfinalized).
- **Generation Requests**: **23** (10 for `mas_srdd_educ_01_r1` + 10 for `mas_srdd_educ_01_r1_attempt2` + 3 for `cd_srdd_educ_01_r1`).
- **Metadata Requests**: **2** (preflight checks before each attempt session).
- **Network / Transport Failures**: **0** (all 25 calls returned HTTP 200).
- **Active / Unfinalized Reservations**: **0** (all 25 finalized).
- **Root Cause of Narrative Discrepancy**: The narrative string "10 + 14 + 1" arose from an author grouping error that lumped the 10 attempt-2 generation calls + 3 ChatDev calls + 1 metadata check into an aggregate "14", adding the initial 10 generation calls and 1st metadata check. The raw ledger JSON is completely immutable and accurate.

---

## 3. Pre-Call Budget Gate & Token-Cap Enforcement

### Controls Implemented:
1. **Pre-Dispatch Token Check**:
   - In [mas/core/llm.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/mas/core/llm.py) (`OpenRouterProvider.generate`) and [mas/core/proxy.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/mas/core/proxy.py), if `cumulative_tokens >= 60,000`, generation is blocked immediately before transport, raising `TokenCapExceededError` or returning HTTP 429 (`TOKEN_CAP_EXCEEDED`).
2. **Output Token Constraining**:
   - Before submitting payloads, the maximum requested output tokens are constrained to the remaining run budget:
     `effective_max_tokens = min(max_tokens, max(1, 60000 - current_tokens))`
3. **Limitation & Fail-Safe Disclosure**:
   - Provider token accounting charges for `total_tokens = prompt_tokens + completion_tokens`.
   - While output tokens can be clamped, prompt tokens are dictated by accumulated conversation history and cannot be strictly known prior to upstream tokenization.
   - If prompt tokens cause the call to exceed 60,000 upon response receipt, `TokenLogger.record_call` halts the run immediately with `TokenCapExceededError`, marks the run as `STOPPED_BUDGET_CEILING`, and disqualifies it from paired completion.

---

## 4. Live Paired Benchmark Execution (`srdd_educ_01`, Repeat 2)

Execution was launched with:
```bash
python eval/runner.py --task-id srdd_educ_01 --repeats 1 --repeat-no 2 --systems mas,chatdev --model cohere/north-mini-code:free
```

### Execution Telemetry Summary:

| System | Run ID | Mode | Status | Calls | Input Tokens | Output Tokens | Total Tokens | Spend |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **MAS** | `mas_srdd_educ_01_r2` | `STOPPED_BUDGET_CEILING` | `STOPPED_BUDGET_CEILING` | 12 | 11,854 | 50,324 | **62,178** | $0.00 |
| **ChatDev** | `cd_srdd_educ_01_r2` | `LIVE_API` | `COMPLETED` | 2 | 2,490 | 1,800 | **4,290** | $0.00 |

### Day-Level HTTP Transmission Accounting (2026-10-21):
- **Preflight Key Metadata**: 1 query
- **MAS Generation Calls**: 12 calls
- **ChatDev Generation Calls**: 2 calls
- **Total Transmissions Consumed Today**: **15 / 45** (30 remaining)
- **Daily Cap Breached**: **NO** (0 excess transmissions)

---

## 5. Neutral Evaluator Verification and Artifact Inspection

### 5.1 Multi-Agent System (`mas_srdd_educ_01_r2`)
- **Tokens**: 62,178 (Breached hard 60,000 ceiling by 2,178 tokens during the final Reviewer call on iteration 3).
- **Execution Mode & Status**: Both set strictly to `STOPPED_BUDGET_CEILING`.
- **Level 2 Neutral Evaluation**:
  - `completeness`: 1.0 (requirements covered)
  - `executability`: 0.0 (`main.py` raised an unhandled runtime error during automated test execution)
  - `consistency`: 0.5714
  - `shared_test`: 0.0
  - `quality`: **0.0000**
  - `bandit`: 0, `ruff`: 0, `radon_mi`: 100.0

### 5.2 ChatDev (`cd_srdd_educ_01_r2`)
- **Tokens**: 4,290 (Within 60,000 ceiling).
- **Execution Mode & Status**: `LIVE_API`, `COMPLETED`.
- **Level 2 Neutral Evaluation**:
  - `completeness`: 0.0 (no runnable source generated)
  - `executability`: 0.0
  - `quality`: **0.0000** / `null`
  - `bandit`: 0, `ruff`: 0, `radon_mi`: 100.0
- **Defect Analysis**: During step 2 of ChatDev's internal chain, ChatDev crashed with exit code 1 (`chat_chain.py` line 164), leaving configuration JSON files in its workspace without generating `main.py`.

---

## 6. Manifest Status and Completed-Pair Accounting

Per benchmark rules in [eval/benchmark_manifest.json](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/eval/benchmark_manifest.json):
- A repeat qualifies as a **completed paired repeat** if and only if **both** MAS and ChatDev achieve `status in ("COMPLETED", "COMPLETED_QUALITY_GATE")`, `execution_mode == "LIVE_API"`, and `tokens <= 60,000`.

### Status of Repeat 2:
- **MAS**: Ineligible (status `STOPPED_BUDGET_CEILING`, 62,178 tokens > 60,000).
- **ChatDev**: Ineligible for pairing (counterpart over budget, and produced no code artifact).
- **Repeat 2 Paired Status**: **UNPAIRED / INCOMPLETE** (`is_paired_complete: false`).

### Benchmark Progress Counter:
```json
"summary": {
  "total_canonical_tasks": 20,
  "required_repeats": 3,
  "completed_paired_repeats": 0,
  "mas_completed_live_runs": 0,
  "chatdev_completed_live_runs": 2,
  "simulation_runs_excluded": 2
}
```
All historical evidence (`mas_srdd_educ_01_r1` FAILED, `mas_srdd_educ_01_r1_attempt2` STOPPED_BUDGET_CEILING, `cd_srdd_educ_01_r1` COMPLETED, `sim_*` SIMULATION_ONLY) remains completely preserved without retroactive modifications.

---

## 7. Next Concrete Execution Command

Today's remaining internal transmission budget stands at **30 attempts** (15 used out of 45).

To execute Repeat 3 of canonical task `srdd_educ_01` under governed live conditions:

```bash
python eval/runner.py --task-id srdd_educ_01 --repeats 1 --repeat-no 3 --systems mas,chatdev --model cohere/north-mini-code:free
```
