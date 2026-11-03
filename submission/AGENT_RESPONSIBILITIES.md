# MAS: Agent Responsibilities & LLM Integration
## Final Year Project Submission — Multi-Agent Team Specification

---

## 1. Agent Roles & Specifications

| Agent Name | Core Responsibilities | Input Artifacts | Output Artifact | Model / Token Configuration |
| :--- | :--- | :--- | :--- | :--- |
| **ManagerAgent** | Requirement normalization, acceptance criteria definition, zero-cost complexity routing. | Raw user prompt, feedback from retries | `TaskPlan` | `max_tokens=1500`, temperature 0.0 |
| **ArchitectAgent** | Component modularity planning, minimal UML class structure, and user stories. | `TaskPlan`, Complexity label `STRUCTURED` | `Architecture`, `UserStory` | `max_tokens=2000`, temperature 0.0 |
| **DeveloperAgent** | Multi-file source code generation, entry-point (`main.py`) creation, CLI `--help` implementation, and domain logic. | `TaskPlan`, `Architecture`, Sliced context, review findings | `CodePatch` | `max_tokens=4000`, temperature 0.0 |
| **TesterAgent** | Generates internal diagnostic test cases, assesses sandbox smoke outcomes, and computes pass rate. | Workspace source code, Sandbox exit codes | `TestReport` | `max_tokens=1500`, temperature 0.0 |
| **ReviewerAgent** | Objective semantic review against acceptance criteria, cross-referencing findings with AST and sandbox evidence. | `TaskPlan`, Workspace source files, AST report, Sandbox stdout/stderr | `ReviewReport` | `max_tokens=1500`, temperature 0.0 |
| **ReflectionAgent** | Evaluates iteration marginal gain ($\Delta Q$), decides whether to `CONTINUE` repair or `STOP`. | History of `ReviewReport` and `TestReport` metrics | `ReflectionDecision` | Zero-shot deterministic or LLM reflection |

---

## 2. Evidence-Based Reviewer Verification

To eliminate phantom defects (where a reviewer agent hallucinate non-existent syntax errors or claims an entry point is missing), the **ReviewerAgent** employs deterministic evidence grounding:

1. **Syntax Error Dispositioning:** If the reviewer LLM reports a "syntax error" or "parse error", the agent runs `ast.parse()` on the file. If deterministic AST parsing succeeds, the critical finding is dispositioned as a false positive.
2. **Entry-Point Dispositioning:** If the reviewer claims "missing CLI" or "missing main function", the agent inspects the code for `def main(` or `def cli(`. If present, the finding is dispositioned.
3. **Execution Output Grounding:** If the reviewer claims "output not printed", the agent cross-references the actual stdout recorded by the sandbox execution runner.

---

## 3. Model Provider Architecture & Governance

### 3.1 Supported Provider Backends
1. **`OpenRouterProvider` (`mas/core/llm.py`):**
   - Native integration with OpenRouter API for both free models (`cohere/north-mini-code:free`, `meta-llama/llama-3.3-70b-instruct:free`, `qwen/qwen-2.5-coder-32b-instruct:free`) and commercial models (`openai/gpt-4o`, `openai/gpt-4o-mini`).
   - Strictly enforces `"provider": {"allow_fallbacks": false}` to prevent silent model substitution.
   - Enforces configurable reasoning token limits (clamped to 0 for Cohere code generation).
2. **`FakeLLMProvider` (`mas/core/llm.py`):**
   - High-speed, deterministic mock provider for unit tests, CI pipelines, and offline regression verification.
   - Generates typed, valid Pydantic schemas without outbound network calls.
3. **`GovernedHTTPClient` (`mas/core/governor.py`):**
   - Context-managed HTTP client wrapping `httpx.Client`.
   - Records every outbound attempt (successful, failed, and retry) in the persistent shared ledger `eval/outbound_transmission_ledger.json`.
   - Thread-safe and process-safe via cross-platform file locking (`msvcrt` on Windows, `fcntl` on POSIX).

---

## 4. Pydantic Schema Contracts (`mas/core/schemas.py`)

All artifacts exchanged between agents are strictly validated through Pydantic v2 schemas:

- **`TaskPlan`:** `id`, `task_id`, `name`, `description`, `complexity`, `files`, `sprint_goals`, `acceptance_criteria`, `ambiguities`.
- **`Architecture`:** `components`, `uml_class_diagram`, `file_structure`, `module_dependencies`.
- **`CodePatch`:** `files` (list of filenames), `file_contents` (mapping of filename to complete code), `summary`, `tests_expected`.
- **`ReviewReport`:** `status` (`PASSED`, `FAILED`, `NEEDS_REVISION`), `critical_issues`, `major_issues`, `minor_issues`, `findings`, `summary`.
- **`TestReport`:** `total_tests`, `passed_tests`, `failed_tests`, `pass_rate`, `coverage`, `details`.
- **`ReflectionDecision`:** `decision` (`CONTINUE`, `STOP`), `reason`, `adaptive_score`, `marginal_gain`, `iteration`.
