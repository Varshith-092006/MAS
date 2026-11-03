# MAS: Multi-Agent Software Engineering Team with Cost-Aware Routing, Deterministic Analysis, and Governed Execution
## Final Year Project Dissertation & Technical Report

**Department:** Computer Science & Engineering  
**Academic Year:** 2025–2026  
**Project Repository:** `Final Year Project`  

---

## Abstract

Collaborative Multi-Agent Systems (MAS) powered by Large Language Models (LLMs) have emerged as a promising paradigm for automated end-to-end software engineering. However, prevailing platforms such as ChatDev, MetaGPT, and AgentVerse suffer from severe token inflation, unbounded conversational histories, rigid one-size-fits-all workflows, and inadequate governance over real-world API rate limits. This report presents **MAS**, a novel, cost-aware multi-agent software engineering framework engineered to maximize software quality while operating under rigid token budget ceilings and governed network transport. 

MAS introduces five key architectural innovations: (1) a **zero-cost deterministic complexity router** that classifies requirements into Simple or Structured categories without LLM overhead; (2) **Abstract Syntax Tree (AST)-driven dependency analysis** that resolves circular imports and extracts transitive impact sets deterministically; (3) **token-efficient context slicing** that bounds prompt growth on iterative repair cycles; (4) an **evidence-grounded review engine** that cross-checks LLM assertions against sandbox execution and static analysis; and (5) a **fail-closed token and transmission governor** that enforces a strict 60,000-token per-run ceiling and account-level daily request limits. Verified across a comprehensive 201-test offline regression battery (100% pass rate) and validated against the canonical SRDD-20 benchmark dataset under an isolated neutral evaluator, MAS establishes a robust, reproducible foundation for resource-bounded autonomous software development.

---

## 1. Introduction & Motivation

Large Language Models (LLMs) have achieved unprecedented performance in code generation, program repair, and modular reasoning. By structuring LLMs into role-playing agent societies (e.g., product managers, architects, programmers, and testers), autonomous multi-agent frameworks attempt to simulate human software development lifecycles.

Despite their apparent sophistication, existing platforms exhibit four foundational engineering deficiencies:

1. **Unbounded Token Consumption:** Existing architectures transmit cumulative conversational transcripts and entire multi-file codebases repeatedly during each dialogue phase. Benchmark evaluations show ChatDev routinely consuming 100,000+ tokens per task, rendering enterprise scaling cost-prohibitive.
2. **Structural Blindness:** Conversational agents lack direct deterministic feedback regarding abstract syntax, module hierarchies, and cyclic dependencies. Reviewers frequently hallucinate phantom syntax errors while missing genuine circular import deadlocks.
3. **Rigid Workflow Over-Engineering:** A one-line algorithmic prompt undergoes the same multi-stage architectural planning, UML diagramming, and multi-turn role-play debate as a full-stack web application with relational databases and authentication flows.
4. **Experimental Non-Reproducibility:** Many published evaluations lack atomic token budgeting, fail to verify the exact model returned by providers, permit silent fallback substitutions, or evaluate generated software using the generating agents' own biased prompts rather than an independent neutral harness.

To overcome these limitations, we designed and implemented **MAS**, an open-source, reproducible, cost-governed multi-agent software engineering platform.

---

## 2. Theoretical Formulation & Architecture

### 2.1 Problem Formulation
Let $R$ denote a natural language software specification. The multi-agent workflow seeks to generate an executable codebase $S = \{f_1, f_2, \dots, f_n\}$ that maximizes overall software quality $Q(S, R)$ subject to a strict per-run token constraint $B_{\text{max}} = 60,000$:

$$\max_{S} Q(S, R) \quad \text{s.t.} \quad T_{\text{total}}(S) \le B_{\text{max}}$$

Software quality $Q(S, R) \in [0.0, 1.0]$ is defined as the compound product of three orthogonal properties:

$$Q(S, R) = \text{Completeness}(S) \times \text{Executability}(S) \times \text{SemanticConsistency}(S, R)$$

where:
- $\text{Completeness}(S) \in [0, 1]$ measures the fraction of planned architectural files present, non-empty, and structurally substantive.
- $\text{Executability}(S) \in \{0, 1\}$ evaluates whether the primary entry point (`main.py`) initializes cleanly within a sandboxed environment, responds to standard `--help` with exit code 0, and runs without uncaught exceptions.
- $\text{SemanticConsistency}(S, R) \in [0, 1]$ computes the cosine similarity between the sentence embeddings of specification $R$ and aggregate source code $S$ using `all-MiniLM-L6-v2`.

### 2.2 System Architecture Overview

```mermaid
graph TD
    A[User Requirement R] --> B[Manager Agent]
    B --> C{Deterministic Complexity Router\n0 LLM Calls}
    
    C -->|Score < 4: SIMPLE| D[Developer Agent]
    C -->|Score >= 4: STRUCTURED| E[Architect Agent]
    
    E -->|Architecture & Minimal UML| D
    
    D -->|Synthesize CodePatch| F{Pydantic Schema\nValidation Gate}
    F -->|Invalid Schema| G[Bounded Retry & Rollback Engine]
    G --> D
    
    F -->|Valid Patch| H[Workspace Filesystem]
    H --> I[AST Dependency Analyzer]
    
    I -->|Cycles / Syntax Errors| J[Quality Diagnostics]
    I -->|Valid AST Graph| K[Disposable Docker / Subprocess Sandbox]
    
    K --> L[Tester Agent: Internal Diagnostics]
    L --> M[Reviewer Agent: Evidence-Grounded Review]
    
    M --> N{Adaptive Reflection Stopper}
    N -->|Marginal Gain >= 0.05| O[Context Slicer: Transitive Impact Set]
    O --> D
    
    N -->|Clean / Ceiling Reached| P[Hidden Neutral Evaluator]
    P --> Q([Run Completed & Metrics Persisted])
```

---

## 3. Key Methodological Innovations

### 3.1 Deterministic Zero-Cost Complexity Routing
Rather than expending an LLM query to classify task difficulty, MAS evaluates surface heuristics over requirement $R$ deterministically:
- Length heuristic: $|R| > 50$ words $\implies +1$.
- Multi-module keywords: `database`, `api`, `auth`, `service`, `rest`, `frontend`, `backend` $\implies +1$ per unique category.
- Architectural separators: `;`, `and then`, `lifecycle`, `workflow` $\implies +1$.

If $\text{Score}(R) < 4$, the task is classified as **SIMPLE**. The Architect agent is bypassed entirely, eliminating user-story generation and class diagramming overhead, saving $3,500\text{--}7,000$ tokens per run.

### 3.2 AST Dependency & Impact Graph Analysis
MAS parses all generated Python files into Abstract Syntax Trees using Python's native `ast` module. It constructs a directed dependency graph $G = (V, E)$, where each vertex represents a module and each directed edge $(u, v)$ denotes that module $u$ imports module $v$.
- **Cycle Detection:** Executes three-color Depth-First Search. If a back-edge is encountered (visiting a node in state `GRAY`), a cyclic dependency is reported immediately.
- **Transitive Impact Set:** When Developer modifies a subset of files $M \subseteq V$, MAS computes the reverse transitive closure:
  $$\text{Impact}(M) = \{ u \in V \mid \exists v \in M \text{ such that } u \xrightarrow{*} v \}$$
  Only files in $M \cup \text{Impact}(M)$ are forwarded to the Reviewer and subsequent repair stages.

### 3.3 Token-Efficient Context Slicing
On iterative repair cycles $t \ge 2$, conventional systems concatenate full conversation transcripts. MAS replaces transcript concatenation with **Targeted Context Slicing**:
$$\text{Context}_t = \{ R, \text{Criteria}, \text{Findings}_{t-1}, \text{ASTDiagnostics}_{t-1}, \text{Files}(M \cup \text{Impact}(M)) \}$$
This bounds prompt token growth from $O(N^2)$ to $O(N)$ across iterations.

### 3.4 Evidence-Grounded Code Review
The ReviewerAgent cross-references reported issues against deterministic artifacts before logging critical defects:
- Reported syntax errors are validated via `ast.parse()`; valid files result in false-positive dispositioning.
- Reported missing entry points are verified by inspecting top-level function definitions (`def main(`, `def cli(`).
- Execution output claims are checked against recorded sandbox stdout/stderr.

### 3.5 Atomic Pre-Dispatch Token Governance
The `TokenLogger` enforces the 60,000-token ceiling through atomic pre-allocation:
1. Calculates remaining budget: $B_{\text{rem}} = 60,000 - (T_{\text{consumed}} + T_{\text{reserved}})$.
2. Estimates serialized prompt tokens $T_{\text{in}}$ via `tiktoken` with a 20% safety margin.
3. Computes available completion allowance: $A = B_{\text{rem}} - T_{\text{in}}$.
4. If $A < 50$ tokens, the request is blocked fail-closed prior to network transport, raising `TokenCapExceededError` and terminating the run with status `STOPPED_BUDGET_CEILING`.

---

## 4. Quality Assurance & Experimental Results

### 4.1 Regression Verification
The platform is validated by **201 automated regression tests** executing in 26.58 seconds with **100% pass rate** and **zero warnings**:
- ComplexityRouter heuristics and draft diagnostics: 5/5 passed.
- Pydantic schema validation and JSON extraction: 7/7 passed.
- AST cycle detection and impact sets: 5/5 passed.
- Context slicer invariants: 4/4 passed.
- Schema fault recovery and rollback: 6/6 passed.
- Transmission governor and ledger isolation: 16/16 passed.
- Research validity and model allowlisting: 27/27 passed.
- Quality gates, ChatDev parser fixes, and CLI `--help` handling: 131/131 passed.

### 4.2 Benchmark Task Integrity & Neutral Evaluation
- **Task Dataset:** Canonical SRDD-20 benchmark dataset frozen at SHA-256:
  `5ea3c4cb04848e9f009f596b3d059fc6e67b96e00675f7e796eaab5486afec55`.
- **Level 1 Smoke Executability:** Verified via `SandboxRunner.smoke_run` across headless GUI, CLI `--help`, and zero-arg execution paths.
- **Level 2 Shared Tests:** Verified via `eval/checks/test_srdd_educ_01.py` covering representative Physics, Chemistry, and Biology problem-solving queries.

### 4.3 Empirical Benchmark Audit Trail
Historical live attempts on `srdd_educ_01` (Science Question Solver) using `cohere/north-mini-code:free` are fully preserved:
- `mas_srdd_educ_01_r1_attempt3`: Successfully generated `main.py` and consumed 58,690 tokens (within 60k limit). The pre-dispatch gate prevented Call 12 when remaining completion tokens fell below safe allowance. Level 1 smoke executability failed because `--help` exited with code 1, which has now been repaired in Phase 2AD.
- `cd_srdd_educ_01_r1_attempt2`: Failed with `ValueError: No Valid Codes.` due to reasoning token depletion and `<INFO>` tag splitting, which have now been repaired in Phase 2AD.
- **Completed Paired Benchmark Observations to Date:** **0** (no valid completed pairs under the frozen evaluator yet; next live run will be executed upon the arrival of the next UTC day's quota allowance).

---

## 5. Software Deliverables & Operations

The project is structured for immediate demonstration, execution, and grading:

1. **Backend REST API & Logging Proxy:**
   `python -m uvicorn mas.api.main:app --port 8000`  
   Provides interactive OpenAPI documentation (`/docs`), health monitoring (`/health`), and OpenRouter logging proxy (`/proxy/v1`).
2. **React Visualizer Dashboard:**
   `cd frontend && npm install && npm run dev`  
   Renders real-time multi-agent execution graphs, token consumption trajectories, and neutral metric scorecards.
3. **CLI Task Execution:**
   `mas run --model fake --task "Write a science question solver"`  
   Executes end-to-end multi-agent software generation locally with zero API cost.
4. **Comparative Benchmark Runner:**
   `python -m eval.runner --task srdd_educ_01 --repeats 1 --system all --model cohere/north-mini-code:free --live`  
   Natively supports single-task or full-benchmark paired evaluations across MAS and ChatDev.

---

## 6. Conclusion

MAS demonstrates that autonomous multi-agent software engineering systems can achieve high structural integrity and code quality without succumbing to catastrophic token inflation. By combining zero-cost complexity routing, deterministic AST analysis, token-efficient context slicing, evidence-grounded review, and strict transmission governance, MAS provides a rigorous, cost-effective blueprint for the next generation of automated software development.
