# iCoder paper → MAS implementation map

Paper: You et al., *iCoder: A multi agent software development platform*, Information and
Software Technology 198 (2026) 108224. Status words: **Done**, **Partial** (simplified or
weaker than the paper), **Missing**, **Extra** (MAS-only improvement).

## Agents and workflow (paper Sec. 3)

| Paper component | MAS component | Status | Notes |
|---|---|---|---|
| RABot: requirement decomposition, user stories, acceptance criteria (3.2.1) | `ManagerAgent` → `TaskPlan` (sprint goals, acceptance criteria); `ArchitectAgent` → `UserStory` | Partial | One plan per task. No multi-subsystem Product Backlog. |
| Complexity-driven decomposition (3.3.3) | `ComplexityRouter`: deterministic score, SIMPLE vs STRUCTURED | Partial / Extra | Two levels instead of 1 to 5+ subsystems. Costs 0 LLM calls; skips the Architect on simple tasks. |
| Sprint-based iterative development (3.3.2) | Iteration loop in `MASWorkflow` (up to 3) | Partial | Iterations refine the whole project. They are not separate sprints over a backlog. Multi-sprint mode would multiply requests, and the free tier allows 500 per day. |
| UMLBot forward design (3.2.2) | `ArchitectAgent` → components, class diagram text, file structure, module dependencies | Partial | Text/Mermaid class diagram only. No PlantUML use-case, sequence or activity views. |
| UMLBot reverse validation, design vs code diff (3.2.2) | `mas/analysis/conformance.py` (Phase 8) | Done (deterministic) | AST rebuilds files, classes and imports, then diffs them with the design. 0 LLM calls. |
| Change impact analysis (3.2.2) | `ContextSlicer` + `ASTAnalyzer.compute_impact_set` | Done | Later iterations get only changed files plus their AST dependents (ablation A2 turns this off). |
| DevBot code generation under design constraints (3.2.3) | `DeveloperAgent` (delimiter-block output, targeted repair) | Done | Integrating a user's existing code is not implemented. |
| ReviewBot R-DCGG dependency graph (3.2.4) | `ASTAnalyzer` dependency graph and cycles | Done | Graph comes from imports, not runtime call or data flow. |
| ReviewBot multi-dimensional review (3.2.4) | `ReviewerAgent`, grounded in AST, Ruff, Bandit, sandbox, tests and conformance | Done / Extra | Evidence-grounded (ablation A3 removes the evidence). Runs once per run, skipped only after a PASS. |
| Placeholder check: no TODO or `pass` (3.2.4) | Placeholder scan in `TesterAgent` + `DeterministicRepairChecker` | Done | Feeds the repair loop and the Reflection completeness signal. |
| Automated testing module (3.2.4) | `TesterAgent`, deterministic (Phase 8) | Done | Real smoke run, `--help` check, placeholder scan, developer tests. 0 LLM calls. |
| Iterative control S_i = (C_i, R_i, D_i, T_i) (3.3.4) | `ReflectionAgent` + `AdaptiveStopper` | Done / Extra | Weighted adaptive score with an epsilon/patience stop. The paper loops until tests pass. |
| Human intervention interface (3.1) | `mas/core/change_request.py`, API and frontend | Partial | Change requests between runs. No mid-sprint approval. |

## Evaluation (paper Sec. 4)

| Paper | MAS | Status |
|---|---|---|
| Completeness = 1 − unimplemented/total functions | `eval/scorers/icoder_metrics.py::calculate_completeness` (frozen) | Done. Computed per project, then averaged (the paper pools over all projects). |
| Executability = share of projects that run | `calculate_executability` v1.3 smoke protocol (frozen) | Done |
| Consistency = cosine(requirement, code) embeddings | all-MiniLM-L6-v2, first 2,000 code chars, clipped to [0, 1] | Done. Paper min-max normalises; we clip. Lexical fallback is labelled. |
| Quality = C × E × S | `calculate_quality`, averaged over projects | Done |
| Baseline ChatDev | Pinned ChatDev submodule, same proxy, model, temperature and seed | Done |
| Extra baseline | `--systems single`: one-call single agent | Extra |
| Token and time overhead (Tables 3–4) | Provider-reported tokens per call (`model_calls`), per-agent breakdown, wall clock, LLM calls | Done / Extra |
| GPT-3.5 / GPT-4o, 100 / 20 tasks | One pinned Gemini Flash Lite model, 20 SRDD tasks (4 per category) | Different by design (free tier). Published numbers are indicative only. |
| Single run per task | Bootstrap CIs, paired Wilcoxon, Cohen's d, ablations A0–A4 | Extra |

## Honest gaps

1. No official benchmark numbers yet. They need a Gemini API key and the maintainer's go-ahead (`RUN_FINAL.md`).
2. Single sprint per run; no multi-subsystem backlog.
3. Text class diagram only; no PlantUML multi-view design.
4. All historical live runs in `mas.db` used OpenRouter free models and older MAS versions. They are shown only as EXPLORATORY data in the dashboard.
