"""DEC-043: fixes found by the first live Gemini smoke test.

1. Gemini's OpenAI-compatible endpoint rejects 'seed' (HTTP 400): omit it there, for all systems.
2. Provider request rejections / zero-output runs are INFRA_ERROR (retryable), never Quality 0.
3. Official rows are chosen per model, so old-model runs cannot block the pinned model's slot.
"""

from unittest.mock import patch

import httpx

import eval.runner as runner_mod
from eval.runner import classify_failure, update_benchmark_manifest
from mas.core.llm import OpenRouterProvider, provider_supports_seed

GEMINI = "https://generativelanguage.googleapis.com/v1beta/openai/"


def test_provider_supports_seed():
    assert provider_supports_seed(GEMINI) is False
    assert provider_supports_seed("https://openrouter.ai/api/v1") is True
    assert provider_supports_seed("http://127.0.0.1:8089/v1") is True


def _capture(base_url):
    provider = OpenRouterProvider(api_key="test-key-not-real", base_url=base_url, default_model="m-1")
    captured = {}

    def fake_post(url, json=None, headers=None):
        captured.update(json or {})
        return httpx.Response(
            200,
            json={"id": "x", "model": "m-1", "choices": [{"message": {"content": "ok"}}],
                  "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}},
            request=httpx.Request("POST", url),
        )

    with patch("httpx.Client.post", side_effect=fake_post):
        provider.generate([{"role": "user", "content": "hi"}], model="m-1")
    return captured


def test_direct_client_omits_seed_for_gemini_only():
    gem = _capture(GEMINI)
    assert "seed" not in gem and gem["temperature"] == 0.0
    assert _capture("https://openrouter.ai/api/v1")["seed"] == 42


def test_proxy_omits_seed_for_gemini(monkeypatch):
    """ChatDev goes through the proxy; it must send the same payload shape as MAS."""
    import mas.core.proxy as proxy_mod

    import mas.core.governor as governor_mod

    monkeypatch.setenv("PROVIDER_BASE_URL", GEMINI)
    sent = {}

    class FakeGovernedClient:
        """Stands in for the real HTTP client: records the payload, never touches the network."""
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json=None, headers=None):
            sent.update(json or {})
            return httpx.Response(
                200,
                json={"id": "x", "model": "m-1", "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                      "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr(governor_mod, "GovernedHTTPClient", FakeGovernedClient)
    import asyncio

    async def call():
        transport = httpx.ASGITransport(app=proxy_mod.proxy_app)  # in-process, no sockets
        async with httpx.AsyncClient(transport=transport, base_url="http://proxy.test") as client:
            await client.post(
                "/v1/chat/completions",
                json={"model": "m-1", "messages": [{"role": "user", "content": "hi"}], "seed": 7},
                headers={"Authorization": "Bearer test-key-not-real"},
            )

    asyncio.run(call())
    assert sent, "proxy did not forward the request"
    assert "seed" not in sent and sent["temperature"] == 0.0


def test_provider_rejections_are_infra_errors():
    assert classify_failure(error_msg="OPENROUTER_ERROR_400: Unknown name \"seed\"") == "INFRA_ERROR"
    assert classify_failure(error_msg="OpenRouter Request Error (400) on model") == "INFRA_ERROR"
    assert classify_failure(error_msg="OpenAI / Proxy error 400: INVALID_ARGUMENT") == "INFRA_ERROR"
    assert classify_failure(error_msg="Request Error (401) unauthenticated") == "INFRA_ERROR"
    assert classify_failure(error_msg="missing required artifact: main.py") == "QUALITY_FAILURE"
    assert classify_failure(error_msg="budget ceiling of 4000 tokens") == "QUALITY_FAILURE"


def _rec(run_id, model, status="COMPLETED", tokens=100, calls=3, q=0.5, live=True):
    return {"run_id": run_id, "task_id": "t1", "system": "mas", "repeat_no": 1, "ablation": "A0",
            "model": model, "status": status, "tokens": tokens, "llm_calls": calls, "quality": q,
            "execution_mode": "LIVE_API" if status == "COMPLETED" else status, "is_live_benchmark": live,
            "timestamp_utc": "2026-11-22T00:00:00Z"}


def test_zero_output_live_failure_is_not_official(tmp_path):
    m = update_benchmark_manifest(
        [_rec("mas_t1_r1", "new-model", status="FAILED", tokens=0, calls=0, q=None)],
        manifest_path=str(tmp_path / "m.json"), canonical_task_ids={"t1"},
    )
    r = m["runs"][0]
    assert r["failure_classification"] == "INFRA_ERROR" and r["official"] is False
    assert r["quality"] is None  # never turned into Quality 0


def test_official_slot_is_scoped_by_model(tmp_path):
    m = update_benchmark_manifest(
        [_rec("mas_t1_r1", "old-model"), _rec("mas_t1_r1_attempt2", "new-model")],
        manifest_path=str(tmp_path / "m.json"), canonical_task_ids={"t1"},
    )
    official = {r["model"]: r["official"] for r in m["runs"]}
    assert official == {"old-model": True, "new-model": True}


def test_resume_only_skips_rows_of_the_same_model(tmp_path, monkeypatch):
    path = tmp_path / "m.json"
    update_benchmark_manifest([_rec("mas_t1_r1", "old-model")], manifest_path=str(path), canonical_task_ids={"t1"})
    monkeypatch.setattr(runner_mod, "MANIFEST_FILE", str(path))
    monkeypatch.setattr(runner_mod, "generate_stats_markdown_report", lambda *a, **k: "")
    ran = []

    class Stop(Exception):
        pass

    def fake_workflow(*a, **k):
        ran.append(1)
        raise Stop()

    monkeypatch.setattr(runner_mod, "MASWorkflow", fake_workflow)
    r = runner_mod.EvaluationRunner(results_path=str(tmp_path / "r.csv"))
    tasks = tmp_path / "tasks.json"
    tasks.write_text('[{"task_id": "t1", "name": "T", "description": "d", "category": "Work"}]')
    # Simulated run of a different model: the old-model official row must NOT cause a skip.
    r.run_benchmark(task_count=1, model="fake", use_fake=True, systems=["mas"], resume=True, tasks_file=str(tasks))
    assert ran == [1]
