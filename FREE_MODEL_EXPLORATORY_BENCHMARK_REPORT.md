# Empirical Benchmark Report: MAS vs ChatDev (Free OpenRouter Model)
## Experimental Condition: `FREE_MODEL_EXPLORATORY`

**Date of Execution:** October 11, 2026  
**Experimental Condition:** `FREE_MODEL_EXPLORATORY` (Strictly distinct from paid GPT-4o research condition)  
**Evaluated Systems:** Multi-Agent System (MAS) vs. ChatDev  
**Provider:** OpenRouter (`https://openrouter.ai/api/v1`)  
**Requested Model:** `cohere/north-mini-code:free`  
**Actual Serving Model:** `cohere/north-mini-code:free`  
**Fallback Policy:** `allow_fallbacks: false` (Strict routing enforced)  
**Total Paid API Spend:** **$0.000000** (Zero cost incurred)  
**Paid GPT-4o Benchmark Status:** `NOT_RUN` (Preserved intact)  

---

## 1. Executive Summary & Core Research Findings

This empirical benchmark evaluated the **Multi-Agent System (MAS)** against the baseline multi-agent architecture **ChatDev** on the canonical Stage 1 Software Requirements Description Dataset (SRDD) task `srdd_educ_01` (*Science Question Solver*). 

Both systems were subjected to identical execution constraints, byte-for-byte identical requirement text, the frozen neutral evaluator, and identical sandbox environments using the free coding model `cohere/north-mini-code:free` via OpenRouter.

### Summary of Comparative Outcomes:
1. **Measured Metric Comparison ($Q = C \times E \times S$):**
   - **MAS:** Completed all four lifecycle phases (Architect, Developer, Tester, Reviewer), generating valid Python source code (`calculator.py`). Achieved Completeness $C = 1.0$, Executability $E = 1.0$, Consistency/Security $S = 0.85$, yielding a composite quality score of **$Q = 0.85$** (Quality / 1k Tokens: **0.0552**).
   - **ChatDev:** Completed dialogue turns and produced workspace configurations (`ChatChainConfig.json`, `PhaseConfig.json`, etc.), but failed to emit any executable `.py` source code files into its output directory. Achieved Completeness $C = 1.0$, Executability $E = 0.0$, Consistency $S = 0.50$, yielding a composite quality score of **$Q = 0.00$** (Quality / 1k Tokens: **0.0000**).
2. **Neutral Behavioral Domain Verification:**
   - Neither system passed the domain-specific neutral behavioral test harness (`eval/checks/test_srdd_educ_01.py`). ChatDev produced no code to test. While MAS produced executable, lint-clean, and secure code, the free reasoning model drifted from the science solver requirement to basic arithmetic functions (`add`, `multiply`), failing domain assertions for physics/chemistry question solving.
3. **Did MAS Outperform ChatDev?**
   - **On composite quality ($Q$):** Yes, MAS achieved $Q = 0.85$ vs. ChatDev $Q = 0.00$.
   - **On executability ($E$):** Yes, MAS produced executable code ($E = 1.0$) whereas ChatDev produced no executable code ($E = 0.0$).
   - **On domain requirement adherence:** Neither system successfully solved science domain questions; both failed the frozen domain behavioral test suite.
4. **Quota and Scope Constraints:**
   - OpenRouter imposes a hard account limit of **50 requests per day** on free models. Prior audit showed 39 requests already consumed on the account. After conducting the smoke test and the canonical Stage 1 matched pair, 47 requests were consumed, leaving only 3 requests remaining. To avoid HTTP 429 quota exhaustion and comply with zero-cost constraints, the exploratory benchmark concluded with the canonical Stage 1 matched pair. The remaining 19 tasks are documented as incomplete due to free quota ceilings.

---

## 2. Model Configuration & Verification Audit

### 2.1 Model Smoke Test
Prior to benchmark execution, a zero-cost smoke test was conducted against OpenRouter:
- **Endpoint:** `https://openrouter.ai/api/v1/chat/completions`
- **HTTP Status:** 200 OK
- **Provider Request ID:** `gen-1791733902-ZRhLtlSaZ4aAQuLy0PZ2`
- **Requested Model:** `cohere/north-mini-code:free`
- **Actual Serving Model:** `cohere/north-mini-code:free`
- **Model Mismatch:** None (`mismatch = False`)
- **Cost Incurred:** $0.00

### 2.2 Model Routing & Enforcement
- `allow_fallbacks: false` was set on every request in both MAS (`mas/core/llm.py`) and ChatDev proxy (`mas/core/proxy.py`).
- No silent fallbacks to `openai/gpt-4o`, `openai/gpt-4o-mini`, or any paid models were permitted.
- Structured output handling was adapted in application code: because `cohere/north-mini-code:free` emits reasoning tokens and does not enforce JSON schemas natively via `response_format`, responses were extracted from `content or reasoning` and parsed with fallback bracket extraction.

---

## 3. Benchmark Task Coverage & Integrity

### 3.1 Canonical Task Specification
- **Task ID:** `srdd_educ_01`
- **Category:** `Education`
- **Title:** `Science Question Solver`
- **Canonical Requirement:**
  ```text
  Step-by-step science question solver providing explanations and solutions.
  ```
- **Expected SHA-256 Checksum:**
  `15b83bd79330fcf4a79de4ad9cbc725ffeba2a695f1b76bf4d1ca567c4740012`
- **Verified SHA-256 Checksum:**
  `15b83bd79330fcf4a79de4ad9cbc725ffeba2a695f1b76bf4d1ca567c4740012` (Exact match)

### 3.2 20-Task Dataset Coverage Status
The full benchmark catalog consists of 20 tasks (`eval/tasks.json`, SHA-256 `5ea3c4cb04848e9f...`).

| Domain | Task ID | Task Title | Exploratory Status | Reason |
| :--- | :--- | :--- | :--- | :--- |
| **Education** | `srdd_educ_01` | Science Question Solver | **COMPLETED** | Canonical matched pair executed |
| Education | `srdd_educ_02` | Culture Quiz Challenge | **INCOMPLETE** | Quota ceiling (50 req/day limit) |
| Education | `srdd_educ_03` | Culture Insights | **INCOMPLETE** | Quota ceiling (50 req/day limit) |
| Education | `srdd_educ_04` | Linguistics Analyzer | **INCOMPLETE** | Quota ceiling (50 req/day limit) |
| **Work** | `srdd_work_05` | Document Tracker | **INCOMPLETE** | Quota ceiling (50 req/day limit) |
| Work | `srdd_work_06` | Code Quality Analyzer | **INCOMPLETE** | Quota ceiling (50 req/day limit) |
| Work | `srdd_work_07` | Complexity Analyzer | **INCOMPLETE** | Quota ceiling (50 req/day limit) |
| Work | `srdd_work_08` | Lead Generation Tracker | **INCOMPLETE** | Quota ceiling (50 req/day limit) |
| **Life** | `srdd_life_09` | Price Comparison | **INCOMPLETE** | Quota ceiling (50 req/day limit) |
| Life | `srdd_life_10` | Nutrition Planner | **INCOMPLETE** | Quota ceiling (50 req/day limit) |
| Life | `srdd_life_11` | Habit Tracker | **INCOMPLETE** | Quota ceiling (50 req/day limit) |
| Life | `srdd_life_12` | Personal Finance Assistant | **INCOMPLETE** | Quota ceiling (50 req/day limit) |
| **Games** | `srdd_game_13` | Math Puzzle Quest | **INCOMPLETE** | Quota ceiling (50 req/day limit) |
| Games | `srdd_game_14` | Trivia Arena | **INCOMPLETE** | Quota ceiling (50 req/day limit) |
| Games | `srdd_game_15` | Dungeon Adventure | **INCOMPLETE** | Quota ceiling (50 req/day limit) |
| Games | `srdd_game_16` | Chess Tactical Trainer | **INCOMPLETE** | Quota ceiling (50 req/day limit) |
| **Utility** | `srdd_util_17` | Unit Converter Suite | **INCOMPLETE** | Quota ceiling (50 req/day limit) |
| Utility | `srdd_util_18` | Markdown Document Formatter| **INCOMPLETE** | Quota ceiling (50 req/day limit) |
| Utility | `srdd_util_19` | Password Security Auditor | **INCOMPLETE** | Quota ceiling (50 req/day limit) |
| Utility | `srdd_util_20` | Regex Pattern Matcher | **INCOMPLETE** | Quota ceiling (50 req/day limit) |

*Total Coverage: 1 task completed (2 runs: 1 MAS + 1 ChatDev), 19 tasks incomplete due to free quota ceilings.*

---

## 4. Matched-Pair Comparison Table (`srdd_educ_01`)

The matched comparison was executed under identical constraints using the neutral evaluator.

| Dimension / Metric | MAS Architecture (Run A) | ChatDev Baseline (Run B) | Comparison ($\Delta$ MAS vs ChatDev) |
| :--- | :--- | :--- | :--- |
| **Run ID** | `mas_srdd_educ_01_free_exp` | `cd_srdd_educ_01_free_exp` | — |
| **Evaluation ID** | `eval_free_model_exploratory_1791737975` | `eval_free_model_exploratory_1791737975` | Matched evaluation session |
| **Benchmark Condition** | `FREE_MODEL_EXPLORATORY` | `FREE_MODEL_EXPLORATORY` | Identical experimental condition |
| **Requested Model** | `cohere/north-mini-code:free` | `cohere/north-mini-code:free` | Identical model |
| **Actual Serving Model** | `cohere/north-mini-code:free` | `cohere/north-mini-code:free` | Zero model drift |
| **Fallback Path** | Disabled (`allow_fallbacks: false`) | Disabled (`allow_fallbacks: false`) | Strict routing verified |
| **Run Status** | `COMPLETED` | `COMPLETED` | Both runs executed to termination |
| **Wallclock Runtime** | **133.73 s** | **44.09 s** | +89.64 s (MAS ran multi-stage pipeline) |
| **Provider-Reported Tokens** | **15,403 tokens** | **2,519 tokens** | +12,884 tokens |
| **Token Provenance** | `PROVIDER_REPORTED` | `PROVIDER_REPORTED` | Verified upstream headers |
| **API Cost (USD)** | **$0.000000** | **$0.000000** | $0.00 across both systems |
| **Functional Completeness ($C$)** | **1.0000** | **1.0000** | Equivalent (AST parseable / manifest present) |
| **Runtime Executability ($E$)** | **1.0000** | **0.0000** | **+1.0000** (MAS executed; ChatDev emitted no `.py`) |
| **Specification Consistency ($S$)** | **0.8500** | **0.5000** | **+0.3500** (MAS lint/security clean) |
| **Composite Quality ($Q = C \cdot E \cdot S$)** | **0.8500** | **0.0000** | **+0.8500** (MAS superior composite score) |
| **Quality / 1,000 Tokens** | **0.0552** | **0.0000** | **+0.0552** |
| **Generated Artifacts** | `calculator.py` | `ChatChainConfig.json`, `PhaseConfig.json`, etc. | MAS generated code; ChatDev generated JSON only |
| **Neutral Behavioral Suite** | `False` (Failed domain assertions) | `False` (No source code found) | Neither passed domain behavioral suite |
| **Static Analysis (Ruff Errors)** | 0 errors | 0 errors (No code scanned) | Neutral |
| **Security Analysis (Bandit)** | 0 issues | 0 issues | Clean |
| **Maintainability (Radon MI)** | 100.0 (High) | 100.0 (Default) | Neutral |

---

## 5. Aggregate Metrics & Statistical Limitations

### 5.1 Aggregate Summary

| Metric | MAS ($N = 1$) | ChatDev ($N = 1$) | Matched Difference ($\Delta$) |
| :--- | :--- | :--- | :--- |
| **Mean Completeness ($C$)** | 1.0000 | 1.0000 | 0.0000 |
| **Mean Executability ($E$)** | 1.0000 | 0.0000 | +1.0000 |
| **Mean Consistency ($S$)** | 0.8500 | 0.5000 | +0.3500 |
| **Mean Composite Quality ($Q$)** | 0.8500 | 0.0000 | +0.8500 |
| **Mean Quality / 1k Tokens** | 0.0552 | 0.0000 | +0.0552 |
| **Behavioral Test Pass Rate** | 0.0% (0/1) | 0.0% (0/1) | 0.0% |
| **Mean Token Consumption** | 15,403 | 2,519 | +12,884 |
| **Total Incurred Cost** | $0.000000 | $0.000000 | $0.000000 |
| **Success Rate (Produced Code)** | 100.0% (1/1) | 0.0% (0/1) | +100.0% |

### 5.2 Missing Data & Statistical Significance
- **Sample Size:** $N = 1$ matched pair.
- **Statistical Significance:** With a sample size of $N = 1$, statistical significance tests (e.g., paired t-test, Wilcoxon signed-rank test) cannot be performed. The results represent an empirical exploratory case study rather than a generalizable population sample.
- **Missing Data Handling:** Incomplete tasks (19 tasks) are recorded as `INCOMPLETE` due to provider rate/quota limits and excluded from averages; their metrics are not imputed or assumed.

---

## 6. Analysis of System Behaviors & Failure Modes

### 6.1 ChatDev Failure to Produce Code
- **Root Cause:** ChatDev relies on a strict conversational protocol between roles (CEO, CPO, CTO, Programmer, Reviewer). In the coding phase, the Programmer agent is expected to enclose Python source code within markdown fences formatted with specific filename comments (e.g., `'''main.py ... '''`).
- **Observed Behavior:** The smaller reasoning model `cohere/north-mini-code:free` participated in dialogue turns, discussing high-level architecture, but did not adhere to the syntax convention needed for ChatDev's code parser to extract and persist `.py` files into the `WareHouse`. Consequently, ChatDev terminated successfully from an orchestration standpoint but left an empty project directory.
- **Impact on Evaluation:** Without Python source code, the neutral evaluator recorded $E = 0.0$, resulting in a composite quality score of $Q = 1.0 \times 0.0 \times 0.5 = 0.0$.

### 6.2 MAS Prompt Drift Under Free Reasoning Model
- **Root Cause:** MAS enforces a structured pipeline (Architect $\to$ Developer $\to$ Tester $\to$ Reviewer) with explicit JSON parsing and fallbacks. The Developer agent produced valid, clean Python syntax (`calculator.py`).
- **Observed Behavior:** Despite receiving the exact requirement (*"Step-by-step science question solver providing explanations and solutions"*), the model drifted toward generating generic arithmetic utilities:
  ```python
  def add(a: int, b: int) -> int:
      '''Adds two numbers.'''
      return a + b

  def multiply(a: int, b: int) -> int:
      '''Multiplies two numbers.'''
      return a * b
  ```
- **Impact on Evaluation:** The code was syntactically valid, lint-clean, and executable ($C = 1.0, E = 1.0, S = 0.85, Q = 0.85$). However, when evaluated by `eval/checks/test_srdd_educ_01.py`, which asserts science question solver classes and methods, the domain tests failed.
- **Takeaway:** MAS's pipeline resilience ensured that code was generated, refined, and executed even with a compact free model, whereas ChatDev produced no code. However, compact free models exhibit prompt drift on domain-specific requirements.

---

## 7. Model Routing Mismatches & Provider Errors

| Request Scope | Expected Model | Reported Serving Model | Mismatch? | Provider Errors Encountered |
| :--- | :--- | :--- | :--- | :--- |
| Smoke Test | `cohere/north-mini-code:free` | `cohere/north-mini-code:free` | No | None (HTTP 200) |
| MAS Pipeline | `cohere/north-mini-code:free` | `cohere/north-mini-code:free` | No | None (HTTP 200 across all 4 agents) |
| ChatDev Pipeline | `cohere/north-mini-code:free` | `cohere/north-mini-code:free` | No | None (HTTP 200 across all turns) |

*Zero model mismatches occurred. All requests strictly hit the verified free endpoint without fallbacks.*

---

## 8. Comparison with Published Literature (iCoder)

The iCoder platform (published by Wang et al.) evaluated multi-agent software development using proprietary frontier models (`openai/gpt-4o` and `openai/gpt-3.5-turbo`) on diverse software engineering benchmarks.

### Methodological Distinctions:
1. **Model Capability Disparity:** iCoder's published performance reflects frontier models with 100B+ parameters and extensive instruction fine-tuning. The current exploratory benchmark utilized `cohere/north-mini-code:free`, a compact coding/reasoning model. Direct quantitative score comparison between this exploratory benchmark and published iCoder figures would be invalid.
2. **Environment & Evaluation Differences:** iCoder utilized self-reported repository-level tasks, whereas our benchmark exercises the canonical SRDD dataset under a frozen, independent black-box neutral evaluator.
3. **Reproducibility Note:** iCoder has not been executed locally in this environment; all iCoder numbers in research documentation serve strictly as historical literature reference points.

---

## 9. Verification & System Health Evidence

### 9.1 Offline Regression Test Suite
Prior to and following the exploratory benchmark, the full automated test suite was executed:
- **Command:** `python -m pytest tests/`
- **Result:** **77 passed, 0 failed** in 109.94s
- **Verified Areas:**
  - Neutral evaluator isolation and scoring rules
  - OpenRouter error handling and HTTP 402/429 diagnostics
  - Research validity gates (model mismatch quarantining, prompt verification)
  - AST analysis, context slicing, and token logging
  - Schema consistency across runs, evaluations, metrics, and API routes

### 9.2 Frontend Production Build
The research dashboard was updated to clearly display the active model condition, distinct free-model exploratory banners, and enhanced CSV export metadata:
- **Command:** `npm run build`
- **Result:** **Clean production build** (`1488 modules transformed`, completed with zero errors).
- **Distinction Enforced:** Free-model exploratory runs are distinctly labeled with cyan banners (`FREE MODEL EXPLORATORY — NOT GPT-4o BASELINE EVIDENCE`) to prevent misattribution to the planned GPT-4o research condition.

---

## 10. Conclusion & Actionable Next Steps

1. **Benchmark Verdict:** Under `cohere/north-mini-code:free`, MAS outperformed ChatDev on composite quality ($Q = 0.85$ vs. $Q = 0.00$) because MAS's structured pipeline successfully produced executable, lint-clean code, whereas ChatDev failed to output any source code. However, neither system satisfied the domain-specific behavioral requirements due to reasoning drift in the free model.
2. **Model Sufficiency Assessment:** Free coding models such as `cohere/north-mini-code:free` are suitable for pipeline debugging, syntax validation, and orchestration testing, but lack the instruction following and domain specialization required to produce complex scientific software engineering solutions.
3. **Quota Protection Enforced:** Daily free request quotas (50 requests/day) were strictly respected; 19 tasks remain incomplete to prevent provider-level rate limit errors.
4. **Research Baseline Status:** The primary research condition (`openai/gpt-4o`) remains `NOT_RUN` and uncorrupted, ready for execution once account credits are deposited.
