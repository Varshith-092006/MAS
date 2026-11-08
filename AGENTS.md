# MAS project: rules for AI agents working in this repo

## What this project is
MAS is a multi-agent software engineering system (Manager, Router, Architect, Developer,
Tester, Reviewer, Reflection agents) that turns a natural-language requirement into a
working Python project. It is a final year project. We compare MAS against ChatDev on the
SRDD dataset (data_attribute_format.csv, 1200 tasks) using the metrics from the iCoder paper
(You et al., Information and Software Technology 198 (2026) 108224):
  Completeness = 1 - (unimplemented functions / total functions)
  Executability = share of projects that run without error
  Consistency = cosine similarity of requirement text and code (sentence embeddings)
  Quality = Completeness x Executability x Consistency, averaged over projects
Published numbers (different model and tasks, so only indicative, never "beaten locally"):
  GPT-3.5 Turbo (100 tasks): ChatDev Q=0.5906, iCoder Q=0.6902
  GPT-4o (20 tasks): ChatDev Q=0.6550, iCoder Q=0.7924
  Token use per task: ChatDev ~22k-30k, iCoder ~105k (GPT-4o) to ~411k (GPT-3.5).
These live in eval/published_references.py. Treat that file as the source of truth.

## Hard rules (never break these)
1. NEVER invent, estimate or hardcode benchmark results. If a table has no data, print "NOT RUN".
2. NEVER put task-specific content into agent prompts (no domain words from any single SRDD
   task). Prompts must work for any requirement.
3. NEVER try to inflate the Consistency metric (do not copy the requirement text into code
   comments or docstrings to raise similarity). Improve real code quality only.
4. NEVER change the frozen evaluator (eval/neutral_evaluator.py, eval/checks/*) or the
   benchmark hashes unless a task says so, and then record it in DECISIONS.md.
5. Both systems (MAS and ChatDev) must get identical requirement text, model, temperature,
   seed and token measurement.
6. Simulated or FakeLLM results must always be labeled SIMULATION_ONLY and must never appear
   in any report table.
7. Tests must not make network calls. Use FakeLLMProvider. You cannot run live benchmarks:
   there is no API key here.
8. Do not edit HLD/LLD/PDF documents or the frontend unless a task says so.

## Commands
  pip install -e ".[dev]"      (add dev extras if missing)
  pytest tests/ -q             (must stay green: 201 tests today; update tests only when
                                 behaviour was changed on purpose, and say so in the PR)

## Definition of done for every task
- All tests pass; new behaviour has new tests.
- A short note in DECISIONS.md: what changed and why.
- The PR description lists every file changed and anything you could not verify.
## Free-tier constraints (this project has no budget)
- All benchmark runs use ONE pinned free model on ONE provider, identical for MAS and ChatDev.
  Never use auto-routers such as "openrouter/free", never allow fallback models.
  Abort the run if the served model name differs from the requested one.
- The real bottleneck is requests per day (and tokens per day on some providers), not dollars.
  Reducing LLM calls per run is therefore a top priority for every change.
- The benchmark takes several days. It must be resumable: stop cleanly when the daily
  budget is used, then continue the next day without redoing finished work.
- Never send the same request twice just to retry quality; only retry infrastructure errors.
