# MAS Research Platform — Complete Execution & User Guide

This guide provides step-by-step instructions for running, testing, and interacting with the entire Multi-Agent Software Engineering (MAS) Research Platform, including the FastAPI backend, the React research dashboard, and the generated applications.

---

## Architecture Overview

```
                      ┌────────────────────────────────────────┐
                      │        Browser / User Interface        │
                      └───────────────────┬────────────────────┘
                                          │
            ┌─────────────────────────────┴─────────────────────────────┐
            ▼                                                           ▼
┌───────────────────────────────┐                       ┌───────────────────────────────┐
│     MAS Research Dashboard    │                       │  Generated To-Do Application  │
│     http://localhost:3000     │                       │     http://localhost:5000     │
│   (Vite + React + Tailwind)   │                       │   (Express + SQLite + React)  │
└───────────────┬───────────────┘                       └───────────────────────────────┘
                │ /api & /ws proxy
                ▼
┌───────────────────────────────┐
│       MAS Backend Engine      │
│     http://localhost:8000     │
│  (FastAPI + SQLite + Uvicorn) │
└───────────────┬───────────────┘
                │
                ├─► Multi-Agent Workflow (Manager, Architect, Developer, Reviewer, etc.)
                ├─► Logging Proxy & Token Telemetry (Port 8089)
                ├─► Neutral Evaluator (AST, Completeness, Executability, Consistency)
                └─► OpenRouter / OpenAI AI Provider
```

---

## 1. Prerequisites

- **Python**: Python 3.11 (`python --version`)
- **Node.js**: Node.js v18+ (`node -v`)
- **API Key**: An OpenRouter API key configured in `.env` (or OpenAI key):

```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
MAS_ALLOW_SUBPROCESS_SANDBOX=1
```

> **Note**: `MAS_ALLOW_SUBPROCESS_SANDBOX=1` allows local process execution fallback when Docker Desktop is not running.

---

## 2. Quick Start: Running the Entire Stack

To run the full stack, open **two terminal windows** (PowerShell or Bash) from the project root:

### Terminal 1: Start MAS Backend Engine (Port 8000)

```powershell
# Navigate to the project root
cd "C:\Users\The Mighty King\Desktop\Final Year Project"

# Start the FastAPI engine with hot reload
python -m uvicorn mas.api.main:app --host 127.0.0.1 --port 8000 --reload
```
* Backend API: `http://localhost:8000`
* Interactive API Documentation (Swagger): `http://localhost:8000/docs`

---

### Terminal 2: Start MAS Research Dashboard (Port 3000)

```powershell
# Navigate to the frontend directory
cd "C:\Users\The Mighty King\Desktop\Final Year Project\frontend"

# Launch the Vite development server
npm run dev
```
* Research Dashboard UI: **`http://localhost:3000`**

---

### Terminal 3 (Optional): Run the Generated To-Do List Application (Port 5000)

If you wish to test the previously generated full-stack To-Do List application:

```powershell
cd "C:\Users\The Mighty King\Desktop\Final Year Project\workspace\19fb25e7-76df-425b-b5ab-b5b1385235ee\backend"
$env:PORT = "5000"
node server.js
```
* Working To-Do List App: **`http://localhost:5000`**

---

## 3. Using the MAS Research Dashboard (`http://localhost:3000`)

Open your browser to **`http://localhost:3000`**. The dashboard is organized into clear functional views via the left sidebar:

### A. Dashboard Overview
- **Metric Cards**: Total Runs, Completed Runs, Failed Runs, Total Tokens, Average Tokens/Run, Average Quality, Quality/1K Tokens, Estimated Cost.
- **Quick Actions**: Launch single tasks or access batch benchmark configuration.
- **Recent Runs Table**: Shows the latest multi-agent executions with quick "Inspect" links.

---

### B. Single Task Run
- **Requirement Box**: Enter any software requirement (e.g. *"Create a Python calculator with add and multiply functions"*).
- **System Selector**:
  - `MAS (Proposed)`: Runs the full multi-agent collaborative pipeline (Manager, Router, Architect, Developer, AST Pruning, Reviewer, Reflection).
  - `ChatDev (Baseline)`: Runs the baseline multi-agent chat dialogue arm under identical conditions.
- **Model Selector**:
  - `openai/gpt-4o`: Primary main benchmark model.
  - `openai/gpt-4o-mini`: Cheaper MAS arm and ablation experiments.
  - `openrouter/free`: Free model via OpenRouter.
  - `fake`: Deterministic zero-cost mode for immediate verification.
- **Click [Start Run]**: Automatically creates the execution run, triggers the agents, and redirects to the **Live Run Visualizer** (`/runs/:runId`).

---

### C. Batch Benchmark & Dry Run
- **Input Sources**:
  - Paste task specifications (JSON array).
  - Upload JSON task files.
  - Upload CSV task benchmarks.
- **Configuration**:
  - Task count (e.g., 20 tasks).
  - Repeats / seeds (e.g., 3 repeats).
  - Systems: `MAS` and/or `ChatDev`.
  - Models: `GPT-4o` and/or `GPT-4o-mini`.
- **Pre-Execution Planning**:
  - Displays real-time **Planned Runs** calculation (e.g., `20 tasks × 3 repeats × 2 systems = 120 planned runs`).
  - Displays **ENGINEERING TOKEN ENVELOPE** (engineering budget cap, not measured data).
- **Dry Run Verification**:
  - Click **[Dry Run (0 Model Calls)]** to validate the execution matrix without triggering real LLM calls or incurring costs.
- **Benchmark Confirmation Modal**:
  - Shows explicit confirmation before dispatching benchmark runs. Supports the 300-run research matrix preset.

---

### D. Runs & Results Matrix
- Full searchable, filterable table of all recorded experiments.
- **Filters**: By System (`MAS`, `ChatDev`), Model, Category (`Creation`, `Education`, `Work`, `Life`, `Games`), or Task ID.
- **Columns**: Quality, Completeness, Executability, Consistency, Shared Test pass rate, Ruff health, Bandit security, Radon maintainability, Tokens, Cost, and Duration.
- **Export**: Click **[Export CSV]** to download data for paper generation and R/Python analysis.

---

### E. Analytics & Charts
- **10-Metric Comparative Benchmark**: Side-by-side progress bars comparing MAS vs ChatDev across all 10 evaluated dimensions.
- **Provider Token Telemetry**: Dedicated token analytics breakdown:
  - Input Tokens, Output Tokens, Total Tokens.
  - Average Tokens/Run, Median Tokens/Run, Max Tokens/Run.
  - Cost and Quality/1K Tokens efficiency index.
  - *All counts come strictly from provider-reported usage, never text-length estimates.*

---

### F. Comparisons & Statistical Summary
- **Rigorous Hypothesis Testing**:
  - MAS Mean Quality vs ChatDev Mean Quality.
  - Difference ($\Delta$) and relative percentage gain.
  - **Paired Permutation Test p-value** ($N=10,000$ permutations).
  - **Cohen's d Effect Size**.
  - **95% Confidence Intervals** and distribution standard deviations.
- **MAS GPT-4o-mini Arm**: Shows performance and cost trade-offs of the cheaper model configuration.

---

### G. Published iCoder Reference
- **Explicit Literature Card**: Marked with a prominent **`REFERENCE ONLY`** banner.
- Displays published values cited from the iCoder paper:
  - Published iCoder Quality: `0.792398`
  - Published ChatDev reference: `0.654990`
  - iCoder reported tokens/task: `104,883.2`
  - ChatDev reported tokens/task: `30,416.6`
- Clarifies that iCoder is external literature reference data, not measured locally by MAS.

---

### H. Live Run Visualizer (`/runs/:runId`)
- **Agent Lifecycle Timeline**: Visualizes progress across `Manager → Router → Architect → Developer → AST → Shared Test → Ruff → Bandit → Radon → Reviewer → Reflection`.
- **Live Event Audit Log**: Real-time WebSocket streaming of append-only events.
- **Diagnostics & Metrics Grid**: Complete breakdown of neutral metrics and internal scores.

---

## 4. Running Automated Tests

To run the complete test suite verifying all MAS modules, APIs, and routers:

```powershell
# Run the entire test suite
python -m pytest tests/ -q

# Run API-specific tests
python -m pytest tests/test_api.py -q
```

---

## 5. Troubleshooting & FAQ

| Problem | Cause | Solution |
| :--- | :--- | :--- |
| **Port 8000 already in use** | A previous Uvicorn process is running | Run `Get-Process python \| Stop-Process` in PowerShell or restart terminal. |
| **Port 3000 already in use** | Vite server already running | Stop existing Node processes or specify another port (`npx vite --port 3001`). |
| **Docker daemon not running** | Docker Desktop is closed | Set `MAS_ALLOW_SUBPROCESS_SANDBOX=1` in `.env` for local execution fallback. |
| **Blank screen on localhost:5000** | Browser cached old bundle | Perform a hard refresh in Chrome: **`Ctrl + Shift + R`** or **`Ctrl + F5`**. |
| **API Key Missing** | `.env` file not loaded | Ensure `OPENROUTER_API_KEY` is defined in the root `.env` file. |
