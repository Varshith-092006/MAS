# MAS Final Year Project — Submission Package
## Multi-Agent Software Engineering Team with Cost-Aware Routing & Governed Execution

Welcome to the official submission bundle for the **MAS** final-year computer science project. This directory contains complete architectural, engineering, operational, and empirical documentation for evaluation, demonstration, and grading.

---

## 1. Submission Package Navigation

| Document | Description |
| :--- | :--- |
| **[`PROJECT_OVERVIEW.md`](./PROJECT_OVERVIEW.md)** | Executive summary, research problem statement, novel contributions, and repository deliverables. |
| **[`SYSTEM_ARCHITECTURE.md`](./SYSTEM_ARCHITECTURE.md)** | System architecture diagram (Mermaid), complexity routing heuristics, AST cycle detection, context slicing, and sandbox isolation. |
| **[`AGENT_RESPONSIBILITIES.md`](./AGENT_RESPONSIBILITIES.md)** | Agent roles (Manager, Architect, Developer, Reviewer, Tester, Reflection), Pydantic schema contracts, and evidence-grounded review. |
| **[`INSTALLATION_AND_OPERATIONS.md`](./INSTALLATION_AND_OPERATIONS.md)** | Step-by-step setup guide for Python 3.11, Docker, environment configuration (`.env`), API startup, frontend visualizer, and CLI commands. |
| **[`TESTING_AND_VERIFICATION.md`](./TESTING_AND_VERIFICATION.md)** | Quality assurance methodology, test taxonomy, actual 201/201 regression suite results (100% pass rate, 0 failures, 0 warnings). |
| **[`BENCHMARK_METHODOLOGY_AND_RESULTS.md`](./BENCHMARK_METHODOLOGY_AND_RESULTS.md)** | Canonical SRDD-20 task dataset (SHA-256 verified), neutral evaluation metrics, resource governance bounds, and full historical audit trail. |
| **[`FINAL_PROJECT_REPORT.md`](./FINAL_PROJECT_REPORT.md)** | Complete academic final-year project dissertation and technical research report. |

---

## 2. Quick Verification Commands

To independently verify the project in less than 60 seconds:

### Step 1: Run Full Offline Regression Suite (201 Tests)
```bash
python -m pytest tests -v
```
*Expected Result:* `201 passed in ~26s` with 0 failures and 0 warnings.

### Step 2: Verify Task Dataset Integrity (SHA-256)
```bash
python -c "import hashlib; h = hashlib.sha256(open('eval/tasks.json', 'rb').read()).hexdigest(); assert h == '5ea3c4cb04848e9f009f596b3d059fc6e67b96e00675f7e796eaab5486afec55', f'Mismatch: {h}'; print('tasks.json SHA-256 Verified OK:', h)"
```

### Step 3: Verify Backend API & Proxy Health
```bash
python scratch/test_api_startup.py
```
*Expected Result:*
- `API Health Status: 200 {'status': 'ok', 'service': 'mas-api', 'version': '0.1.0'}`
- `Proxy Health Status: 200 {'status': 'ok'}`
- `SRDD Tasks Status: 200 items: 20`

### Step 4: Run a Local Software Generation Task (Zero Cost, Fake Provider)
```bash
mas run --model fake --task "Build a python scientific calculator that computes velocity from distance and time"
```

---

## 3. Project Summary & Key Invariants

- **Configured Model Condition:** `cohere/north-mini-code:free` (strictly verified exact model match; silent fallbacks disabled).
- **Authorized Stage Spend:** `$0.00` (`MAS_STAGE_MAX_SPEND=0.00`).
- **Per-Run Token Budget:** 60,000 tokens (atomic fail-closed pre-dispatch reservation).
- **Daily Outbound Transmission Cap:** 45 attempts per UTC day (persistent file-locked ledger).
- **Benchmark Observation Status:** 0 completed paired observations to date. All historical runs and failure modes are transparently documented in [`BENCHMARK_METHODOLOGY_AND_RESULTS.md`](./BENCHMARK_METHODOLOGY_AND_RESULTS.md).
