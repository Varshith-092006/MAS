"""Comprehensive offline tests for Phase 2AA:
- Token budget fail-closed pre-dispatch reservation and boundary enforcement.
- ChatDev non-zero exit handling, missing main.py detection, and status propagation.
- Manifest pairing integrity under failure modes.
"""

import json
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch
import pytest

from mas.core.llm import (
    FakeLLMProvider,
    ModelResult,
    OpenRouterProvider,
    TokenCapExceededError,
    estimate_prompt_tokens,
    token_logger,
)
from eval.chatdev_adapter import ChatDevAdapter
from eval.runner import update_benchmark_manifest


@pytest.fixture(autouse=True)
def reset_token_logger_state():
    """Isolates token logger in-memory cache and reservations between tests."""
    token_logger._run_totals.clear()
    token_logger._reservations.clear()
    yield
    token_logger._run_totals.clear()
    token_logger._reservations.clear()


# ============================================================================
# SECTION 3: TOKEN BUDGET BOUNDARY TESTS
# ============================================================================

def test_prompt_consumes_most_of_remaining_budget():
    """When a prompt consumes most remaining budget leaving < 50 tokens, it must be blocked before dispatch."""
    run_id = "test_run_prompt_heavy"
    # Pre-record 59,500 tokens (remaining allowance = 500 tokens)
    res_prior = ModelResult(
        text="code",
        model_name="fake",
        provider_model_version="v1",
        input_tokens=40000,
        output_tokens=19500,
        total_tokens=59500,
        latency_ms=10,
        request_id="req1",
        estimated_cost=0.0,
    )
    token_logger.record_call(run_id, "developer", res_prior)

    # A prompt of 400 words (~500 tokens with safety margin)
    # Available for completion = 500 - 500 = 0 < 50 -> must block!
    large_prompt = "arbitrary unique token sequence " * 100
    provider = FakeLLMProvider()

    with pytest.raises(TokenCapExceededError) as exc_info:
        provider.generate(
            messages=[{"role": "user", "content": large_prompt}],
            run_id=run_id,
            agent_name="tester",
            max_tokens=2000,
        )

    assert "budget gate blocked request before dispatch" in str(exc_info.value)
    assert "insufficient for estimated prompt" in str(exc_info.value)


def test_prompt_tokens_plus_requested_completion_exceeding_allowance():
    """Prompt tokens + requested completion exceeding remaining allowance clamps completion allowance."""
    run_id = "test_run_clamped_completion"
    # Pre-record 58,000 tokens (remaining = 2,000 tokens)
    res_prior = ModelResult(
        text="code",
        model_name="fake",
        provider_model_version="v1",
        input_tokens=40000,
        output_tokens=18000,
        total_tokens=58000,
        latency_ms=10,
        request_id="req1",
        estimated_cost=0.0,
    )
    token_logger.record_call(run_id, "manager", res_prior)

    provider = OpenRouterProvider(api_key="sk-test-key")
    captured_payload = {}

    def mock_post(url, json=None, headers=None):
        nonlocal captured_payload
        captured_payload = json
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": "gen-clamp",
            "model": "cohere/north-mini-code:free",
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {"prompt_tokens": 40, "completion_tokens": 100, "total_tokens": 140},
        }
        return mock_resp

    with patch("mas.core.governor.GovernedHTTPClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.side_effect = mock_post
        mock_client_cls.return_value = mock_client

        provider.generate(
            messages=[{"role": "user", "content": "short prompt"}],
            run_id=run_id,
            agent_name="developer",
            max_tokens=2000,
        )

    clamped_max = captured_payload.get("max_tokens")
    assert clamped_max is not None
    assert clamped_max < 2000
    assert clamped_max >= 50
    # Prompt + clamped max tokens cannot exceed the 2000 remaining allowance
    est_prompt = estimate_prompt_tokens([{"role": "user", "content": "short prompt"}])
    assert clamped_max + est_prompt <= 2000


def test_remaining_budget_too_small_for_safe_request():
    """If remaining budget is < 50 tokens, it must be fail-closed blocked before dispatch."""
    run_id = "test_run_too_small"
    # Pre-record 59,960 tokens (remaining = 40 tokens)
    res_prior = ModelResult(
        text="code",
        model_name="fake",
        provider_model_version="v1",
        input_tokens=40000,
        output_tokens=19960,
        total_tokens=59960,
        latency_ms=10,
        request_id="req1",
        estimated_cost=0.0,
    )
    token_logger.record_call(run_id, "developer", res_prior)

    provider = FakeLLMProvider()
    with pytest.raises(TokenCapExceededError) as exc_info:
        provider.generate(
            messages=[{"role": "user", "content": "hi"}],
            run_id=run_id,
            agent_name="tester",
            max_tokens=100,
        )

    assert "budget gate blocked request before dispatch" in str(exc_info.value)


def test_reservation_and_accounting_across_multiple_calls():
    """Reservations lock tokens atomically; reservations are released and reconciled after response."""
    run_id = "test_run_reservations"
    est_input = 100
    req_output = 500

    # 1. First reservation
    res_id_1, eff_out_1 = token_logger.reserve_budget(run_id, est_input, req_output, min_safe_completion=50)
    assert eff_out_1 == 500
    assert token_logger.get_active_reservation_tokens(run_id) == 600

    # 2. Second reservation in-flight
    res_id_2, eff_out_2 = token_logger.reserve_budget(run_id, est_input, req_output, min_safe_completion=50)
    assert eff_out_2 == 500
    assert token_logger.get_active_reservation_tokens(run_id) == 1200

    # 3. Complete first call
    result_1 = ModelResult(
        text="res1",
        model_name="fake",
        provider_model_version="v1",
        input_tokens=90,
        output_tokens=480,
        total_tokens=570,
        latency_ms=10,
        request_id="req1",
        estimated_cost=0.0,
    )
    token_logger.record_call(run_id, "agent1", result_1, reservation_id=res_id_1)
    # Reservation 1 released, total tokens = 570, reservation 2 still active (600)
    assert token_logger.get_active_reservation_tokens(run_id) == 600
    totals = token_logger.get_run_totals(run_id)
    assert totals["total_tokens"] == 570

    # 4. Release second reservation (e.g. on dispatch abort)
    token_logger.release_reservation(res_id_2)
    assert token_logger.get_active_reservation_tokens(run_id) == 0


def test_provider_reporting_more_tokens_than_estimate():
    """If provider returns more tokens than estimated pushing total over 60,000, TokenCapExceededError is raised."""
    run_id = "test_run_overreport"
    # Pre-record 55,000 tokens
    res_prior = ModelResult(
        text="code",
        model_name="fake",
        provider_model_version="v1",
        input_tokens=35000,
        output_tokens=20000,
        total_tokens=55000,
        latency_ms=10,
        request_id="req1",
        estimated_cost=0.0,
    )
    token_logger.record_call(run_id, "developer", res_prior)

    provider = OpenRouterProvider(api_key="sk-test-key")

    def mock_post(url, json=None, headers=None):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": "gen-huge",
            "model": "cohere/north-mini-code:free",
            "choices": [{"message": {"role": "assistant", "content": "unexpectedly verbose output"}}],
            # Reports 6,000 tokens when remaining was only 5,000 -> 55,000 + 6,000 = 61,000 > 60,000!
            "usage": {"prompt_tokens": 1000, "completion_tokens": 5000, "total_tokens": 6000},
        }
        return mock_resp

    with patch("mas.core.governor.GovernedHTTPClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.side_effect = mock_post
        mock_client_cls.return_value = mock_client

        with pytest.raises(TokenCapExceededError) as exc_info:
            provider.generate(
                messages=[{"role": "user", "content": "test"}],
                run_id=run_id,
                agent_name="developer",
                max_tokens=2000,
            )

    assert "exceeded token cap: 61000 > 60000" in str(exc_info.value)


def test_no_generation_request_dispatched_after_gate_rejects():
    """Verifies that no HTTP request is dispatched when the token budget gate rejects a request."""
    run_id = "test_run_no_dispatch"
    res_prior = ModelResult(
        text="code",
        model_name="fake",
        provider_model_version="v1",
        input_tokens=40000,
        output_tokens=20000,
        total_tokens=60000,
        latency_ms=10,
        request_id="req1",
        estimated_cost=0.0,
    )
    token_logger.record_call(run_id, "developer", res_prior)

    provider = OpenRouterProvider(api_key="sk-test-key")

    with patch("mas.core.governor.GovernedHTTPClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        with pytest.raises(TokenCapExceededError):
            provider.generate(
                messages=[{"role": "user", "content": "generate something"}],
                run_id=run_id,
                agent_name="developer",
            )

        # GovernedHTTPClient must NOT have been instantiated or called
        mock_client_cls.assert_not_called()
        mock_client.post.assert_not_called()


# ============================================================================
# SECTION 2: CHATDEV FAILURE & RUNNER INTEGRITY TESTS
# ============================================================================

def test_chatdev_nonzero_exit_produces_failed_status():
    """When ChatDev process exits with non-zero code, it produces FAILED, never COMPLETED."""
    adapter = ChatDevAdapter(llm=MagicMock(spec=OpenRouterProvider))
    task = {"task_id": "test_cd_fail", "name": "Test Nonzero Exit", "description": "Fail task"}
    workspace = tempfile.mkdtemp(prefix="cd_fail_ws_")

    try:
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = "Traceback (most recent call last):\n  File 'run.py', line 125, in <module>\nValueError: No Valid Codes."

        with patch("subprocess.run", return_value=mock_proc):
            res = adapter.run_task(
                task=task,
                output_base_dir=workspace,
                model="cohere/north-mini-code:free",
                run_id="test_cd_nonzero_run",
                use_fake=False,
            )

        assert res["status"] == "FAILED"
        assert "ChatDev exited with code 1" in res["failed_reason"]
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_chatdev_missing_main_py_produces_incomplete():
    """If ChatDev exits 0 but fails to produce main.py, it must be marked INCOMPLETE, never COMPLETED."""
    adapter = ChatDevAdapter(llm=MagicMock(spec=OpenRouterProvider))
    task = {"task_id": "test_cd_missing_main", "name": "Missing Main", "description": "Test contract"}
    workspace = tempfile.mkdtemp(prefix="cd_missing_main_ws_")

    try:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stderr = ""

        with patch("subprocess.run", return_value=mock_proc):
            res = adapter.run_task(
                task=task,
                output_base_dir=workspace,
                model="cohere/north-mini-code:free",
                run_id="test_cd_missing_main_run",
                use_fake=False,
            )

        assert res["status"] == "INCOMPLETE"
        assert "Missing required artifact: main.py" in res["failed_reason"]
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_manifest_pairing_excludes_failed_and_incomplete_runs(tmp_path):
    """update_benchmark_manifest must never pair runs if either system is FAILED or INCOMPLETE."""
    test_mf_path = str(tmp_path / "test_manifest.json")
    records = [
        {
            "run_id": "mas_test_pair_r1",
            "task_id": "srdd_test_01",
            "task_name": "Test Pairing",
            "system": "mas",
            "model": "cohere/north-mini-code:free",
            "repeat_no": 1,
            "ablation": "A0",
            "status": "COMPLETED",
            "execution_mode": "LIVE_API",
            "tokens": 45000,
            "cost": 0.0,
        },
        {
            "run_id": "cd_test_pair_r1",
            "task_id": "srdd_test_01",
            "task_name": "Test Pairing",
            "system": "chatdev",
            "model": "cohere/north-mini-code:free",
            "repeat_no": 1,
            "ablation": "A0",
            "status": "FAILED",
            "execution_mode": "FAILED",
            "tokens": 4200,
            "cost": 0.0,
            "error": "ChatDev exited with code 1",
        },
    ]

    manifest = update_benchmark_manifest(records, manifest_path=test_mf_path)
    # The pair must NOT be complete
    mas_rec = next(r for r in manifest["runs"] if r["run_id"] == "mas_test_pair_r1")
    cd_rec = next(r for r in manifest["runs"] if r["run_id"] == "cd_test_pair_r1")

    assert mas_rec.get("is_paired_complete") is False
    assert cd_rec.get("is_paired_complete") is False
    assert mas_rec.get("paired_counterpart_run_id") is None
    assert cd_rec.get("paired_counterpart_run_id") is None
    assert manifest["summary"]["completed_paired_repeats"] == 0
