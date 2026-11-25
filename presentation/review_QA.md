# Review preparation: questions and answers

Questions a reviewer may ask about the MAS project, with the answers given in the Claude session.
Started 24 Nov 2026. Each entry is added as the question is answered; the PDF is made on request.

---

## Q1. What is the project all about, and why are we doing it?

**Short answer (about 30 seconds):**
Our project is MAS, an AI software engineering team. You give it a requirement in plain English, such as "build an expense tracker that saves to SQLite", and a team of specialised AI agents turns it into a working Python project: they plan it, design it, write the code, test it, review it and improve it. We built it because a single AI assistant is good at small coding tasks but unreliable for a whole project. We wanted to show that specialised agents, with objective checks by real tools, produce code that actually runs. We tested this against ChatDev, a well-known multi-agent system, and against a single AI agent, on the same 20 benchmark tasks.

**What the project is**
- **Input:** a natural-language requirement.
- **Output:** a folder of Python files that runs with `python main.py`, plus scores showing how good it is.
- **The team, 7 roles:**
  - **Manager:** plans the task.
  - **Complexity Router:** decides whether the task is small or large.
  - **Architect:** designs larger projects.
  - **Developer:** writes the code.
  - **Tester:** runs the program.
  - **Reviewer:** finds defects.
  - **Reflection:** scores each round and decides whether to stop or improve.

  Only 4 of the 7 call the AI model. The Router, Tester and Reflection are plain code, so their checks are objective and cost nothing.
- **Also built:**
  - a web app to generate projects, inspect every run and re-run the generated code;
  - a fair benchmarking setup with a frozen evaluator.

**Why we did it**
1. **The problem:** AI coding assistants handle single tasks well, but real development spans requirements, design, coding, testing and review. One agent checking its own work misses requirements and leaves defects undetected.
2. **The research gap:** the LLM multi-agent survey (Li et al., 2024) names unreliable, hard-to-verify agent decisions as an open problem. Software is an ideal place to study it, because you can check objectively whether code runs.
3. **The research question:** can specialised LLM agents work together to automate a reliable software-development workflow?
4. **A fair, measurable comparison:** we used the metrics from the iCoder paper (You et al., 2026): Completeness, Executability, Consistency and Quality. MAS, ChatDev and a single agent got identical tasks, model, settings and scoring.

**What we found (60 official runs: 20 tasks × 3 systems)**
- **Programs that run:** MAS 20 of 20, the single agent 16 of 20, ChatDev 2 of 20.
- **Quality:** MAS 0.493, the single agent 0.383, ChatDev 0.055.
- **MAS vs ChatDev:** MAS scored higher on 19 of 20 tasks. That's statistically significant (p = 0.000004), and MAS used 69% fewer tokens.
- **MAS vs the single agent:** MAS scored higher on 12 of 20, which is not yet significant (p = 0.19). We state this honestly as a limitation and as future work.

**If the reviewer asks "so what?":** it shows that adding objective, tool-based verification inside the agent loop is what makes generated code reliably runnable, more than simply adding more agents. ChatDev uses more agents and more tokens, yet only 2 of its 20 programs ran.

---

## Q2. Does MAS run properly, and how do you compare it with ChatDev? How are the tasks run?

**Is MAS running properly?**
- **Offline end-to-end run:** the expense-tracker requirement went through every agent in order (Manager → Developer → AST analysis → Tester → Reviewer → Reflection). It finished in 2.8 s, wrote `main.py` and `calculator.py`, and stored its scores and step log. The generated program passed the evaluator's run check (exit code 0). Offline mode uses a built-in sample answer instead of the live model, so it tests the machinery, not the model.
- **Automated tests:** all 375 pass.
- **Live runs:** the two live attempts on 24 Nov failed only because Google's Gemini service returned 503 "high demand", an outage on the provider's side. Such failures are recorded as infrastructure failures and never scored.

**What gets run**
- **Tasks:** 20 tasks from the SRDD dataset (1,200 tasks), 4 from each category (Education, Work, Life, Game, Creation), frozen in `eval/tasks_v2.json`.
- **Command** (one run per task per system; it resumes across days):
  `python -m eval.runner --benchmark --live --systems mas,chatdev,single --model gemini-3.5-flash-lite --tasks-file eval/tasks_v2.json --tasks 20 --repeats 1 --require-embeddings --resume --stop-at-budget`
- **For each task, the runner runs three systems one after another:**
  1. **MAS:** our `MASWorkflow`, running inside the same Python process.
  2. **ChatDev:** the real ChatDev code, pinned to one fixed commit, started as a separate program (`python run.py --task "<requirement>" --name <task> --model <model>`). Its output folder is copied into our workspace.
  3. **Single agent:** one LLM call that writes the whole project (the "no team" baseline).

**How it's kept fair**
- **Same input:** identical requirement text for all three, plus the same rule: the program must run with `python main.py`.
- **Same model:** one pinned model (`gemini-3.5-flash-lite`), no fallback; a run aborts if the provider answers with a different model.
- **Same settings:** temperature 0 is forced for ChatDev by our proxy; the output cap is 8,192 tokens for all.
- **Same token counting:** ChatDev's calls pass through our logging proxy, which records the provider-reported token usage exactly as MAS's own client does.
- **Same quota rules:** every request from every system goes through the same quota governor.
- **Same scoring:** one frozen evaluator scores every project identically (Completeness, Executability, Consistency, Quality).
- **Same result rule:** a task's official result is the first attempt that wasn't an infrastructure failure. Server outages are rerun; bad code is never rerun and counts as it is.

**About the ChatDev patch** (`patches/chatdev_local.patch`, recorded with a checksum in DECISIONS.md):
- it lets ChatDev use our OpenAI-compatible endpoint (the proxy), so it can run on Gemini;
- it makes ChatDev's extraction of code from the model's replies more robust, which helps ChatDev;
- it stops ChatDev's review loop after one full review-and-fix cycle instead of letting it loop indefinitely.

**How results are compared:** per task, as pairs, with a Wilcoxon signed-rank test and bootstrap 95% confidence intervals.

**Results:** MAS scored higher than ChatDev on 19 of 20 tasks (p = 0.000004). ChatDev's programs ran in only 2 of 20 cases; a typical failure is a `main.py` that starts with the text `main.py` on line 1.

**A likely follow-up:** "Didn't the patch change ChatDev?" Yes, but only for compatibility and robustness: it doesn't change ChatDev's agents, roles or prompts. The code-extraction part makes ChatDev more likely to succeed, so it doesn't bias the comparison towards MAS.

---

## Q3. What is the logging proxy? How are the results and metrics compared (with one example), and which algorithms are used?

### 1. The logging proxy
A small web service (`mas/core/proxy.py`, running locally at `127.0.0.1:8089`) that sits between ChatDev and the AI model:
`ChatDev → logging proxy (our code) → Gemini API`, and the reply comes back the same way while the proxy records every call in `mas.db`.

**Why we need it:** ChatDev is someone else's program. We can't add our measurement code inside it, but we can tell it which address to send its model requests to (`OPENAI_BASE_URL`). We point it at the proxy, and the proxy forwards each request to Gemini. On every call it:
1. **forces the same settings** as MAS: temperature 0, output capped at 8,192 tokens;
2. **pins the model** to `gemini-3.5-flash-lite` and rejects any reply from a different model (`MODEL_MISMATCH`);
3. **applies the same quota rules** through the same quota governor as MAS (12 per minute, 450 per day);
4. **enforces the token budget**: it reserves the expected tokens before sending, and refuses if the run's budget would be exceeded;
5. **records the real token use**: the provider-reported input, output and total tokens per call;
6. **tags each call with its run**, so "tokens per task" can be compared fairly.

So ChatDev's tokens are counted from the same provider-reported numbers as MAS's own client records. That makes the "69% fewer tokens" comparison fair.

### 2. Worked example: task srdd_crea_01, "Color Palette Picker"
Requirement: "a photo software application that allows users to generate color palettes based on the colors found in a photo…", plus the shared rule that the program must run with `python main.py` and exit cleanly with `--help`. All three systems got exactly this text. All numbers below were recomputed from the saved code folders with the evaluator's own functions and match `results.csv` exactly.

| Metric | MAS | Single agent | ChatDev |
|---|---|---|---|
| Files | main.py, palette_picker.py, test_main.py | app.py, image.py, main.py, palette.py | main.py, palette_picker.py |
| Functions found (empty ones) | 14 (0) | 17 (0) | 0 (palette_picker.py has a syntax error, so the evaluator can't read it) |
| Completeness (C) | 1.0 | 1.0 | 1.0 (see the note below) |
| Executability (E) | 1: runs | 1: runs | 0: crashes on line 1 |
| Consistency (S) | 0.6541 | 0.6281 | 0.6296 |
| Quality = C × E × S | 0.6541 | 0.6281 | 0.0 |
| Tokens / LLM calls | 7,352 / 3 | 4,097 / 1 | 59,052 / 15 |

**The four scoring algorithms**
1. **Completeness:**
   - Parse every Python file into an abstract syntax tree (AST).
   - Count the functions, and the "unimplemented" ones: a body that's only `pass`, `...`, a docstring, or `raise NotImplementedError`.
   - Completeness = 1 − unimplemented ÷ total.
2. **Executability:** a "smoke run" in a sandbox, with a 45-second limit:
   - Import `main.py` and call `main()`; desktop windows are opened and closed straight away, without waiting for anyone.
   - If the program exits with a usage error, `python main.py --help` must exit with 0, and a run with a test file must not crash.
   - Executability = 1 if it passes, else 0.
3. **Consistency:**
   - Turn the requirement text and the code (its first 2,000 characters) into 384-number vectors with the `all-MiniLM-L6-v2` sentence-embedding model.
   - Take their cosine similarity, clipped to the range 0–1.
   - All 60 official runs used real embeddings, not the word-overlap fallback.
4. **Quality** = C × E × S: if any one part is 0, the project scores 0.

**Why ChatDev scored 0 here:** its `main.py` contains only the text `main.py`, which Python treats as an undefined name (`NameError`), so the program crashes on line 1; its other file has a syntax error at line 221.

**A weakness to be ready for:** ChatDev still gets Completeness 1.0. The evaluator skips files it can't parse, finds 0 functions, and the metric's rule scores "no functions" as 1.0. Only the run check catches the broken project, which is why Quality multiplies the scores: a broken program can't score above 0.

### 3. How the systems are compared: the statistical algorithms
**The official result per task** is the first attempt that wasn't an infrastructure failure. Server outages are rerun; bad code is never rerun and counts as it is. That gives exactly 20 tasks × 3 systems = 60 runs.

1. **Averages:** the mean Quality per system: MAS 0.493, single agent 0.383, ChatDev 0.055.
2. **Bootstrap 95% confidence interval:** resample the 20 task scores with replacement 10,000 times (seed 42), take each resample's mean, and keep the middle 95%. MAS's range (about 0.43–0.55) doesn't overlap ChatDev's (0.00–0.14). Bootstrap intervals come from random resampling, so the third decimal can shift slightly between implementations (0.433–0.549 vs 0.434–0.548 for MAS); the conclusions don't change.
3. **Wilcoxon signed-rank test (paired):** for each task, take MAS's score minus the other system's on the same task, rank the differences by size, and test whether the positive and negative ranks are balanced. Pairing by task cancels out the fact that some tasks are simply harder than others.
4. **Effect size d_z:** the mean of the per-task differences divided by their standard deviation. It measures how large the gap is, not just whether it exists.

| Comparison | MAS wins (of 20) | Mean difference | Wilcoxon p | d_z | Verdict |
|---|---|---|---|---|---|
| MAS vs ChatDev | 19 | +0.438 | 0.000004 | 2.18 (very large) | Significant |
| MAS vs single agent | 12 | +0.110 | 0.19 | 0.40 (small to medium) | Not significant |

**How to say it in the viva:** "We score every project with one frozen evaluator using the iCoder metrics. Then we compare the systems task by task with a paired Wilcoxon test and bootstrap confidence intervals. MAS beats ChatDev on 19 of 20 tasks, and that's significant. Its edge over a single agent is real on average but not significant with 20 tasks, so we'd need more tasks to confirm it."

---

## Q4. What is the tech stack?

**One-line answer:** a Python 3.11 backend (FastAPI, SQLAlchemy and Pydantic) running the agent system, a React web app on top, Google's Gemini model as the AI, and a SQLite database. Evaluation uses sentence-transformer embeddings and SciPy statistics.

| Layer | Technology | Version | What we use it for |
|---|---|---|---|
| Language | Python | 3.11 | The whole agent system, evaluation and backend |
| AI model | Google Gemini `gemini-3.5-flash-lite` | free tier | The LLM behind the Manager, Architect, Developer and Reviewer; reached through Google's OpenAI-compatible API |
| HTTP client | httpx | 0.28 | Calls to the Gemini API, wrapped in our quota governor |
| Data validation | Pydantic | 2.11 | The typed artifacts the agents exchange (TaskPlan, Architecture, CodePatch, TestReport, ReviewReport…) |
| Backend API | FastAPI + Uvicorn | 0.104 / 0.24 | REST API (`/runs`, `/evaluations`, `/config`, quick-test, open), WebSocket updates, and the logging proxy |
| Database | SQLite through SQLAlchemy | 2.0 | `mas.db`: runs, agent steps, model calls, scores (Docker Compose can use PostgreSQL 15 instead) |
| Code analysis | Python `ast` module | built in | Dependency graph, cycle detection, empty-function detection, design conformance |
| Code quality tools | Ruff · Bandit · Radon | 0.16 · 1.9 · 6.0 | Style and errors · security issues · maintainability index |
| Sandbox | Docker (`python:3.11-slim`, no network, 512 MB) or an isolated subprocess | – | Running generated programs safely, with a 45-second limit |
| Consistency metric | sentence-transformers (`all-MiniLM-L6-v2`) on PyTorch | 6.2 / 2.15 | Embeds the requirement and the code for cosine similarity |
| Statistics | NumPy · SciPy | 2.4 · 1.15 | Bootstrap confidence intervals, Wilcoxon signed-rank test |
| Token counting | tiktoken | – | Token estimates before sending, for the budget reservation |
| Frontend | React + Vite | 18.3 / 5.4 | The web app (Overview, Generate, Benchmark, Runs, Compare…) |
| Styling and icons | Tailwind CSS · lucide-react | 3.4 · 0.344 | Light, professional theme; icons |
| Reports | Matplotlib + our scripts | 3.10 | Figures, the HTML dashboard, LaTeX tables |
| Testing | pytest | 9.1 | 375 automated tests, none of which call the live model |
| Baseline system | ChatDev | pinned commit `c1c31e2` + our patch | The comparison system |
| Config and secrets | YAML (`config.yaml`) + `.env` | – | Settings; the API key stays in `.env`, which is git-ignored |

**How it fits together:** the React web app calls the FastAPI backend, which starts the MAS orchestrator. The orchestrator runs the seven agents (Manager, Router, Architect, Developer, Tester, Reviewer, Reflection). The four LLM agents call the Gemini API through httpx and the quota governor. Everything is stored in SQLite (`mas.db`), the workspace folders (generated code) and `results.csv`.

**If the reviewer asks "why these choices?"**
- **Python:** the generated projects are Python, and the AI and evaluation libraries (sentence-transformers, SciPy) are Python.
- **FastAPI:** fast, async (it handles other requests while waiting on slow ones), and it uses the same Pydantic models as the agents.
- **SQLite:** no server to set up, a single file, enough for one user.
- **Gemini free tier:** the project has no budget, and one pinned model keeps the comparison fair.
- **React + Vite:** quick development and a responsive interface.

---

## Q5. Did you use LangChain or LangGraph?

**No.** Neither is imported anywhere in the code, LangChain isn't installed, and neither is listed in `pyproject.toml`. (LangGraph happens to be installed on the laptop, but nothing uses it.)

**What MAS uses instead:** its own orchestrator in plain Python, `MASWorkflow.run()` in `mas/core/workflow.py`. It follows the same idea as LangGraph, but by hand:

| LangGraph concept | How MAS does it |
|---|---|
| Shared graph state | `MASState`, a typed dictionary (`TypedDict` in `mas/core/state.py`) passed from agent to agent |
| Nodes | The agents: Manager, Router, Architect, Developer, Tester, Reviewer, Reflection |
| Conditional edge | The Router's SIMPLE/STRUCTURED decision (whether to run the Architect) |
| Loop with an exit condition | A `while` loop of at most 3 rounds; Reflection's STOP/CONTINUE decides |
| Checkpointing | Our own `CheckpointManager`: snapshots, rollback, and restoring the best round |

**Why we didn't use a framework:**
1. **Control over every API call.** On the free tier (450 requests a day), each call has to pass our quota governor, token-budget reservation and retry rules. A framework adds hidden calls and retries we couldn't measure exactly.
2. **Fair, exact measurement.** Token counts must be the provider's own numbers, recorded per agent. Our own client does that directly.
3. **Determinism and testing.** Without a framework, all 375 tests run offline with a fake model, and the loop logic is easy to audit.
4. **Fewer dependencies.** A small, transparent codebase is easier to explain and reproduce.

**Watch out: the design documents say LangGraph.** The HLD says the agents "are made with a LangGraph state graph", the LLD says "LangGraph for the agent workflow", and "Documentation for Building" has a "LangGraph State Schema" section.

**Honest answer if asked:** "We designed it as a LangGraph state graph. During implementation we wrote the orchestrator ourselves, following the same state-and-nodes pattern, because we needed exact control over every API call on the free tier."

---

## Q6. What are we trying to achieve here?

**Short answer (to say out loud):**
We're trying to show that a team of specialised AI agents, whose work is checked by real tools rather than by the AI judging itself, can turn a plain-English requirement into a working program more reliably and more cheaply than existing approaches. We prove it with a fair, measurable comparison against ChatDev and a single AI agent.

**What we aim to achieve, five goals:**

| # | Goal | How we measure it | Where we stand |
|---|---|---|---|
| 1 | Automate the full development workflow (plan → design → code → test → review → improve) from one requirement | A working multi-agent system with 7 roles, plus a web app | Done: built, with 375 tests passing |
| 2 | Make generated code reliable: it must actually run | Executability, the share of programs that run without error | MAS 20 of 20, ChatDev 2 of 20, single agent 16 of 20 |
| 3 | Get higher overall quality than an existing multi-agent system | Quality = Completeness × Executability × Consistency (the iCoder paper's metric) | MAS 0.493 vs ChatDev 0.055; higher on 19 of 20 tasks, p = 0.000004 |
| 4 | Be efficient: fewer AI calls and tokens, within a free tier | Tokens and LLM calls per task | 14,689 tokens and 4.4 calls per task, vs ChatDev's 47,191 and 14.8 (69% and 70% fewer) |
| 5 | Compare fairly and reproducibly | Same requirement, model, settings, token counting and frozen evaluator for every system; paired statistical tests | Done: 60 official runs, every number traceable in `results.csv` |

**The research question:** can specialised LLM agents work together to automate a reliable software-development workflow?

**Our hypothesis:** what makes AI-generated code reliable isn't simply having more agents (ChatDev has more, and uses 3× the tokens). It's objective verification inside the loop: running the program, scanning for empty functions, and static analysis tools, combined with a stop rule that decides when the code is good enough.

**What counts as success, honestly stated:**
- **Better than ChatDev:** clearly shown and statistically significant.
- **Runnable code every time on our 20 tasks**, at a fraction of ChatDev's cost.
- **Better than a single agent:** higher on average (0.493 vs 0.383, higher on 12 of 20 tasks), but not yet statistically significant (p = 0.19). Showing that clearly needs more tasks and repeats, which is our main future work.

**The bigger picture:** the LLM multi-agent survey (Li et al., 2024) names unreliable, hard-to-verify agent decisions as an open problem. Software engineering lets us test reliability objectively, because a program either runs or it doesn't. Our project is a practical step towards trustworthy AI development teams.

---

## Q7. What is our goal relative to the iCoder agent, and which results or metrics do we want to achieve?

**Key fact first:** iCoder's code was never released, so it can't be run. Every iCoder number comes from its paper (You et al., Information and Software Technology 198 (2026) 108224, Tables 1–4), and the project treats those numbers as reference points only.

**Our goal relative to iCoder:**
1. **Build iCoder's key ideas into a lightweight, free-tier system** (`PAPER_MAPPING.md` lists each one):
   - complexity-driven task decomposition → our Complexity Router;
   - the requirement bot and design bot → our Manager and Architect;
   - its dependency-graph review → our AST dependency graph and cycle check;
   - design-vs-code validation → our conformance check;
   - the "no TODO or `pass`" placeholder check → our Tester and repair loop;
   - its review-then-test loop → our Reflection score S_t with stop rules.
2. **Reproduce the paper's main claim in our own fair experiment:** a structured multi-agent system beats ChatDev on the same four metrics.
3. **Do it at a fraction of the cost:** iCoder's paper shows it used 3.4× ChatDev's tokens. We aimed to use fewer tokens than ChatDev, not more.

**Paper numbers vs ours**

| Metric | iCoder, paper (GPT-4o, 20 tasks) | ChatDev, paper (GPT-4o) | MAS, ours (Gemini Flash Lite, 20 tasks) | ChatDev, ours |
|---|---|---|---|---|
| Completeness | 0.996 | 1.000 | 1.000 | 0.950 |
| Executability | 0.95 | 0.80 | 1.00 (20 of 20) | 0.10 (2 of 20) |
| Consistency | 0.837 | 0.819 | 0.493 | 0.501 |
| Quality | 0.792 | 0.655 | 0.493 | 0.055 |
| Tokens per task | 104,883 | 30,417 | 14,689 | 47,191 |

(With GPT-3.5 on 100 tasks, the paper reports iCoder Quality 0.690 vs ChatDev 0.591, and 411,145 vs 22,327 tokens per task.)

**The targets we set, and where we landed**
- **Beat ChatDev on Quality, significantly, with paired tests:** achieved. 0.493 vs 0.055; higher on 19 of 20 tasks, p = 0.000004.
- **Executability at least iCoder's 0.95:** achieved. 1.00: every MAS program ran.
- **Completeness close to 1:** achieved. 1.000.
- **Use fewer tokens than ChatDev (iCoder used 3.4× more):** achieved. 69% fewer tokens, 70% fewer calls.
- **Match iCoder's absolute Quality of 0.79:** not comparable, for the reasons below.

**Why our Quality of 0.493 can't be compared directly with iCoder's 0.79:**
1. **The Consistency scale is different.** The paper min-max normalises its Consistency scores; we use the raw cosine similarity, clipped to 0–1. That puts our scores around 0.49 against their 0.83 for every system, ChatDev included, and since Quality multiplies by Consistency, it pulls our Quality down too.
2. **A different model:** a small free-tier "Lite" model against GPT-4o.
3. **Different tasks:** our 20 SRDD tasks aren't the paper's 20.

**So compare ratios, not raw numbers.** In the paper, iCoder beats ChatDev by about 1.2× on Quality. In ours, MAS beats ChatDev by about 9×. Be honest here: much of that bigger gap is because ChatDev struggled badly on the small model (only 2 of 20 ran, against 0.80 in the paper). MAS's advantage on executability is real, but the size of the gap partly reflects ChatDev's weakness with this model.

**The one-sentence answer for the reviewer:**
"iCoder isn't open source, so we can't run it. We implemented its core ideas in a free-tier system, used its exact metrics, and reproduced its main claim that a structured multi-agent system beats ChatDev. MAS scored higher on 19 of 20 tasks while using a third of ChatDev's tokens, whereas iCoder used 3.4× ChatDev's tokens. Absolute scores differ from the paper because of the model, the tasks and a different Consistency scale, so the published numbers are indicative only."

---

## Q8. What are the main modules?

The project has three main modules, the same three as in the presentation (one per team member). Each one is built from specific folders in the code.

**Module 1: Requirement Analysis & Planning.** Turns a plain-English requirement into a plan.

| Part | File | What it does |
|---|---|---|
| Manager agent (LLM, 1 call) | `mas/agents/manager.py` | Builds the TaskPlan: description, files, goals, acceptance criteria |
| Complexity Router (no LLM) | `mas/agents/router.py` | Scores the requirement 0–9 with fixed rules. A score of 4 or more is STRUCTURED, otherwise SIMPLE |
| Architect agent (LLM, 2 calls, STRUCTURED only) | `mas/agents/architect.py` | Designs components, a class diagram, the file list and user stories |
| Artifact policy | `mas/agents/base.py`, `mas/core/schemas.py` | Every output is a validated Pydantic object. If invalid, it's retried with the error, then rolled back to a checkpoint |

**Module 2: Code Generation & Verification.** Writes the code, checks it with real tools, and improves it in rounds.

| Part | File | What it does |
|---|---|---|
| Developer agent (LLM) | `mas/agents/developer.py` | Writes every file as `=== FILE ===` blocks, plus one targeted repair if checks fail |
| Deterministic checks | `mas/analysis/deterministic_checker.py` | Is `main.py` there, does every file parse, are there empty functions, does it pass a smoke run |
| Code analysis | `mas/analysis/ast_analyzer.py`, `conformance.py`, `quality_tools.py` | Import graph and cycles, design-vs-code check, Ruff, Bandit, Radon |
| Tester (no LLM) | `mas/agents/tester.py` + `mas/analysis/sandbox.py` | Runs the program in a sandbox, checks `--help`, runs the developer's own tests |
| Reviewer agent (LLM) | `mas/agents/reviewer.py` | Lists critical, major and minor findings for the next round |
| Reflection (no LLM) | `mas/agents/reflection.py` | Computes the round score S_t. Stops when the code is clean, when gains stall, or after 3 rounds, keeping the best round |
| Orchestrator | `mas/core/workflow.py` | Runs the whole loop over a shared state |

**Module 3: Evaluation, Benchmark & Web App.** Measures MAS fairly against other systems and gives the user an interface.

| Part | File | What it does |
|---|---|---|
| Benchmark runner | `eval/runner.py` | Runs MAS, ChatDev and the single agent on the 20 tasks; resumes across days |
| Frozen evaluator | `eval/neutral_evaluator.py`, `eval/scorers/icoder_metrics.py` | Computes Completeness, Executability, Consistency and Quality, the same way for every system |
| Baselines | `eval/chatdev_adapter.py`, `mas/baselines/single_agent.py` | Pinned ChatDev (through the logging proxy) and the one-call single agent |
| Quota and fairness | `mas/core/governor.py`, `mas/core/proxy.py`, `mas/core/llm.py` | Free-tier limits (12 per minute, 450 per day), token counting, same model and settings |
| Statistics and reports | `eval/stats.py`, `scripts/make_report.py`, `make_dashboard.py` | Bootstrap confidence intervals, Wilcoxon test, tables, dashboard |
| Web app | `mas/api/` (FastAPI) + `frontend/` (React) | Generate projects, inspect runs, run the generated code, compare systems |

**How they connect:** the requirement goes through Module 1 (plan), then Module 2 (code → check → test → review → reflect, up to 3 rounds), which produces the project; Module 3 then scores it with the frozen evaluator, compares the systems, and presents the results in reports and the web app.

**The short answer for the viva:** "Module 1 understands and plans the requirement, Module 2 builds and verifies the code in a loop, and Module 3 measures it fairly against ChatDev and a single agent, and presents it through a web app."

---

## Q9. How are we dealing with hallucinations?

**Short answer (to say out loud):**
"We never trust the model's own claims. Every output is checked by something that can't hallucinate: the schema validator, the Python parser, the sandbox that actually runs the program, and static-analysis tools. The Reviewer is shown these real results, and the decision to stop is based mostly on the objective signals, not on the AI's opinion."

**How hallucinations show up in code generation, and what catches each kind:**

| Kind of hallucination | Example | How MAS deals with it | Where in the code |
|---|---|---|---|
| Invented functions, modules or APIs | `import colorlib` (doesn't exist), calling a method that isn't defined | The sandbox actually runs the program. A missing import or name crashes it, and the crash text goes back to the Developer for one targeted repair | `deterministic_checker.py`, `tester.py`, `sandbox.py` |
| Fake or empty code that "looks done" | A function containing only `pass`, `...`, a docstring or `TODO` | An AST placeholder scan flags every such function, and the Developer must fill it in. The Completeness metric counts them too | `tester.py` (`scan_placeholders`) |
| Malformed output | Broken JSON, missing fields, files without names | Every agent output must pass Pydantic schema validation. If it fails, it's retried with the exact error, then rolled back to a checkpoint (at most 3 attempts). Code arrives in simple `=== FILE ===` blocks, which a small model gets wrong less often than JSON | `base.py`, `schemas.py`, `developer.py` |
| The AI reviewer claiming "it works" | The Reviewer says PASSED although the program crashes | Grounded review: the Reviewer is given the real evidence (sandbox exit code, test pass rate and failure output, Ruff, Bandit, import cycles, design conformance). If its own reply is invalid 3 times, it defaults to the safe answer, NEEDS_REVISION | `reviewer.py` |
| Being talked into stopping too early | The AI's optimism ends the loop | Reflection's score S_t is 85% objective signals (tests 30%, Ruff 10%, Bandit 15%, Radon 10%, completeness/runs 20%) and only 15% the Reviewer's opinion. A "clean" stop needs every check to pass and no critical defects | `reflection.py` |
| Drifting from the design | Files or classes the Architect planned never get built | A design-conformance check compares the planned files and classes with the ones actually in the code, using the AST | `conformance.py` |
| Drifting from the requirement | The code solves a different problem | Acceptance criteria from the Manager go into every Developer and Reviewer prompt; the Consistency metric then measures requirement–code similarity | `manager.py`, `icoder_metrics.py` |
| Silent model swap or randomness | The provider answers with a different model | The run aborts on any model mismatch, and temperature is 0 | `llm.py`, `proxy.py` |

**The evidence that it works:** MAS's programs ran in 20 of 20 tasks, against 2 of 20 for ChatDev, which has no execution-based checking in its loop. Its crashes were exactly the hallucinated kind, such as a `main.py` containing only the text `main.py`.

**The honest limits** (say them before the reviewer does):
1. Code that runs but is logically wrong can still pass. The smoke run proves the program starts and exits cleanly, not that every feature is correct.
2. Consistency is text similarity, not correctness. It can't prove that every requirement is implemented.
3. The Reviewer is still an LLM. It can miss problems; the grounding reduces errors but doesn't remove them.
4. No human approval step sits inside the loop; change requests happen between runs.

**Future work here:** generating real feature tests from the acceptance criteria, and running them as part of the Tester.

---

## Q10. What is the code on slide 26 ("Code and Program Output")?

Slide 26 shows two kinds of proof that the work is real: a piece of our own source code (left) and real output from programs the systems generated (right).

**Left: the stop rule from our Reflection agent**
File `mas/agents/reflection.py`, function `evaluate_stop`. The slide shows a simplified excerpt; only the reason messages are shortened. This code decides, after each round, whether MAS stops or tries to improve the code again.

```python
def evaluate_stop(self, iteration, current_score,
                  previous_score, has_critical_defects, tests_pass):
    delta = round(current_score - previous_score, 4)
    if not has_critical_defects and tests_pass:
        return "STOP", "clean_result", delta
    if delta < self.stop_epsilon:
        self.consecutive_low_gain += 1
    else:
        self.consecutive_low_gain = 0
    if self.consecutive_low_gain >= self.patience:
        return "STOP", "marginal_gain_plateau", delta
    if iteration >= self.max_iterations:
        return "STOP", "max_iterations", delta
    return "CONTINUE", f"iteration {iteration + 1}", delta
```

**Line by line:**
- **Inputs:** the round number, this round's score S_t, last round's score, whether the Reviewer found a critical defect, and whether every Tester check passed.
- **`delta`:** the gain, how much this round improved the code.
- **Rule 1, `clean_result`:** no critical defect and every check passed → STOP, the code is good.
- **Counting low gains:** if the gain is below `stop_epsilon` (0.02 in `config.yaml`), count it as a weak round; a good round resets the count.
- **Rule 2, `marginal_gain_plateau`:** 2 weak rounds in a row (`patience` = 2) → STOP, more rounds aren't helping.
- **Rule 3, `max_iterations`:** round 3 reached (`max_iterations` = 3) → STOP, so cost stays bounded.
- **Otherwise, CONTINUE:** the Developer gets the review findings and test failures and repairs the code.

**Why it matters (and how it differs from iCoder):** iCoder loops until its review and tests pass, with no fixed bound. Our rule stops early when the code is clean, stops when improvements stall, and never goes beyond 3 rounds. When it stops on the limit, the orchestrator keeps the best-scoring round rather than the last one. That's how MAS kept to about 4.4 LLM calls per task.

**Right: real output from the web app's "Run Program" tab**
The quick test runs a program exactly the way the evaluator did: headless, with no keyboard input, and a 45-second limit.
1. **MAS, `mas_srdd_crea_01_r1` (Color Palette Picker): PASS.** The program started, asked for an image path, got no input (as in the evaluator), printed "Exiting." and finished with exit code 0, a clean run.
2. **ChatDev, `cd_srdd_crea_01_r1` (same task): FAIL.** It crashed straight away with `NameError: name 'main' is not defined` and exit code 1. The cause: ChatDev's `main.py` contains only the text `main.py` (the file name instead of code), and Python reads that as an undefined variable. Its other file also has a syntax error.

**How to explain the slide in the viva:**
"On the left is the actual stop rule from our Reflection agent. It ends the improvement loop when the code is clean, when improvement stalls, or after 3 rounds, so the cost stays bounded. On the right is real output from our web app's Run Program tab for the same task: MAS's program runs cleanly, while ChatDev's crashes on line 1 because its main file contains only its own file name. That's a typical example of why ChatDev ran in only 2 of 20 tasks."

---

## Q11. What are the commands to run this project?

Run these in PowerShell from the project folder (`Final Year Project`).

**1. One-time setup**
- Install the Python package with its development extras: `pip install -e ".[dev]"`
- Create your settings file: `Copy-Item .env.example .env`, then set `PROVIDER_API_KEY` (the Gemini key), `PROVIDER_BASE_URL` (the Gemini URL from the example) and `BENCH_MODEL=gemini-3.5-flash-lite`. Never share or commit `.env`.
- Install the web app's packages: `cd frontend; npm install; cd ..`
- Set up ChatDev (clone, pin to the fixed commit, apply our patch; only needed for the comparison): `python scripts/setup_chatdev.py`

**2. Run the web app (best for a demo)**
- Terminal 1, the backend API: `python -m uvicorn mas.api.main:app --port 8000`
- Terminal 2, the frontend: `cd frontend; npm run dev`
- Open http://localhost:3000. Use Generate a Project to build one, and Run Details → Run Program to test-run the result.

**3. Run MAS from the command line**
- Offline test, no API calls (built-in sample answer): `python mas_cli.py run --task "Build a calculator with add, subtract, multiply and divide" --model fake`
- Live run with Gemini (uses a few of the 450 daily requests): `python mas_cli.py run --task "Build a command-line expense tracker that saves expenses to SQLite" --model gemini-3.5-flash-lite`
- Always pass `--model`: the CLI's default is an old OpenRouter model.
- Inspect a run: `python mas_cli.py results <run_id>`; `status <run_id>` and `logs <run_id>` work the same way.

**4. The benchmark (MAS vs ChatDev vs single agent)**
- Offline check of the environment (no model calls): `python -m eval.runner --preflight`
- A small live test, the first task with all three systems: `python -m eval.runner --smoke --live --systems mas,chatdev,single --model gemini-3.5-flash-lite --tasks-file eval/tasks_v2.json`
- The full 20-task benchmark, the exact command we used. It stops cleanly at the daily limit; run it again the next day to continue:
  `python -m eval.runner --benchmark --live --systems mas,chatdev,single --model gemini-3.5-flash-lite --tasks-file eval/tasks_v2.json --tasks 20 --repeats 1 --require-embeddings --resume --stop-at-budget`

**5. Reports and dashboard (no model calls)**
- Rebuild the report tables and figures: `python scripts/make_report.py --results results.csv --manifest eval/benchmark_manifest.json --output-dir reports`
- Rebuild the offline dashboard: `python scripts/make_dashboard.py`, then open it with `start reports\dashboard.html`

**6. Tests (offline, 375 tests):** `python -m pytest tests/ -q`

**The short answer for the viva:** "Start the backend with uvicorn and the frontend with `npm run dev`, then use the web app. The benchmark is one command, `python -m eval.runner --benchmark …`, which resumes across days. Reports come from `make_report.py` and `make_dashboard.py`, and `pytest` runs the 375 offline tests."

---

## Q12. What is the database, and where are we storing data?

**Short answer:** MAS uses SQLite, a single-file database, through SQLAlchemy. The file is `mas.db` in the project root folder. Generated code isn't stored in the database: it's saved as ordinary files in workspace folders, and the database records where each run's folder is.

**The database**
- **Engine:** SQLite. No server to install, one file, enough for a single-user research tool.
- **Access layer:** SQLAlchemy 2 (models in `mas/db/models.py`, connection in `mas/db/session.py`).
- **Location:** `mas.db` in the project folder (about 0.9 MB).
- **Configuration:** the `DATABASE_URL` setting; default `sqlite:///./mas.db`.
- **Alternative:** `docker-compose.yml` can run it on PostgreSQL 15 by changing only `DATABASE_URL`; the code stays the same.
- **Backup:** `archive/mas_full_backup_2026-11-23.db`, the full database from before the cleanup, kept locally and git-ignored.

**The 9 tables, and what's in them now**

| Table | What it stores | Rows |
|---|---|---|
| `runs` | One row per run: system, model, status, tokens, timings, failure reason, code-folder path | 65 (the 60 official runs, plus 5 from 24 Nov: 4 failed live attempts and 1 offline test) |
| `agent_events` | The step-by-step log: which agent did what and when (shown in Run Details) | 455 |
| `model_calls` | Every LLM call: agent, provider-reported input and output tokens, latency, actual model, request ID | 410 |
| `metrics` | Scores per run: Completeness, Executability, Consistency, Quality, plus internal scores | 567 |
| `artifacts` | Each agent's typed output: TaskPlan, Architecture, CodePatch, TestReport, ReviewReport | 112 |
| `tasks` | The 20 benchmark tasks | 20 |
| `evaluations` | Benchmark batches | 4 |
| `checkpoints`, `config_snapshots` | Reserved; checkpoints are actually saved as files | 0 |

**What's stored outside the database (as files)**

| What | Where |
|---|---|
| Generated code of benchmark runs | `eval/workspaces/<run_id>/` (60 official folders) |
| Generated code from the web app or CLI | `workspace/<run_id>/` |
| Checkpoints (snapshots for rollback and the best round) | A `.mas_snapshots/` folder inside each run's code folder |
| Official results table | `results.csv`: every attempt, the official flag, all metrics |
| Benchmark manifest | `eval/benchmark_manifest.json` |
| Daily request ledger | `eval/outbound_transmission_ledger.json`: request counts per quota day, file-locked so parallel processes can't overcount |
| Reports and dashboard | `reports/` |
| Settings and API key | `config.yaml` and `.env` (the key stays only in `.env`, which is git-ignored) |

**If the reviewer asks "why SQLite?":** "It's one file with no server, so anyone can run the project. It's enough for one user, and because we use SQLAlchemy, switching to PostgreSQL is a one-line config change. The Docker setup already does that."

---

## Q13. Why does MAS have more agents than iCoder's four?

**Short answer:** "MAS has 7 roles, but only 4 of them call the LLM: Manager, Architect, Developer and Reviewer. That's the same number of AI agents as iCoder. The other 3 (Router, Tester, Reflection) are plain code. We split them out so that the checking and decision-making is objective, free, and can't hallucinate."

**How they line up:**

| iCoder agent | MAS roles that cover it | LLM? |
|---|---|---|
| RABot (requirements, complexity, Sprints) | Manager (TaskPlan) + Complexity Router (rule-based score) | Manager yes; Router no |
| UMLBot (design + reverse validation) | Architect (design) + AST conformance check | Architect yes; check no |
| DevBot (code generation) | Developer | yes |
| ReviewBot (dependency graph, review, tests) | Reviewer + Tester + AST analysis | Reviewer yes; Tester no |
| iCoder's loop control (D_i, T_i) | Reflection (score S_t, stop rules) | no |

**Why the split helps:**
1. **One job per role.** Each piece is simpler, easier to test, and easier to explain.
2. **Cheaper.** Three roles cost 0 LLM calls, and MAS averaged 4.4 calls per task.
3. **Objective.** Running the program, scanning for empty functions and deciding when to stop are done by code, not by the model's opinion. That's our main defence against hallucinations.

---

## Q14. How is previous context passed to the current step? What is the memory?

**Short answer:** "There's no chat history. Memory is a structured shared state: a typed dictionary called `MASState`. Every agent reads the specific fields it needs and writes its output back as a validated artifact. Each LLM call gets a fresh prompt built from that state, so we control exactly what context goes in."

**Three levels of memory:**

| Level | What it is | Where |
|---|---|---|
| Working memory (within a run) | `MASState`: requirement, TaskPlan, Architecture, current code, TestReport, ReviewReport, round number, scores | `mas/core/state.py`, passed between agents by `workflow.py` |
| Snapshots (within a run) | A code snapshot per round, used for rollback and to restore the best round | `.mas_snapshots/` in the run folder (`checkpoints.py`) |
| Permanent record (all runs) | Every artifact, agent step and LLM call | `mas.db` (artifacts, agent_events, model_calls) |

**What each agent receives from earlier steps:**
- **Architect:** the requirement and the Manager's TaskPlan.
- **Developer, round 1:** the requirement, acceptance criteria, planned files and the class diagram (up to 2,000 characters).
- **Developer, rounds 2–3:** "promoted" context from the previous round:
  - the current code, but only the changed files plus the files that depend on them, chosen by the ContextSlicer using the AST import graph (the "impact set");
  - the latest 5 review findings;
  - the latest 5 test diagnostics;
  - the sandbox error, cut to 300 characters.
- **Reviewer:** the code, the acceptance criteria, and the real evidence (exit code, test results, Ruff, Bandit, import cycles, design conformance).

**Between runs:** each run starts fresh. The exception is a change request, which loads the previous project, works out which files the change affects, and updates only those.

---

## Q15. Doesn't passing that context increase the input size?

**Short answer:** "Yes, somewhat, from round 2 onwards, because the Developer needs to see the current code to repair it. But it's bounded by design, and we measured it: the first Developer call averages 767 input tokens, later calls average 3,280 (at most 6,155). A whole MAS run averages about 8,900 input tokens, while ChatDev uses about 47,000 tokens per task."

**What keeps the context small:**

| Control | Effect |
|---|---|
| No chat history | Each call is rebuilt from state, so old messages never pile up |
| Context slicing | Only changed files plus their AST dependents are sent, not the whole project |
| Caps | Latest 5 review findings, latest 5 test diagnostics, class diagram up to 2,000 characters, sandbox error up to 300 characters, Tester output up to 40 lines or 1,500 characters |
| Early stop | The loop ends as soon as the code is clean: 6 of 20 runs finished in round 1 (3 calls), and 15 of 20 used 4 calls or fewer |
| At most 3 rounds | A hard ceiling, keeping the best round |
| Reviewer skipped | Once a review has passed and the code is still clean, it isn't run again |
| Token budget | Each run has a 100,000-token budget; each call reserves its tokens first and is refused if they don't fit. Output is capped at 8,192 tokens per call |

**The honest trade-off:** sending the current code makes later prompts larger. Without it, though, the Developer would rewrite every file from scratch each round, which costs more output tokens and risks breaking code that already worked. That change is recorded as DEC-045 (P1).

(Measured on the 20 official MAS runs, from the `model_calls` table in `mas.db`.)

---

## Q16. How are the automated tests done, and how and where are the metrics' tests calculated?

**Short answer:** "We test at two levels. The project itself has 375 offline pytest tests, with the network blocked and a fake model. The generated projects are tested by a frozen neutral evaluator that actually runs each program in a sandbox, and computes Completeness by AST, Consistency by embeddings, and Quality as their product, identically for every system. MAS's own Tester only steers MAS's loop; it never counts in the comparison."

### 1. The automated test suite (`tests/`, 375 tests in 53 files)
Run with `python -m pytest tests/ -q` (result on 25 Nov: 375 passed in about 3 minutes). `tests/conftest.py` makes every test isolated and offline:
- **No network calls:** every connection to anything outside this computer is blocked by patching Python's `socket.connect` (the project's rule 7).
- **Fake model:** `FakeLLMProvider` returns fixed answers, so the tests cost nothing and give the same result every time.
- **No real secrets:** API keys and the model ID are blanked, so the real `.env` is never used.
- **Separate data:** a throwaway `test_mas.db` and test request ledger are created, then deleted, so real data isn't touched.

**What they cover:** agents (router, schemas, Tester, conformance, adaptive stopping, loop fixes); the evaluator (metric functions, the run-check protocol, UTF-8 handling); ChatDev (adapter, parser, timeouts); quota and tokens (governor, token logger, budget stop); results (statistics, reports, dashboard); the API (`/config`, quick-test, open); fault injection and recovery; and the full pipeline end to end with the fake model.

**Examples:** "a crash whose error text contains an emoji must still count as a crash"; "`/config` never returns the API key"; "open-program refuses requests from other computers".

### 2. Testing the generated projects: two separate kinds

**(a) MAS's own Tester, inside the loop** (`mas/agents/tester.py`, MAS only):
- It runs the program, checks `--help`, scans for empty functions, and runs the Developer's own `test_*.py` files.
- The resulting pass rate makes up 30% of the round score S_t and helps decide stop or continue.
- It's used only for MAS's internal decisions, never for the comparison.

**(b) The frozen neutral evaluator, after each run** (`eval/neutral_evaluator.py`, the same for all three systems):

| Metric | Function (file) | How it's calculated | Part of Quality? |
|---|---|---|---|
| Completeness | `calculate_completeness` (`eval/scorers/icoder_metrics.py`) | AST scan: 1 − empty functions ÷ all functions | Yes |
| Executability | `calculate_executability` (v1.3) → `smoke_run` (`mas/analysis/sandbox.py`) | Runs `main.py` headless in the sandbox, 45 s limit; `--help` fallback for command-line tools; 1 or 0 | Yes |
| Consistency | `calculate_consistency` (`icoder_metrics.py`) | Cosine similarity of MiniLM embeddings: requirement vs the first 2,000 characters of code | Yes |
| Quality | `calculate_quality` | C × E × S | — |
| Shared test | `eval/scorers/shared_test.py` | Level 1 smoke run + Level 2 fixed black-box checks from `eval/checks/level2_checks.json` (only 3 tasks have them: `srdd_educ_01` and 2 examples). Score = 0.5 × L1 + 0.5 × L2, or just L1. It never uses tests the systems wrote themselves | No, reported separately (MAS 0.975, single agent 0.80, ChatDev 0.105) |
| Ruff · Bandit · Radon | `mas/analysis/quality_tools.py` | Lint errors · high-severity security issues · maintainability index | No, reported separately |

**Where the numbers go:** `eval/runner.py` has each system build its project in `eval/workspaces/<run_id>/`. Then `NeutralEvaluator.evaluate_project(folder, the identical requirement text)` writes the scores to the `metrics` table in `mas.db` (scope "neutral") and to `eval/benchmark_manifest.json`. From there they go to `results.csv` (`eval/reports.py`), then to `eval/stats.py` (bootstrap CI, Wilcoxon), and finally to `reports/` and the web app.

---
