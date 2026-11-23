"""DEC-051: /config exposes the pinned model and quota for the UI, never the API key."""

import asyncio

import httpx

from mas.api.main import app


def _get_config():
    async def _call():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            return await client.get("/config")

    return asyncio.run(_call())


def test_config_reports_model_and_never_the_key(monkeypatch):
    secret = "test-secret-value-1234567890"
    monkeypatch.setenv("PROVIDER_API_KEY", secret)
    monkeypatch.setenv("BENCH_MODEL", "example-model-id")
    monkeypatch.setenv("PROVIDER_BASE_URL", "https://provider.example/v1/")
    resp = _get_config()
    assert resp.status_code == 200
    body = resp.json()
    assert body["bench_model"] == "example-model-id"
    assert body["provider_host"] == "provider.example"
    assert body["api_key_configured"] is True
    assert secret not in resp.text


def test_config_without_model_or_key(monkeypatch):
    monkeypatch.delenv("BENCH_MODEL", raising=False)
    monkeypatch.delenv("PROVIDER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    body = _get_config().json()
    assert body["bench_model"] is None
    assert body["api_key_configured"] is False
