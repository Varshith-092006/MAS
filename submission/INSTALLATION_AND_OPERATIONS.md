# MAS: Installation, Configuration & Operations Guide
## Final Year Project Submission — Deployment & Run Manual

---

## 1. Prerequisites

- **Operating System:** Windows 10/11, Ubuntu 22.04+, or macOS 13+
- **Python:** Python 3.11.x (verified on Python 3.11.0)
- **Node.js:** Node 18.x or 20.x (with npm 9+)
- **Docker (Optional):** Docker Desktop with Docker Compose (for sandboxed containerized code execution and full-stack deployment)

---

## 2. Local Environment Setup

### 2.1 Python Environment & Editable Package
```bash
# Clone and enter workspace directory
cd "Final Year Project"

# Create and activate virtual environment (optional but recommended)
python -m venv venv
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux/macOS:
source venv/bin/activate

# Install editable package and dependencies
pip install -e .
```

### 2.2 Environment Configuration (`.env`)
Create a `.env` file in the project root based on `.env.example`:
```bash
cp .env.example .env
```
Ensure the following variables are configured in `.env`:
```ini
# OpenRouter API Configuration
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=cohere/north-mini-code:free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Strict Research Governance Settings
MAS_STAGE_MAX_SPEND=0.00
MAX_DAILY_HTTP_TRANSMISSIONS=45
MAX_CALLS_PER_RUN=15
OPENROUTER_REASONING_MAX_TOKENS=0

# Local Proxy Configuration
OPENAI_BASE_URL=http://127.0.0.1:8000/proxy/v1
MAS_ALLOW_SUBPROCESS_SANDBOX=1
```
> **Security Notice:** `.env` is explicitly excluded from version control in `.gitignore`. Never commit API keys or paste them into public channels.

---

## 3. Application Startup Sequence

The MAS platform consists of a FastAPI backend (with integrated logging proxy and SQLite database) and a modern React/Vite dashboard.

### 3.1 Starting the Backend API & Logging Proxy
From the project root:
```bash
python -m uvicorn mas.api.main:app --host 127.0.0.1 --port 8000 --reload
```
- **API Base URL:** `http://127.0.0.1:8000`
- **Swagger Documentation:** `http://127.0.0.1:8000/docs`
- **Health Check:** `http://127.0.0.1:8000/health`
- **Logging Proxy Endpoint:** `http://127.0.0.1:8000/proxy/v1`

### 3.2 Starting the React Frontend Visualizer
From the `frontend/` directory:
```bash
cd frontend
npm install
npm run dev
```
- **Web Dashboard:** `http://localhost:5173` (or `http://localhost:3000` under Docker)
- The visualizer displays real-time agent execution traces, token consumption curves against the 60,000 ceiling, and neutral evaluator metric scorecards.

### 3.3 Running via Docker Compose (Optional)
To launch the complete isolated containerized stack:
```bash
docker compose up -d
```
Services initialized:
- `mas_api`: FastAPI backend and logging proxy on port `8000`
- `mas_db`: PostgreSQL database on port `5432`
- `mas_frontend`: React UI dashboard on port `3000`

---

## 4. CLI Execution Workflows

### 4.1 Running Tasks Locally via CLI
```bash
# 1. Simple task (deterministic fake model, zero cost)
mas run --model fake --task "Write a python calculator that adds two integers"

# 2. Structured task (triggers Architect agent for UML and user stories)
mas run --model fake --task "Build a multi-user inventory system with a SQLite database, user login authentication, admin and staff roles, REST API endpoints, analytics metrics reporting, and an approval workflow lifecycle."

# 3. View run audit telemetry and recorded metrics
mas status <RUN_ID>
mas logs <RUN_ID>
mas results <RUN_ID>
```

### 4.2 Benchmark Execution CLI
```bash
# 1. Dry run: prints benchmark task matrix with 0 model calls
python -m eval.runner --dry-run

# 2. Execute paired benchmark (1 repeat, both MAS and ChatDev)
python -m eval.runner --task srdd_educ_01 --repeats 1 --system all --model cohere/north-mini-code:free --live
```
