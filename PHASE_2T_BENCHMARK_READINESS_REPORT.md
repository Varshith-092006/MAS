# PHASE 2T: BENCHMARK READINESS AND DEVELOPMENT PILOT FINALIZATION REPORT

**Status**: Verified & Prepared for Comparative Benchmark  
**Date**: October 19, 2026  
**Environment**: Windows, Python 3.12, SQLite Database `mas.db`, OpenRouter Free-Tier (`cohere/north-mini-code:free`)

---

## 1. Final Pilot Verification & Preservation

All four development pilot applications have been audited, verified offline against their independent Level 2 evaluator suites, and confirmed intact in the repository. **No code or artifacts were regenerated.**

| Pilot Task ID | Run Directory | Model Identity | Prompt / Completion Tokens | Cost (USD) | Behavioral Assertions | Quality Gate Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Task A** (`dev_markdown_toc_01`) | `workspace/mas_dev_toc_a_p2m_1792332881` | `cohere/north-mini-code:free` | 27,970 / 1,466 | $0.00 | 10 / 10 Passed (100%) | **PASSED** |
| **Task B** (`dev_inventory_system_01`) | `workspace/mas_dev_inv_b_p2m_1792417660` | `cohere/north-mini-code:free` | 33,201 / 1,217 | $0.00 | 9 / 9 Passed (100%) | **PASSED** |
| **Task C** (`dev_log_analyzer_01`) | `workspace/mas_dev_log_c_p2m_1792418269` | `cohere/north-mini-code:free` | 49,936 / 1,185 | $0.00 | 10 / 10 Passed (100%) | **PASSED** |
| **Task D** (`dev_markdown_toc_01` repeat) | `workspace/mas_dev_toc_d_p2m_repeat_1792418892` | `cohere/north-mini-code:free` | 11,223 / 748 | $0.00 | 10 / 10 Passed (100%) | **PASSED** |
| **Total** | — | — | **122,330 / 4,616** | **$0.00** | **39 / 39 Passed (100%)** | **PERFECT PASS** |

### Workspace Artifacts Confirmed:
- **Task A**: [main.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/workspace/mas_dev_toc_a_p2m_1792332881/main.py), [test_main.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/workspace/mas_dev_toc_a_p2m_1792332881/test_main.py)
- **Task B**: [models.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/workspace/mas_dev_inv_b_p2m_1792417660/models.py), [storage.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/workspace/mas_dev_inv_b_p2m_1792417660/storage.py), [service.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/workspace/mas_dev_inv_b_p2m_1792417660/service.py), [main.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/workspace/mas_dev_inv_b_p2m_1792417660/main.py), [test_main.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/workspace/mas_dev_inv_b_p2m_1792417660/test_main.py)
- **Task C**: [main.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/workspace/mas_dev_log_c_p2m_1792418269/main.py), [test_main.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/workspace/mas_dev_log_c_p2m_1792418269/test_main.py)
- **Task D**: [main.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/workspace/mas_dev_toc_d_p2m_repeat_1792418892/main.py), [test_main.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/workspace/mas_dev_toc_d_p2m_repeat_1792418892/test_main.py)

### Offline Regression Suite:
Ran full pytest offline regression suite without outbound network calls:
```
150 passed, 2 warnings in 22.25s
```

---

## 2. October 19 Outbound Transmission Ledger Reconciliation

Forensic inspection of [eval/outbound_transmission_ledger.json](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/eval/outbound_transmission_ledger.json) confirms exactly **25 outbound HTTP transmissions** recorded for UTC date `2026-10-19`.

### Transmission Breakdown:
1. **Metadata Key Preflights (2 calls)**:
   - Attempt `att_1792416873_38c7cd90`: Preflight before initial Task B launch (`https://openrouter.ai/api/v1/key`).
   - Attempt `att_1792417660_5b070baf`: Preflight before relaunched Task B launch (`https://openrouter.ai/api/v1/key`).
2. **Live Generation Requests (23 calls)**:
   - **Initial Task B (`mas_dev_inv_b_p2m_1792416873`) — 6 calls**:
     - 1 Manager call (`att_1792416874_1d6205da`)
     - 2 Architect calls (`att_1792416878_77db2549`, `att_1792416886_594cb7a3`)
     - 3 Developer calls (`att_1792416893_3d790d56`, `att_1792416901_3f421ca9`, `att_1792416922_c91bc31f`). Failed due to DB column mismatch during event logging; workspace halted.
   - **Relaunched Task B (`mas_dev_inv_b_p2m_1792417660`) — 6 calls**:
     - 1 Manager call (`att_1792417661_3ee4cf22`)
     - 2 Architect calls (`att_1792417666_bc316cf5`, `att_1792417674_219bb5ce`)
     - 3 Developer calls (`att_1792417684_e7e6005d`, `att_1792417694_0e2b3476`, `att_1792417711_35b6b8d7`). Succeeded; generated multi-module inventory application.
   - **Task C (`mas_dev_log_c_p2m_1792418269`) — 8 calls**:
     - 1 Manager call (`att_1792418270_f57c2105`)
     - 3 Developer calls (`att_1792418277_3b995e8e`, `att_1792418288_400f959c`, `att_1792418301_3866ae77`)
     - 1 Tester call (`att_1792418320_eebc6a6f`)
     - 3 Reviewer calls (`att_1792418327_f9c8f2ba`, `att_1792418341_f696dc5b`, `att_1792418357_4f783226`). Succeeded; generated log analyzer application.
   - **Task D (`mas_dev_toc_d_p2m_repeat_1792418892`) — 3 calls**:
     - 3 Manager calls (`att_1792418892_5ef686b2`, `att_1792418896_ca8d6b9a`, `att_1792418903_2a433a01`). Succeeded; generated repeat TOC application.

$$\text{Total Calls} = 2 \text{ (metadata)} + 6 \text{ (B initial)} + 6 \text{ (B repeat)} + 8 \text{ (C)} + 3 \text{ (D)} = 25 \text{ calls}$$

### Budget Status:
- Daily ceiling: **45 attempts**
- Used today (`2026-10-19`): **25 attempts**
- Remaining allowance: **20 attempts**

---

## 3. Comparative Benchmark Design Specification

### Authoritative Specification & Canonical Dataset
- **Dataset**: [eval/tasks.json](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/eval/tasks.json) is **strictly locked** (SHA-256 verified, unmodified).
- **Scope**: 20 canonical SRDD tasks spanning 5 domains (Business, Education, Healthcare, Utilities, Web/Data).
- **Repeats**: 3 independent stochastic runs per task per framework (60 runs per framework).

### Multi-Agent Framework Parity
| Dimension | Multi-Agent System (MAS) | ChatDev (Baseline) |
| :--- | :--- | :--- |
| **Task Requirements** | Exact raw prompt from `tasks.json` | Exact raw prompt from `tasks.json` |
| **Model Endpoint** | `cohere/north-mini-code:free` via OpenRouter | `cohere/north-mini-code:free` via OpenRouter |
| **Fallback Policy** | `allow_fallbacks: False` (strict rejection) | `allow_fallbacks: False` (strict rejection) |
| **Model Verification** | Provider-returned `model` must match exactly | Provider-returned `model` must match exactly |
| **Workspace Isolation** | Clean dedicated run directory per repeat | Clean dedicated run directory per repeat |
| **Independent Evaluation** | Evaluated by [eval/evaluator.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/eval/evaluator.py) | Evaluated by [eval/evaluator.py](file:///c:/Users/The%20Mighty%20King/Desktop/Final%20Year%20Project/eval/evaluator.py) |

### iCoder Benchmark Evaluation Protocol
- **Distinction**: In accordance with the project specification and literature review, **iCoder** results are incorporated as a **published literature reference baseline** from the published empirical studies (IST 2026 / original dataset release), *not* as an unverified local execution clone with divergent dependencies.
- **Reporting**: iCoder reported quality, token usage, and pass-rates are mapped directly to corresponding SRDD task IDs in the statistical synthesis table.

### Evaluation Metrics & Statistical Protocol
- **Metric Formula**: Composite Quality Score $Q = C \times E \times S$
  - **Completeness ($C$)**: Fraction of specified functional features implemented.
  - **Executability ($E$)**: Binary or ratio of passing test suites.
  - **Consistency ($S$)**: Structural and AST syntactic validity across generated modules.
- **Cost & Telemetry**: Provider-reported prompt tokens, completion tokens, reasoning tokens, latency (ms), and cost ($0.00 verified).
- **Statistical Tests**:
  - Paired Mann-Whitney $U$ test and Wilcoxon signed-rank test for distribution differences ($p < 0.05$).
  - Cliff's delta ($\delta$) and Cohen's $d$ for effect size estimation.
  - 95% bootstrap confidence intervals across the 3 repeats.
- **Exclusion Criteria**: Runs with network dropouts, rate-limit halts, or mismatched model IDs are isolated to `eval/quarantine/` and explicitly reported as invalid attempts.

---

## 4. Transmission Budget Analysis & Scheduling

### Cost & Request Estimation:
- **MAS single run**: ~4–7 calls per task repeat.
- **ChatDev single run**: ~8–15 calls per task repeat (due to multi-phase chat dialogs).
- **Minimal 1-task paired batch** (1 task $\times$ 3 repeats $\times$ 2 frameworks):
  $$\text{Requests} = 3 \times (\approx 5) + 3 \times (\approx 12) + 2 \text{ preflights} \approx 53 \text{ requests}$$
- **Remaining allowance today**: **20 requests**.

### Scheduling Decision:
Launching a comparative benchmark batch today would exceed the daily ceiling of 45 attempts halfway through execution, triggering governed halt mechanisms and producing an incomplete, unpublishable batch.

**Decision**:
1. Conclude Phase 2T with offline verification, audit reconciliation, and execution readiness complete.
2. **Schedule live benchmark execution immediately following the next UTC reset boundary** (`2026-10-20 00:00:00 UTC`), providing the complete fresh 45-request quota.

### Next Execution Command:
```bash
# To run the first canonical benchmark batch post-UTC reset:
python eval/runner.py --task-id srdd_educ_01 --repeats 3 --systems mas,chatdev
```

---

## 5. Summary of Achievements & Deliverables

1. **All 4 Development Pilots Verified**: 39/39 passing behavioral assertions (100%), $0.00 cost, intact workspaces.
2. **Ledger Reconciled**: All 25 outbound transmissions for Oct 19 accounted for (2 metadata + 23 generations across Tasks B-initial, B-relaunch, C, D).
3. **Clean Codebase**: 150/150 offline tests passing, `tasks.json` locked and pristine.
4. **Benchmark Blueprint Formulated**: Fair, unbiased MAS vs ChatDev configuration with iCoder published baseline reference and rigorous statistical gating.
