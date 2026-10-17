"""Unit tests for FastAPI endpoints."""

import asyncio
import httpx
import pytest

from mas.api.main import app
from mas.db.session import init_db


@pytest.fixture(autouse=True)
def init_test_db():
    init_db()


def test_health_endpoint():
    async def _test():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"

    asyncio.run(_test())


def test_create_and_get_run_api():
    async def _test():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            req_body = {
                "requirement": "Build a simple math module",
                "task_id": "test_api_task",
                "model": "fake",
                "workspace_base": "./workspace/test_api",
            }
            post_resp = await client.post("/runs", json=req_body)
            assert post_resp.status_code == 200
            data = post_resp.json()
            assert "run_id" in data
            run_id = data["run_id"]
            assert data["status"] in ("COMPLETED", "COMPLETED_QUALITY_GATE")

            # GET /runs/{id}
            get_resp = await client.get(f"/runs/{run_id}")
            assert get_resp.status_code == 200
            run_data = get_resp.json()
            assert run_data["run_id"] == run_id

            # GET /runs/{id}/events
            events_resp = await client.get(f"/runs/{run_id}/events")
            assert events_resp.status_code == 200
            events = events_resp.json()
            assert len(events) > 0

            # GET /runs/{id}/results
            results_resp = await client.get(f"/runs/{run_id}/results")
            assert results_resp.status_code == 200

            # GET /runs/{id}/artifacts
            artifacts_resp = await client.get(f"/runs/{run_id}/artifacts")
            assert artifacts_resp.status_code == 200
            assert isinstance(artifacts_resp.json(), list)

            # GET /runs/{id}/workspace
            workspace_resp = await client.get(f"/runs/{run_id}/workspace")
            assert workspace_resp.status_code == 200
            assert "files" in workspace_resp.json()

    asyncio.run(_test())

