# MAS: Multi-Agent Software Engineering Team
## Final Year Project Submission — Project Overview & Problem Statement

---

## 1. Executive Summary

Modern Large Language Model (LLM)-based multi-agent software development systems (such as ChatDev, MetaGPT, and AgentVerse) demonstrate impressive code generation capabilities. However, existing architectures suffer from fundamental engineering and research limitations:

1. **Catastrophic Token Inflation:** Existing systems repeatedly transmit full multi-turn conversational histories and redundant multi-file source code across every dialogue phase. Standard benchmarks show systems consuming over 100,000 tokens per software task.
2. **One-Size-Fits-All Inflexibility:** Trivial tasks (e.g., adding two numbers or writing a basic utility function) are routed through identical heavyweight planning, architectural modeling, and multi-round chat loops as complex enterprise workflows.
3. **Unchecked Hallucinations & Broken Contracts:** Conversational agents frequently deviate from structural and typing contracts, introduce circular dependencies, produce broken CLI interfaces, or fabricate test results.
4. **Lack of Controlled Experimental Governance:** Prior studies often evaluate multi-agent teams without fail-closed budget caps, without verification of actual serving models, and without independent, neutral evaluation harnesses.

**MAS (Multi-Agent Software Engineering Team)** addresses these challenges through a principled, cost-aware architecture that introduces deterministic complexity routing, AST-driven dependency and cycle analysis, token-efficient context slicing, fail-closed token budget governance, and an isolated, hidden neutral evaluation harness.

---

## 2. Problem Statement

Given a natural language software specification $R$, the objective is to generate an executable, structurally sound, and requirement-aligned software repository $S = \{f_1, f_2, \dots, f_n\}$ such that:

$$\max \text{Quality}(S, R) \quad \text{subject to} \quad \text{TokenUsage}(S) \le B_{\text{max}}$$

where:
- $\text{Quality}(S, R) = \text{Completeness}(S) \times \text{Executability}(S) \times \text{SemanticConsistency}(S, R)$.
- $B_{\text{max}} = 60,000$ tokens per task run (enforced strictly via atomic fail-closed reservations).
- Evaluation must be executed independently of the generating agent team using fixed neutral test assertions.

---

## 3. Key Research & Engineering Contributions

### A. Deterministic Zero-Cost Complexity Routing
- A deterministic router classifies incoming requirements into **SIMPLE** (score 0–3) or **STRUCTURED** (score 4+) using surface heuristics (word count, multi-module indicators, structural patterns) with **zero LLM calls**.
- Simple tasks bypass expensive architectural decomposition (Architect agent) and user-story generation entirely, directly engaging the Developer agent and saving thousands of tokens.

### B. Structural AST Dependency & Impact Analysis
- Replaces conversational code review with deterministic Python AST analysis.
- Detects circular dependency cycles ($A \to B \to C \to A$), unresolved imports, and syntax defects prior to semantic review.
- Computes transitive reverse-dependency impact sets so subsequent repair iterations inspect only affected files.

### C. Token-Efficient Context Slicing
- Rather than appending full conversational history across iterations, MAS slices the Developer prompt to include only the requirement, acceptance criteria, active lint/test findings, and the transitive impact set of modified files.
- Prevents $O(N^2)$ prompt growth across repair cycles.

### D. Multi-Domain Scientific & CLI Quality Safeguards
- Generated applications strictly implement standard CLI `--help` flags and zero-argument clean execution protocols (exit code 0), preventing runtime crashes during headless smoke execution.
- Multi-domain requirements (Physics, Chemistry, Biology) are verified through independent, frozen canonical assertions.

### E. Rigid Token Governance & Outbound Transmission Accounting
- **Atomic Pre-Dispatch Budget Gate:** Atomically reserves estimated prompt tokens plus completion allowance before dispatch. If remaining allowance falls below a safe completion threshold (50 tokens), execution halts fail-closed (`STOPPED_BUDGET_CEILING`), preventing unauthorized token overrun.
- **Provider Quota Governor:** Persistent, file-locked transmission ledger tracking every outbound HTTP request against account rate limits and daily research allowances (45 attempts/day), preventing API blacklisting.
- **Strict Model Verification:** Explicit canonical model allowlisting with verified dated snapshots, disabling silent fallback substitutions.

---

## 4. Repository Structure & Deliverables

```text
Final Year Project/
├── mas/                     # Core MAS framework package
│   ├── agents/              # Specialized agents (Manager, Architect, Developer, Reviewer, Tester)
│   ├── analysis/            # AST analysis, quality tools (Ruff, Bandit, Radon), Docker/subprocess sandbox
│   ├── api/                 # FastAPI REST and WebSocket event streaming endpoints
│   ├── core/                # LLM providers, token logging, proxy, events, state machine, schemas
│   └── db/                  # SQLAlchemy models and SQLite persistence engine
├── eval/                    # Neutral evaluation battery and benchmark runner
│   ├── checks/              # Frozen test assertions (Level 1 smoke + Level 2 domain tests)
│   ├── scorers/             # iCoder metrics (Completeness, Executability, Consistency, Quality)
│   ├── tasks.json           # Canonical SRDD-20 task dataset (SHA-256 frozen)
│   ├── runner.py            # Comparative evaluation runner (MAS vs ChatDev)
│   └── benchmark_manifest.json # Production manifest recording all historical runs & audit trail
├── external/                # External baselines
│   └── ChatDev/             # Pinned ChatDev v1.0.0 submodule with patched parser
├── frontend/                # React/Vite dashboard for live run visualization
├── tests/                   # 201 deterministic offline regression tests (100% pass rate)
└── submission/              # Final submission documentation bundle
```
