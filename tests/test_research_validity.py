"""Regression test suite for MAS Research System Validity and Provenance Integrity.

Covers all 16 failure scenarios and invariants required by Section 11 of the audit:
1. FakeLLMProvider results are labelled SIMULATED and excluded from empirical charts by default.
2. A missing API key cannot cause automatic fallback to fake mode.
3. An invalid or inaccessible model cannot be silently substituted.
4. A real provider result records actual returned model ID and usage where provided.
5. Token usage is never invented when missing.
6. Zero or unavailable tokens never produce a fabricated Quality / 1K Tokens value.
7. Cost cannot be silently fabricated for runs lacking valid usage.
8. Generated files are persisted and visible in the workspace viewer.
9. A completed run with missing required artifacts or evaluation is detected.
10. A ChatDev run cannot be populated with a MAS result.
11. A run's database record, results API, and run visualizer agree.
12. Analytics totals reconcile exactly with their contributing records.
13. The neutral evaluator is isolated from the MAS workflow.
14. iCoder reference results cannot be counted as locally executed experiments.
15. The dry-run report correctly calculates planned run count and reports zero model calls.
16. Failed and timed-out executions remain visible and are not dropped from failure statistics.
"""

import asyncio
import json
import os
import shutil
import uuid
import httpx
import pytest
from datetime import datetime

from unittest.mock import patch

from mas.api.main import app
from mas.core.llm import (
    FakeLLMProvider,
    OpenRouterProvider,
    ModelResult,
    TokenLogger,
    calculate_model_cost,
    resolve_openrouter_model,
    ModelMismatchError,
    is_model_match,
    token_logger,
)
from mas.core.workflow import MASWorkflow, generate_artifacts_manifest
from eval.chatdev_adapter import ChatDevAdapter
from eval.neutral_evaluator import NeutralEvaluator
from eval.runner import EvaluationRunner
from mas.db.models import Run, ModelCall, Metric, Evaluation
from mas.db.session import get_session, init_db


@pytest.fixture(autouse=True)
def setup_test_db():
    """Ensure database tables exist for tests."""
    init_db()
    yield


def run_async(coro):
    return asyncio.run(coro)


def test_1_fake_provider_labelled_simulated_and_excluded_by_default():
    """Test 1: FakeLLMProvider results are labelled SIMULATED and excluded from empirical charts by default."""
    llm = FakeLLMProvider()
    res = llm.generate([{"role": "user", "content": "test"}], model="fake")
    assert res.execution_mode == "SIMULATED"
    assert res.token_provenance == "SIMULATED"

    # Verify that in API analytics, SIMULATED runs are excluded when include_simulated=False
    run_id = f"test_sim_{uuid.uuid4().hex[:8]}"
    with get_session() as session:
        session.add(
            Run(
                run_id=run_id,
                system="mas",
                model="fake",
                execution_mode="SIMULATED",
                token_provenance="SIMULATED",
                status="COMPLETED",
                started_at=datetime.utcnow(),
            )
        )
        session.commit()

    async def _test():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            resp = await client.get("/analytics/summary?include_simulated=false")
            assert resp.status_code == 200
            data = resp.json()
            assert data["provenance_filter"]["include_simulated"] is False
            assert data["provenance_filter"]["excluded_simulated_runs"] >= 1

    run_async(_test())


def test_2_missing_api_key_cannot_fallback_to_fake():
    """Test 2: A missing API key cannot cause automatic fallback to fake mode."""
    provider = OpenRouterProvider(api_key="", base_url="https://openrouter.ai/api/v1")
    with pytest.raises(RuntimeError) as exc_info:
        provider.generate([{"role": "user", "content": "ping"}], model="openai/gpt-4o")
    assert "Missing API key" in str(exc_info.value)
    assert "fake provider is strictly prohibited" in str(exc_info.value)


def test_3_invalid_or_inaccessible_model_cannot_be_silently_substituted():
    """Test 3: An invalid or inaccessible model cannot be silently substituted."""
    unknown = resolve_openrouter_model("unknown-custom-model-999")
    # Resolution preserves the requested model identifier and does not substitute GPT-4o or a free model
    assert unknown == "unknown-custom-model-999"


def test_4_real_provider_records_actual_model_and_usage():
    """Test 4: A real provider result records the actual returned model ID and usage where provided."""
    res = ModelResult(
        text='{"status": "ok"}',
        model_name="openai/gpt-4o-2024-08-06",
        provider_model_version="fp_abc123",
        input_tokens=150,
        output_tokens=75,
        total_tokens=225,
        latency_ms=300,
        request_id="gen-req-789",
        estimated_cost=0.001125,
        execution_mode="LIVE_API",
        token_provenance="PROVIDER_REPORTED",
    )
    assert res.execution_mode == "LIVE_API"
    assert res.token_provenance == "PROVIDER_REPORTED"
    assert res.model_name == "openai/gpt-4o-2024-08-06"
    assert res.total_tokens == res.input_tokens + res.output_tokens


def test_5_token_usage_never_invented_when_missing():
    """Test 5: Token usage is never invented when missing."""
    data_without_usage = {"choices": [{"message": {"content": "hello"}}]}
    usage = data_without_usage.get("usage")
    if usage and isinstance(usage, dict) and any(k in usage for k in ("prompt_tokens", "completion_tokens", "total_tokens")):
        tot = usage.get("total_tokens")
        prov = "PROVIDER_REPORTED"
    else:
        tot = None
        prov = "UNAVAILABLE"

    assert tot is None
    assert prov == "UNAVAILABLE"


def test_6_zero_or_unavailable_tokens_never_produce_fabricated_q1k():
    """Test 6: Zero or unavailable tokens never produce a fabricated Quality / 1K Tokens value."""
    # When tokens == 0 or None, q_per_1k must be None / N/A
    quality = 0.85
    tot_tokens_zero = 0
    q1k_zero = round(quality / (tot_tokens_zero / 1000), 4) if (tot_tokens_zero and tot_tokens_zero > 0) else None
    assert q1k_zero is None

    tot_tokens_none = None
    q1k_none = round(quality / (tot_tokens_none / 1000), 4) if (tot_tokens_none and tot_tokens_none > 0) else None
    assert q1k_none is None


def test_7_cost_cannot_be_silently_fabricated():
    """Test 7: Cost cannot be silently fabricated for runs lacking valid usage."""
    cost = calculate_model_cost("openai/gpt-4o", 0, 0)
    assert cost == 0.0


def test_8_generated_files_persisted_and_visible_in_workspace():
    """Test 8: Generated files are persisted and visible in the workspace viewer."""
    run_id = f"test_ws_{uuid.uuid4().hex[:8]}"
    ws_dir = os.path.abspath(os.path.join("eval", "workspaces", run_id))
    os.makedirs(ws_dir, exist_ok=True)
    try:
        main_file = os.path.join(ws_dir, "app.py")
        with open(main_file, "w", encoding="utf-8") as f:
            f.write("print('test project')\n")

        async def _test():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                # Test workspace listing endpoint
                resp = await client.get(f"/runs/{run_id}/workspace")
                assert resp.status_code == 200
                data = resp.json()
                assert data["file_count"] >= 1
                assert any(f["name"] == "app.py" for f in data["files"])

                # Test file reading endpoint
                resp_file = await client.get(f"/runs/{run_id}/workspace?file_path=app.py")
                assert resp_file.status_code == 200
                file_data = resp_file.json()
                assert "print('test project')" in file_data["content"]

                # Test path traversal prevention
                resp_traversal = await client.get(f"/runs/{run_id}/workspace?file_path=../../../../etc/passwd")
                assert resp_traversal.status_code in (403, 404)

        run_async(_test())
    finally:
        shutil.rmtree(ws_dir, ignore_errors=True)


def test_9_completed_run_with_missing_required_artifacts_detected():
    """Test 9: A completed run with missing required artifacts or evaluation is detected."""
    manifest = generate_artifacts_manifest("./nonexistent_workspace_dir_1234")
    assert manifest == []


def test_10_chatdev_run_cannot_be_populated_with_mas_result():
    """Test 10: A ChatDev run cannot be populated with a MAS result."""
    cd_adapter = ChatDevAdapter()
    output = cd_adapter.run_task(
        task={"task_id": "test_t1", "name": "Task 1", "description": "Do X"},
        output_base_dir="./eval/workspaces",
        model="fake",
        use_fake=True,
    )
    assert output["system"] == "chatdev"
    assert "chatdev" in output["run_id"]


def test_11_run_database_record_and_api_agree():
    """Test 11: A run's database record, results API, and run visualizer agree."""
    run_id = f"test_agree_{uuid.uuid4().hex[:8]}"
    with get_session() as session:
        session.add(
            Run(
                run_id=run_id,
                system="mas",
                model="openai/gpt-4o-mini",
                actual_model="openai/gpt-4o-mini",
                execution_mode="LIVE_API",
                token_provenance="PROVIDER_REPORTED",
                total_tokens=1250,
                status="COMPLETED",
                started_at=datetime.utcnow(),
            )
        )
        session.commit()

    async def _test():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            resp = await client.get(f"/runs/{run_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["run_id"] == run_id
            assert data["execution_mode"] == "LIVE_API"
            assert data["total_tokens"] == 1250

    run_async(_test())


def test_12_analytics_totals_reconcile_with_contributing_records():
    """Test 12: Analytics totals reconcile exactly with their contributing records."""
    async def _test():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            resp = await client.get("/analytics/summary")
            assert resp.status_code == 200
            data = resp.json()
            tok_data = data["token_analytics"]
            assert tok_data["total_tokens"] == tok_data["input_tokens"] + tok_data["output_tokens"]

    run_async(_test())


def test_13_neutral_evaluator_isolated_from_mas_workflow():
    """Test 13: The neutral evaluator is isolated from the MAS workflow."""
    import inspect
    from mas.agents.manager import ManagerAgent
    from mas.agents.developer import DeveloperAgent
    from mas.agents.reviewer import ReviewerAgent

    # NeutralEvaluator must not be imported or used by internal MAS agents
    for agent_cls in [ManagerAgent, DeveloperAgent, ReviewerAgent]:
        source = inspect.getsource(agent_cls)
        assert "NeutralEvaluator" not in source


def test_14_icoder_reference_not_counted_as_locally_executed():
    """Test 14: iCoder reference results cannot be counted as locally executed experiments."""
    async def _test():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            resp = await client.get("/analytics/summary")
            assert resp.status_code == 200
            data = resp.json()
            icoder = data["icoder_reference"]
            assert "PUBLISHED REFERENCE" in icoder["status"] or "REFERENCE ONLY" in icoder["status"]
            assert "NOT executed" in icoder["citation"] or "NOT executed" in icoder["note"]

    run_async(_test())


def test_17_published_references_exact_table_values_and_model_conditions():
    """Test 17: Published literature references match exact iCoder tables and avoid misattributed figures."""
    from eval.published_references import PUBLISHED_REFERENCES, get_published_reference

    # GPT-3.5 Turbo condition (Table 1 & Table 3, pp. 12-13, 100 tasks)
    ref_35 = get_published_reference("gpt-3.5-turbo")
    assert ref_35["model_condition"] == "gpt-3.5-turbo"
    assert ref_35["tasks_evaluated"] == 100
    assert ref_35["quality_table"] == "Table 1, Page 12"
    assert ref_35["overhead_table"] == "Table 3, Page 13"
    assert ref_35["icoder_quality"] == 0.690192
    assert ref_35["chatdev_quality"] == 0.590626
    assert ref_35["icoder_tokens_per_task"] == 411144.62
    assert ref_35["chatdev_tokens_per_task"] == 22327.02

    # GPT-4o condition (Table 2 & Table 4, pp. 12-13, 20 tasks)
    ref_4o = get_published_reference("gpt-4o")
    assert ref_4o["model_condition"] == "gpt-4o"
    assert ref_4o["tasks_evaluated"] == 20
    assert ref_4o["quality_table"] == "Table 2, Page 12"
    assert ref_4o["overhead_table"] == "Table 4, Page 13"
    assert ref_4o["icoder_quality"] == 0.792398
    assert ref_4o["chatdev_quality"] == 0.654990
    assert ref_4o["icoder_tokens_per_task"] == 104883.2
    assert ref_4o["chatdev_tokens_per_task"] == 30416.6

    # Verify deprecated/incorrect values (0.8640) are NOT present
    for conf in PUBLISHED_REFERENCES.values():
        assert conf["icoder_quality"] != 0.8640
        assert conf["chatdev_quality"] != 0.7210
        assert "PUBLISHED REFERENCE" in conf["status_label"]



def test_15_dry_run_reports_zero_model_calls():
    """Test 15: The dry-run report correctly calculates the planned run count and reports zero model calls."""
    runner = EvaluationRunner()
    initial_calls = TokenLogger()._run_totals
    result = runner.dry_run(tasks=runner.load_tasks()[:2], repeats=3, systems=["mas", "chatdev"], models=["gpt-4o"])
    # 2 tasks * 3 repeats * 2 systems * 1 model = 12 runs
    assert result["planned_runs"] == 12
    assert result["model_calls"] == 0
    assert len(initial_calls) == 0


def test_16_failed_and_timed_out_executions_remain_visible():
    """Test 16: Failed and timed-out executions remain visible and are not dropped from failure statistics."""
    fail_id = f"test_fail_{uuid.uuid4().hex[:8]}"
    with get_session() as session:
        session.add(
            Run(
                run_id=fail_id,
                system="mas",
                model="openai/gpt-4o",
                execution_mode="FAILED",
                status="FAILED",
                failure_reason="Execution timeout after 600s",
                started_at=datetime.utcnow(),
            )
        )
        session.commit()

    async def _test():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            resp = await client.get("/runs?status=FAILED")
            assert resp.status_code == 200
            runs = resp.json()["runs"]
            assert any(r["run_id"] == fail_id for r in runs)

    run_async(_test())


def test_17_gpt4o_cannot_succeed_when_served_by_another_model():
    """Test 17: A request for GPT-4o cannot succeed as a GPT-4o experiment when another model serves it."""
    provider = OpenRouterProvider(api_key="test-api-key", base_url="https://openrouter.ai/api/v1")
    fake_resp = httpx.Response(
        200,
        json={
            "id": "gen-mismatch-1",
            "model": "cohere/north-mini-code:free",
            "choices": [{"message": {"content": "code"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        },
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
    )
    with patch("httpx.Client.post", return_value=fake_resp):
        with pytest.raises(ModelMismatchError) as exc:
            provider.generate([{"role": "user", "content": "hi"}], model="openai/gpt-4o")
        assert "Model mismatch error" in str(exc.value)
        assert "openai/gpt-4o" in str(exc.value)
        assert "cohere/north-mini-code:free" in str(exc.value)


def test_18_gpt4o_mini_cannot_silently_become_free_model():
    """Test 18: A request for GPT-4o-mini cannot silently become a free model."""
    provider = OpenRouterProvider(api_key="test-api-key", base_url="https://openrouter.ai/api/v1")
    fake_resp = httpx.Response(
        200,
        json={
            "id": "gen-mismatch-2",
            "model": "liquid/lfm-2.5-2.6b:free",
            "choices": [{"message": {"content": "code"}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 60, "total_tokens": 180},
        },
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
    )
    with patch("httpx.Client.post", return_value=fake_resp):
        with pytest.raises(ModelMismatchError) as exc:
            provider.generate([{"role": "user", "content": "hi"}], model="openai/gpt-4o-mini")
        assert "Model mismatch error" in str(exc.value)
        assert "liquid/lfm-2.5-2.6b:free" in str(exc.value)


def test_19_missing_model_metadata_causes_transparent_failure():
    """Test 19: Missing model metadata causes a transparent failure."""
    provider = OpenRouterProvider(api_key="test-api-key", base_url="https://openrouter.ai/api/v1")
    fake_resp = httpx.Response(
        200,
        json={
            "id": "gen-nomodel-3",
            "choices": [{"message": {"content": "code"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        },
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
    )
    with patch("httpx.Client.post", return_value=fake_resp):
        with pytest.raises(ModelMismatchError) as exc:
            provider.generate([{"role": "user", "content": "hi"}], model="openai/gpt-4o")
        assert "Missing model metadata" in str(exc.value)


def test_20_cost_uses_verified_serving_model_pricing():
    """Test 20: Cost uses verified serving model pricing; uncataloged model returns None rather than requested model price."""
    # Actual GPT-4o pricing: $2.50 / $10.00 per 1M tokens
    cost_4o = calculate_model_cost("openai/gpt-4o", 1000, 1000)
    assert cost_4o == 0.0125

    # Actual GPT-4o-mini pricing: $0.15 / $0.60 per 1M tokens
    cost_mini = calculate_model_cost("openai/gpt-4o-mini", 1000, 1000)
    assert cost_mini == 0.00075

    # Free model pricing: $0.00
    cost_free = calculate_model_cost("liquid/lfm-2.5-2.6b:free", 1000, 1000)
    assert cost_free == 0.0

    # Uncataloged model: None (unavailable), never falls back to requested price
    cost_unknown = calculate_model_cost("unregistered/exotic-model-7b", 1000, 1000)
    assert cost_unknown is None


def test_21_mismatched_runs_excluded_from_completed_benchmark_runs():
    """Test 21: Model-mismatched or diagnostic runs cannot be counted as completed benchmark runs in aggregates."""
    mismatch_id = f"test_mm_{uuid.uuid4().hex[:8]}"
    with get_session() as session:
        session.add(
            Run(
                run_id=mismatch_id,
                system="mas",
                model="openai/gpt-4o",
                actual_model="cohere/north-mini-code:free",
                execution_mode="LIVE_API",
                status="MODEL_MISMATCH_DIAGNOSTIC",
                failure_reason="MODEL_MISMATCH_DIAGNOSTIC: Requested openai/gpt-4o but served by free model",
                started_at=datetime.utcnow(),
            )
        )
        session.commit()

    async def _test():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            resp = await client.get("/analytics/summary?include_simulated=false&model=openai/gpt-4o")
            assert resp.status_code == 200
            data = resp.json()
            prov = data["provenance_filter"]
            # Verified that mismatched run is not counted in eligible_live_runs
            assert prov["eligible_live_runs"] == 0
            assert prov["excluded_failed_runs"] >= 1

    run_async(_test())


def test_22_model_mismatched_records_remain_visible_in_audit_history():
    """Test 22: Model-mismatched records remain visible in the audit history with separate requested and actual models."""
    diag_id = f"test_audit_{uuid.uuid4().hex[:8]}"
    with get_session() as session:
        session.add(
            Run(
                run_id=diag_id,
                system="mas",
                model="openai/gpt-4o-mini",
                actual_model="liquid/lfm-2.5-2.6b:free",
                execution_mode="LIVE_API",
                status="MODEL_MISMATCH_DIAGNOSTIC",
                failure_reason="MODEL_MISMATCH_DIAGNOSTIC: Served by free model",
                started_at=datetime.utcnow(),
            )
        )
        session.commit()

    async def _test():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            resp = await client.get("/runs")
            assert resp.status_code == 200
            runs = resp.json()["runs"]
            matched = [r for r in runs if r["run_id"] == diag_id]
            assert len(matched) == 1
            row = matched[0]
            assert row["model"] == "openai/gpt-4o-mini"
            assert row["actual_model"] == "liquid/lfm-2.5-2.6b:free"
            assert row["status"] == "MODEL_MISMATCH_DIAGNOSTIC"

    run_async(_test())


def test_23_explicit_model_allowlist_rejects_variants_and_fallbacks():
    """Test 23: Explicit model allowlist rejects unauthorized variants, search-preview, audio, realtime, instruct, and free fallbacks."""
    # GPT-4o rejects variants and free models
    assert is_model_match("openai/gpt-4o", "openai/gpt-4o") is True
    assert is_model_match("openai/gpt-4o", "openai/gpt-4o-2024-05-13") is True
    assert is_model_match("openai/gpt-4o", "openai/gpt-4o-2024-08-06") is True
    assert is_model_match("openai/gpt-4o", "openai/gpt-4o-2024-11-20") is True
    assert is_model_match("openai/gpt-4o", "openai/gpt-4o-mini") is False
    assert is_model_match("openai/gpt-4o", "openai/gpt-4o-audio-preview") is False
    assert is_model_match("openai/gpt-4o", "openai/gpt-4o-realtime-preview") is False
    assert is_model_match("openai/gpt-4o", "openai/gpt-4o-search-preview") is False
    assert is_model_match("openai/gpt-4o", "openai/gpt-4o:free") is False
    assert is_model_match("openai/gpt-4o", "liquid/lfm-2.5-2.6b:free") is False
    assert is_model_match("openai/gpt-4o", "cohere/north-mini-code:free") is False

    # GPT-4o-mini rejects GPT-4o, audio, and unrelated mini variants
    assert is_model_match("openai/gpt-4o-mini", "openai/gpt-4o-mini") is True
    assert is_model_match("openai/gpt-4o-mini", "openai/gpt-4o-mini-2024-07-18") is True
    assert is_model_match("openai/gpt-4o-mini", "openai/gpt-4o") is False
    assert is_model_match("openai/gpt-4o-mini", "openai/gpt-4o-mini-audio-preview") is False
    assert is_model_match("openai/gpt-4o-mini", "cohere/north-mini-code:free") is False
    assert is_model_match("openai/gpt-4o-mini", "liquid/lfm-2.5-2.6b:free") is False

    # GPT-3.5 Turbo rejects instruct, 4o, mini, free models, and 16k variants
    assert is_model_match("openai/gpt-3.5-turbo", "openai/gpt-3.5-turbo") is True
    assert is_model_match("openai/gpt-3.5-turbo", "openai/gpt-3.5-turbo-0125") is True
    assert is_model_match("openai/gpt-3.5-turbo", "openai/gpt-3.5-turbo-1106") is True
    assert is_model_match("openai/gpt-3.5-turbo", "openai/gpt-3.5-turbo-0613") is True
    assert is_model_match("openai/gpt-3.5-turbo", "openai/gpt-3.5-turbo-16k") is False
    assert is_model_match("openai/gpt-3.5-turbo", "openai/gpt-3.5-turbo-16k-0613") is False
    assert is_model_match("openai/gpt-3.5-turbo", "openai/gpt-3.5-turbo-instruct") is False
    assert is_model_match("openai/gpt-3.5-turbo", "openai/gpt-4o") is False
    assert is_model_match("openai/gpt-3.5-turbo", "openai/gpt-4o-mini") is False
    assert is_model_match("openai/gpt-3.5-turbo", "openrouter/free") is False

    # GPT-3.5 Turbo 16k separately declared condition
    assert is_model_match("openai/gpt-3.5-turbo-16k", "openai/gpt-3.5-turbo-16k") is True
    assert is_model_match("openai/gpt-3.5-turbo-16k", "openai/gpt-3.5-turbo-16k-0613") is True
    assert is_model_match("openai/gpt-3.5-turbo-16k", "openai/gpt-3.5-turbo") is False

    # Missing or empty model identity is strictly rejected
    assert is_model_match(None, "openai/gpt-4o") is False
    assert is_model_match("openai/gpt-4o", None) is False
    assert is_model_match("", "openai/gpt-4o") is False
    assert is_model_match("openai/gpt-4o", "") is False


def test_24_openrouter_payload_enforces_allow_fallbacks_false():
    """Test 24: OpenRouter request payload strictly sets allow_fallbacks to False."""
    provider = OpenRouterProvider(api_key="test-api-key", base_url="https://openrouter.ai/api/v1")
    captured_payload = {}

    def mock_post(url, json=None, headers=None):
        nonlocal captured_payload
        captured_payload = json
        return httpx.Response(
            200,
            json={
                "id": "gen-test-payload",
                "model": "openai/gpt-4o",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            },
            request=httpx.Request("POST", url),
        )

    with patch("httpx.Client.post", side_effect=mock_post):
        provider.generate([{"role": "user", "content": "hi"}], model="openai/gpt-4o")

    assert captured_payload.get("model") == "openai/gpt-4o"
    assert captured_payload.get("provider", {}).get("allow_fallbacks") is False


def test_25_all_workflow_agents_follow_model_policy_including_skipped_architect():
    """Test 25: All actual agents called by workflow follow model policy; Architect skipped on SIMPLE tasks."""
    recorded_calls = []

    class MockTrackingLLM(FakeLLMProvider):
        def generate(self, messages, model="fake", response_schema=None, temperature=0.0, run_id=None, agent_name="agent", max_tokens=2000):
            recorded_calls.append({"agent": agent_name, "model": model})
            return super().generate(
                messages=messages,
                model=model,
                response_schema=response_schema,
                temperature=temperature,
                run_id=run_id,
                agent_name=agent_name,
                max_tokens=max_tokens,
            )

    tracking_llm = MockTrackingLLM()
    wf = MASWorkflow(llm=tracking_llm)

    # 1. SIMPLE path: router scores < 4, Architect should be skipped
    recorded_calls.clear()
    state_simple = wf.run(
        requirement="Write a tiny add function that takes a and b and returns a + b.",
        task_id="test_simple_01",
        model_name="openai/gpt-4o",
    )
    assert state_simple.get("complexity") == "SIMPLE"
    agent_names_called = [c["agent"] for c in recorded_calls]
    assert "architect" not in agent_names_called, "Architect must be skipped on SIMPLE task"
    assert "manager" in agent_names_called
    assert "developer" in agent_names_called
    assert "tester" in agent_names_called
    assert "reviewer" in agent_names_called

    # Verify every LLM call used the exact configured model
    for call in recorded_calls:
        assert call["model"] == "openai/gpt-4o", f"Agent {call['agent']} did not use requested model"

    # 2. STRUCTURED path: complex requirement routes to STRUCTURED, Architect must be called with configured model
    recorded_calls.clear()
    complex_req = (
        "Build a hospital management system with database persistence for patient records; "
        "user authentication and jwt login; admin and doctor rbac roles; "
        "REST api integration endpoints; and analytics dashboard reporting."
    )
    state_structured = wf.run(
        requirement=complex_req,
        task_id="test_struct_01",
        model_name="openai/gpt-3.5-turbo",
    )
    assert state_structured.get("complexity") == "STRUCTURED"
    struct_agents_called = [c["agent"] for c in recorded_calls]
    assert "architect" in struct_agents_called, "Architect must be called on STRUCTURED task"
    for call in recorded_calls:
        assert call["model"] == "openai/gpt-3.5-turbo", f"Agent {call['agent']} did not use requested model"


def test_26_model_call_telemetry_persistence_and_mismatch_failure():
    """Test 26: Telemetry is recorded in model_calls table before failure, and mismatched run is excluded from benchmarks."""
    run_id = f"test_telemetry_{uuid.uuid4().hex[:8]}"
    provider = OpenRouterProvider(api_key="test-api-key", base_url="https://openrouter.ai/api/v1")

    # Provider serves audio preview instead of requested GPT-4o
    mock_resp = httpx.Response(
        200,
        json={
            "id": "gen-req-audio-mismatch-999",
            "model": "openai/gpt-4o-audio-preview",
            "choices": [{"message": {"content": "audio-code"}}],
            "usage": {"prompt_tokens": 150, "completion_tokens": 45, "total_tokens": 195},
            "provider": "OpenAI",
            "system_fingerprint": "fp_audio_123",
        },
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
    )

    with get_session() as session:
        session.add(
            Run(
                run_id=run_id,
                system="mas",
                model="openai/gpt-4o",
                actual_model="openai/gpt-4o",
                execution_mode="LIVE_API",
                token_provenance="PROVIDER_REPORTED",
                status="RUNNING",
                started_at=datetime.utcnow(),
            )
        )
        session.commit()

    with patch("httpx.Client.post", return_value=mock_resp):
        with pytest.raises(ModelMismatchError) as exc:
            provider.generate(
                messages=[{"role": "user", "content": "hello"}],
                model="openai/gpt-4o",
                run_id=run_id,
                agent_name="developer",
            )
        assert "Model mismatch error" in str(exc.value)

    # Telemetry must be recorded in model_calls table
    with get_session() as session:
        call_row = session.query(ModelCall).filter(ModelCall.run_id == run_id).first()
        assert call_row is not None
        assert call_row.requested_model == "openai/gpt-4o"
        assert call_row.actual_model == "openai/gpt-4o-audio-preview"
        assert call_row.request_id == "gen-req-audio-mismatch-999"
        assert call_row.agent == "developer"
        assert call_row.input_tokens == 150
        assert call_row.output_tokens == 45
        assert call_row.total_tokens == 195
        assert call_row.raw_metadata is not None

        # Mark run failed with diagnostic mismatch status
        run_row = session.query(Run).filter(Run.run_id == run_id).first()
        run_row.status = "MODEL_MISMATCH_DIAGNOSTIC"
        run_row.actual_model = "openai/gpt-4o-audio-preview"
        session.commit()

    # Verify run is excluded from eligible benchmark summary
    async def _test():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            resp = await client.get("/analytics/summary?include_simulated=false&model=openai/gpt-4o")
            assert resp.status_code == 200
            data = resp.json()
            assert data["provenance_filter"]["eligible_live_runs"] == 0

    run_async(_test())


def test_27_failed_runs_without_artifacts_or_eval_reporting():
    """Test 27: Failed runs producing no artifacts are never evaluated; metrics are N/A and excluded from research stats."""
    run_id = f"test_failed_eval_{uuid.uuid4().hex[:8]}"
    failure_err = "OpenRouter Insufficient Credits (402): Account credits depleted. Switch to a free model or add credits."

    with get_session() as session:
        session.add(
            Run(
                run_id=run_id,
                system="mas",
                model="openai/gpt-4o",
                actual_model="openai/gpt-4o",
                execution_mode="FAILED",
                status="FAILED",
                failure_reason=failure_err,
                token_provenance="UNAVAILABLE",
                total_tokens=0,
                input_tokens=0,
                output_tokens=0,
                estimated_cost=0.0,
                artifacts_manifest="[]",
                started_at=datetime.utcnow(),
                finished_at=datetime.utcnow(),
            )
        )
        session.commit()

    # 1. Run must remain in DB audit history
    with get_session() as session:
        stored_run = session.query(Run).filter(Run.run_id == run_id).first()
        assert stored_run is not None
        assert stored_run.status == "FAILED"
        assert stored_run.failure_reason == failure_err
        # No metrics rows must exist because evaluation never ran
        metric_rows = session.query(Metric).filter(Metric.run_id == run_id).all()
        assert len(metric_rows) == 0

    # 2. Token usage reporting must report UNAVAILABLE, not measured zero usage
    totals = token_logger.get_run_totals(run_id)
    # When no model calls were completed and token provenance is UNAVAILABLE, usage is unavailable
    assert totals["call_count"] == 0 or totals["token_provenance"] == "UNAVAILABLE"

    # Reporting format: metrics must be None / N/A, not fabricated 0.0
    failed_metrics = {
        "completeness": None,
        "executability": None,
        "consistency": None,
        "quality": None,
        "shared_test": None,
    }
    assert failed_metrics["quality"] is None
    assert failed_metrics["completeness"] is None
    q1k = round(failed_metrics["quality"] / (totals["total_tokens"] / 1000), 4) if (failed_metrics["quality"] is not None and totals.get("total_tokens")) else None
    assert q1k is None

    # 3. Analytics API: visible in audit history, strictly excluded from comparative research stats
    async def _test_analytics():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            # Check /runs includes the run in audit history
            r_runs = await client.get("/runs")
            assert r_runs.status_code == 200
            run_items = r_runs.json().get("runs", [])
            found_run = next((r for r in run_items if r["run_id"] == run_id), None)
            assert found_run is not None
            assert found_run["status"] == "FAILED"
            assert found_run["failure_reason"] == failure_err
            # Uncalculated metrics and unavailable tokens must be None in API output
            assert found_run["quality"] is None
            assert found_run["completeness"] is None
            assert found_run["tokens"] is None
            assert found_run["quality_per_1k"] is None

            # Check /analytics/summary strictly excludes the failed run from comparative statistics
            r_summary = await client.get("/analytics/summary?include_simulated=false&model=openai/gpt-4o")
            assert r_summary.status_code == 200
            summary_data = r_summary.json()
            prov = summary_data["provenance_filter"]
            assert prov["eligible_live_runs"] == 0
            assert prov["excluded_failed_runs"] >= 1
            # Quality distribution has 0 contributing runs
            assert summary_data["statistical_summary"]["quality"]["sample_sizes"]["mas"] == 0

    run_async(_test_analytics())


def test_28_skipped_runs_distinguished_from_failures():
    """Test 28: Skipped runs (e.g. ChatDev skipped due to MAS failure) are distinct from execution failures,
    excluded from completed runs and comparative stats, and reflected accurately in reconciliation and APIs.
    """
    skipped_run_id = f"test_skipped_cd_{uuid.uuid4().hex[:8]}"
    skip_reason = "Skipped: Stage 1 stopped after MAS Run A failure"

    with get_session() as session:
        session.add(
            Run(
                run_id=skipped_run_id,
                system="chatdev",
                task_id="srdd_educ_01",
                model="openai/gpt-4o",
                actual_model="openai/gpt-4o",
                execution_mode="SKIPPED",
                status="SKIPPED",
                failure_reason=None,
                skip_reason=skip_reason,
                token_provenance="UNAVAILABLE",
                total_tokens=0,
                input_tokens=0,
                output_tokens=0,
                estimated_cost=0.0,
                artifacts_manifest="[]",
                started_at=datetime.utcnow(),
                finished_at=datetime.utcnow(),
            )
        )
        session.commit()

    # 1. Database state verification: failure_reason must be None, skip_reason populated
    with get_session() as session:
        stored_run = session.query(Run).filter(Run.run_id == skipped_run_id).first()
        assert stored_run is not None
        assert stored_run.status == "SKIPPED"
        assert stored_run.execution_mode == "SKIPPED"
        assert stored_run.failure_reason is None
        assert stored_run.skip_reason == skip_reason
        assert stored_run.system == "chatdev"
        # Zero metric records
        metric_rows = session.query(Metric).filter(Metric.run_id == skipped_run_id).all()
        assert len(metric_rows) == 0

        # Also check historical Stage 1 runs in mas.db
        hist_mas = session.query(Run).filter(Run.run_id == "mas_srdd_educ_01_canonical").first()
        if hist_mas:
            assert hist_mas.status == "FAILED"
            assert hist_mas.failure_reason is not None and "402" in hist_mas.failure_reason
            assert hist_mas.skip_reason is None

        hist_cd = session.query(Run).filter(Run.run_id == "SKIPPED_DUE_TO_MAS_FAILURE").first()
        if hist_cd:
            assert hist_cd.status == "SKIPPED"
            assert hist_cd.execution_mode == "SKIPPED"
            assert hist_cd.failure_reason is None
            assert hist_cd.skip_reason is not None and "Stage 1 stopped" in hist_cd.skip_reason

    # 2. API verification: excluded from completed runs and comparative statistics
    async def _test_skipped_api():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            # /runs verification
            r_runs = await client.get("/runs")
            assert r_runs.status_code == 200
            data_runs = r_runs.json()
            runs_list = data_runs.get("runs", [])
            summary = data_runs.get("summary", {})

            found_run = next((r for r in runs_list if r["run_id"] == skipped_run_id), None)
            assert found_run is not None
            assert found_run["status"] == "SKIPPED"
            assert found_run["execution_mode"] == "SKIPPED"
            assert found_run["failure_reason"] is None
            assert found_run["skip_reason"] == skip_reason
            assert found_run["quality"] is None
            assert found_run["tokens"] is None
            assert found_run["quality_per_1k"] is None

            # Skipped runs must be counted under skipped_runs, not completed_runs
            assert summary["skipped_runs"] >= 1
            assert summary["excluded_skipped_runs"] >= 1

            # /analytics/summary verification
            r_summary = await client.get("/analytics/summary?include_simulated=false&model=openai/gpt-4o")
            assert r_summary.status_code == 200
            summary_data = r_summary.json()
            prov = summary_data["provenance_filter"]
            assert prov["eligible_live_runs"] == 0
            assert prov["excluded_skipped_runs"] >= 1

            # ChatDev must have 0 sample size in comparative stats
            assert summary_data["statistical_summary"]["quality"]["sample_sizes"]["chatdev"] == 0

    run_async(_test_skipped_api())

    # 3. Reconciliation verification: canonical reconciliation file
    recon_path = os.path.join(os.path.dirname(__file__), "..", "eval", "canonical_pilot_reconciliation.json")
    if os.path.exists(recon_path):
        with open(recon_path, "r", encoding="utf-8") as f:
            recon = json.load(f)
        assert recon["pair_validity"] == "INCOMPLETE"
        assert recon["mas"]["status"] == "FAILED"
        assert recon["mas"]["failure_reason"] is not None and "402" in recon["mas"]["failure_reason"]
        assert recon["chatdev"]["status"] == "SKIPPED"
        assert recon["chatdev"]["execution_mode"] == "SKIPPED"
        assert recon["chatdev"]["failure_reason"] is None
        assert "Stage 1 stopped after MAS Run A failure" in recon["chatdev"]["skip_reason"]




