# Phase 2AG — Immediate API Key Switch & Live Benchmark Execution Report

**Workspace:** `C:\Users\The Mighty King\Desktop\Final Year Project`  
**Date (UTC):** `2026-10-23`  
**Model Condition:** `cohere/north-mini-code:free` (Strict identity verified, fallbacks disabled, authorized spend: $0.00)  
**Evaluator Version:** `v1.3` (Level 1 smoke test + Level 2 frozen tests `fb3843c4...`)  
**Test Suite Status:** **201 / 201 passed (100%)** in 24.66s  

---

## 1. Executive Summary

1. **Secure API Key Switch & Preflight Check:**
   - The user's new OpenRouter API key configured in `.env` was securely loaded via `python-dotenv` without logging, printing, committing, or exposing secrets.
   - Upstream preflight authentication to `GET https://openrouter.ai/api/v1/key` succeeded with HTTP `200 OK`.
   - Initial upstream quota reported: `50` free requests available (`limit: 50, used: 0, remaining: 50`).
   - Local transmission ledger showed 16 accountable attempts (14 prior calls + 2 metadata queries) out of the hard internal 45 daily cap, leaving **29 internal transmissions available**.

2. **Benchmark Execution Decision:**
   - The conservative threshold for a single-task paired run (`srdd_educ_01`, Repeat 1) was calculated at 22 transmissions.
   - Since $29 \ge 22$ internal attempts and $50 \ge 22$ upstream quota, all safety gates passed to execute immediately.

3. **Live Benchmark Execution Results (`srdd_educ_01`, Repeat 1):**
   - Runner command executed:
     ```powershell
     python -m eval.runner --task srdd_educ_01 --repeats 1 --system all --model cohere/north-mini-code:free --live
     ```
   - **MAS Attempt 4 (`mas_srdd_educ_01_r1_attempt4`):**
     - **Status:** **`COMPLETED`** (Successfully completed the full multi-agent cycle).
     - **Token Usage:** **57,053 tokens** (Strictly within the 60,000-token per-run ceiling; no budget-ceiling abort).
     - **Cost:** **$0.00** (Zero authorized spend maintained).
     - **Generated Code:** Valid `main.py` (6,980 bytes, 170 lines) implementing complete science question solving logic across Biology (photosynthesis), Chemistry (carbon/atomic number), Physics (velocity/speed), and generic scientific reasoning with structured JSON output and `--help` CLI support.
     - **Neutral Evaluation:** Completeness = 1.0, Executability = 1.0, Shared Test = 1.0 (100% pass on frozen Level 1 & Level 2 test suites), Ruff = 0 violations, Bandit = 0 high vulnerabilities, Radon MI = 100.0, Composite Quality = 0.3636.
   - **ChatDev Attempt 3 (`cd_srdd_educ_01_r1_attempt3`):**
     - **Status:** **`FAILED`**
     - **Token Usage:** 3,251 tokens, Cost: $0.00.
     - **Root Cause of Failure:** Windows Console Encoding Crash (`UnicodeEncodeError`). ChatDev's console logging (`log_and_print_online` in `external/ChatDev/chatdev/utils.py:22`) crashed under the default Windows `cp1252` encoding when the Cohere model generated a Unicode non-breaking hyphen (`\u2011`) in position 1264 (`charmap codec can't encode character '\u2011': character maps to <undefined>`).
     - **Permanent Fix Applied:** Added `PYTHONIOENCODING="utf-8"` and `PYTHONUTF8="1"` to `eval/chatdev_adapter.py` and `mas/analysis/sandbox.py` to prevent Windows console charmap encoding crashes.

4. **Resource Governance & Cap Status:**
   - Total outbound transmissions recorded today: **35 / 45**.
   - Remaining internal transmission allowance: **10 transmissions**.
   - Completed paired repeats in manifest: **0** (MAS completed 1, ChatDev completed 0; pairing requires both systems to complete).
   - Because 10 remaining transmissions is below the single-pair launch threshold (22 calls), further live generation is **safely stopped** until the daily UTC reset (00:00:00 UTC) to prevent ceiling breaches.

---

## 2. Resource & Quota Accounting

| Metric | Upstream (OpenRouter) | Internal Shared Ledger (`eval/outbound_transmission_ledger.json`) |
| :--- | :--- | :--- |
| **Authentication Status** | HTTP 200 OK (`is_free_tier: true`) | Verified |
| **Daily Ceiling** | 50 requests/day | 45 transmissions/day (hard internal cap) |
| **Consumed Today** | 22 requests | 35 transmissions |
| **Remaining Allowance** | 28 requests | **10 transmissions** |
| **Cap Breached** | No | No (`cap_breached: false`) |
| **Active Reservations** | 0 | 0 |

---

## 3. Benchmark Attempts Breakdown (`srdd_educ_01`, Repeat 1)

| Run ID | System | Attempt | Tokens | Cost | Status | Exit / Failure Reason |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `mas_srdd_educ_01_r1` | MAS | 1 | 51,682 | $0.00 | `FAILED` | Legacy unhandled exception |
| `mas_srdd_educ_01_r1_attempt2` | MAS | 2 | 62,871 | $0.00 | `STOPPED_BUDGET_CEILING` | Token overspend (> 60k) |
| `mas_srdd_educ_01_r1_attempt3` | MAS | 3 | 58,690 | $0.00 | `STOPPED_BUDGET_CEILING` | Pre-dispatch reservation block |
| **`mas_srdd_educ_01_r1_attempt4`** | **MAS** | **4** | **57,053** | **$0.00** | **`COMPLETED`** | **Full cycle finished under 60k cap!** |
| `cd_srdd_educ_01_r1` | ChatDev | 1 | 5,228 | $0.00 | `FAILED` | Legacy code block parsing error |
| `cd_srdd_educ_01_r1_attempt2` | ChatDev | 2 | 4,385 | $0.00 | `FAILED` | `ValueError: No Valid Codes.` |
| **`cd_srdd_educ_01_r1_attempt3`** | **ChatDev** | **3** | **3,251** | **$0.00** | **`FAILED`** | **Windows `cp1252` `UnicodeEncodeError (\u2011)`** |

---

## 4. Evaluation of Generated MAS Artifact (`mas_srdd_educ_01_r1_attempt4`)

### Generated File: `eval/workspaces/mas_srdd_educ_01_r1_attempt4/main.py`
- **File size:** 6,980 bytes (170 lines).
- **CLI Behavior:** Exits cleanly with code 0 on `--help`, outputs clear parameter descriptions.
- **Science Domain Coverage:**
  - **Photosynthesis:** 5-step breakdown (light absorption, photolysis, oxygen release, CO2 Calvin cycle fixation, glucose synthesis).
  - **Chemistry:** Identifies atomic number 6, symbol C, electron configuration $1s^2 2s^2 2p^2$ for carbon.
  - **Physics:** Calculates speed = distance / time given numeric parameters, explains definitions.
  - **Fallback:** 4-step scientific method decomposition.

### Neutral Evaluator (`eval/neutral_evaluator.py`) Metrics
- **Completeness:** `1.0` (Entry points and required structure present)
- **Executability:** `1.0` (Smoke run succeeds with clean exit code 0)
- **Shared Test Harness:** `1.0` (100% pass on frozen Level 1 & Level 2 tests)
- **Ruff Violations:** `0`
- **Bandit High Vulnerabilities:** `0`
- **Radon Maintainability Index:** `100.0`
- **Consistency Score:** `0.3636`
- **Composite Quality:** `0.3636`

---

## 5. Completed Paired Observations & Scientific Integrity

- **Completed Paired Repeats:** **0 / 60** (MAS live completed: 1; ChatDev live completed: 0).
- **Preservation of Evidence:** All historical attempts (`attempt1`, `attempt2`, `attempt3`, `attempt4`) are intact and logged in `mas.db`, `eval/benchmark_manifest.json`, and `results.csv`.
- **Statistical Claim Policy:** Because ChatDev failed in this paired run, **no empirical superiority claim of MAS over ChatDev is made**. Scientific validity requires paired observations across identical seeds/tasks before statistical tests (Wilcoxon signed-rank / Mann-Whitney U) can be computed.

---

## 6. Next Steps & Earliest Safe Execution

1. **Bug Fix Applied & Verified:**
   - Added UTF-8 environment settings (`PYTHONIOENCODING="utf-8"`, `PYTHONUTF8="1"`) to `eval/chatdev_adapter.py` and `mas/analysis/sandbox.py`.
   - Regression suite re-verified: **201/201 passed**.
2. **Current Ledger State:**
   - Outbound transmissions consumed today: **35 / 45**.
   - Remaining internal allowance: **10 transmissions** (below the 22-transmission launch threshold for a pair).
3. **Earliest Safe Execution:**
   - **Schedule:** Immediately following the UTC calendar reset at `00:00:00 UTC` (which occurs in ~13 hours 33 minutes from current local time).
   - At reset, the daily ledger resets to 0 / 45 transmissions, allowing ChatDev and MAS to execute the remaining repeats cleanly with full quota.
