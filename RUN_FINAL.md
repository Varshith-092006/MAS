1. pip install -e .
2. In .env set PROVIDER_BASE_URL, PROVIDER_API_KEY and BENCH_MODEL (one exact model ID).
3. python -m eval.runner --preflight
4. python -m eval.runner --estimate --tasks-file eval/tasks_v2.json
5. Each day: python -m eval.runner --benchmark --systems mas,chatdev --tasks-file
   eval/tasks_v2.json --repeats 1 --require-embeddings --live --resume --stop-at-budget
6. When all 20 tasks are done: ablations A1 to A4 on MAS only (use --resume --stop-at-budget)
7. python scripts/make_report.py
