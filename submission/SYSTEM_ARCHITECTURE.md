# MAS: System Architecture & Workflow Specification
## Final Year Project Submission — Technical Architecture

---

## 1. High-Level Architectural Diagram

```mermaid
flowchart TD
    User([User Specification]) --> Manager[Manager Agent]
    Manager --> Router{Deterministic Complexity Router\n(0 LLM Calls)}

    Router -->|Score 0–3: SIMPLE| Developer[Developer Agent]
    Router -->|Score 4+: STRUCTURED| Architect[Architect Agent]
    
    Architect -->|Architecture & Minimal UML| Developer
    
    Developer -->|Generate CodePatch| PatchValidator{Pydantic Schema\nValidation}
    PatchValidator -->|Malformed Schema| RetryGate[Bounded Retry & Rollback]
    RetryGate --> Developer
    
    PatchValidator -->|Valid CodePatch| Workspace[Write to Workspace Dir]
    Workspace --> AST[Deterministic AST Dependency Analyzer]
    
    AST -->|Syntax Error / Cycle Detected| LintReport[Quality & AST Diagnostics]
    AST -->|Clean Structure| Sandbox[Sandbox Smoke Runner]
    
    Sandbox --> Tester[Tester Agent\n(Internal Pytest Scope)]
    Tester --> Reviewer[Reviewer Agent\n(Semantic Review)]
    
    Reviewer --> Stopper{Adaptive Reflection Stopper}
    
    Stopper -->|Marginal Gain >= Threshold\n& Issues Exist| Slicer[Context Slicer\nTransitive Impact Set]
    Slicer --> Developer
    
    Stopper -->|Clean / Ceiling Reached| NeutralEval[Hidden Neutral Evaluator\nIndependent Battery]
    
    NeutralEval --> FinalReport([Run Finalization & Persistence])
```

---

## 2. Core Subsystems

### 2.1 Deterministic Complexity Router (`mas/agents/router.py`)
- **Execution Cost:** 0 LLM calls (100% deterministic regex and surface heuristic evaluation).
- **Inputs:** Raw natural language requirement string.
- **Scoring Heuristics:**
  - *Word count threshold:* requirements $> 50$ words increment score (+1).
  - *Multi-module indicators:* terms such as `database`, `api`, `auth`, `service`, `rest`, `frontend`, `backend`, `model`, `schema` increment score (+1 per domain).
  - *Architectural conjunctions and structural separators:* `;`, `and then`, `lifecycle`, `workflow` increment score (+1).
- **Routing Decision:**
  - $\text{Score} < 4 \implies \textbf{SIMPLE}$: Bypasses Architect; Developer generates standard single/dual-file implementation.
  - $\text{Score} \ge 4 \implies \textbf{STRUCTURED}$: Invokes Architect for component decomposition, dependency mapping, and user story specifications.

### 2.2 AST Dependency & Impact Analyzer (`mas/analysis/ast_analyzer.py`)
- **Syntax Parsing:** Evaluates Python Abstract Syntax Trees for all generated `.py` files.
- **Graph Construction:** Builds a directed module dependency graph $G = (V, E)$ from import statements (`import foo`, `from bar import baz`).
- **Cycle Detection:** Runs Depth-First Search (DFS) with three-color marking (`WHITE`, `GRAY`, `BLACK`) to detect circular import cycles ($A \to B \to C \to A$).
- **Transitive Impact Set:** When file $f$ is modified, computes the reverse reachability closure:
  
  $$\text{Impact}(f) = \{ v \in V \mid \exists \text{ path from } v \text{ to } f \text{ in } G \}$$

### 2.3 Context Slicer (`mas/core/context_slicer.py`)
- Traditional multi-agent systems resend the full history across each review round.
- MAS filters the Developer context in iteration $t > 1$:
  1. Primary requirement and acceptance criteria.
  2. Findings reported by Reviewer and Tester from iteration $t-1$.
  3. Only the files belonging to $\text{ModifiedFiles} \cup \text{Impact}(\text{ModifiedFiles})$.
- Reduces token footprint by $40\%\text{--}65\%$ on iterative bug fixing rounds.

### 2.4 Adaptive Reflection Stopper (`mas/agents/reflection.py`)
- At the end of each iteration, evaluates code quality delta $\Delta Q = Q_t - Q_{t-1}$.
- **Stopping Conditions:**
  - $\text{Status} == \text{PASSED}$ (zero critical and zero major issues).
  - Marginal gain $\Delta Q < 0.05$ (diminishing returns prevention).
  - Hard limit of 3 iterations reached.
  - Per-run token ceiling breached or threatened ($< 50$ completion tokens available).

### 2.5 Disposable Sandbox Execution (`mas/analysis/sandbox.py`)
- **Docker Isolation (Primary):**
  - Container flags: `--network none --cpus 1.0 --memory 512m --pids-limit 64 --read-only`.
  - Mounted `/workspace` volume with disposable lifecycle (`--rm`).
  - Timeout: 45 seconds strict timeout.
- **Subprocess Isolation (Fallback for CI / Non-Docker Environments):**
  - Cleaned environment (scrubbed API secrets).
  - Dedicated working directory and `PYTHONPATH` isolation.

### 2.6 OpenRouter Logging Proxy (`mas/core/proxy.py`)
- Standard OpenAI-compatible HTTP proxy running on FastAPI.
- Intercepts requests from both MAS and external ChatDev subprocesses:
  - Enforces `"provider": {"allow_fallbacks": false}` to prevent model substitution.
  - Suppresses reasoning tokens for free/code models (`"reasoning": {"max_tokens": 0}`).
  - Clamps output token requests to available per-run budget ceiling.
  - Records exact provider-reported token usage (`prompt_tokens`, `completion_tokens`, `total_tokens`) into `ModelCall` SQLite table.
  - Checks actual returning model against strict canonical model allowlist (`is_model_match`).
