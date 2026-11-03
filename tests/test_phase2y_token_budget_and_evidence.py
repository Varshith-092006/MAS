"""Phase 2Y Tests: Token budget enforcement, multi-call accumulation, and evaluator determinism."""

import json
import pytest
from unittest.mock import MagicMock

from mas.core.llm import (
    FakeLLMProvider,
    ModelResult,
    TokenCapExceededError,
    TokenLogger,
)
from eval.neutral_evaluator import NeutralEvaluator
from eval.runner import update_benchmark_manifest
from mas.db.session import init_db


def test_token_logger_multi_call_accumulation_and_budget_exhaustion():
    """Test 1: TokenLogger accumulates tokens across multiple agent calls and raises TokenCapExceededError upon crossing 60k."""
    logger = TokenLogger(max_tokens_per_run=60000)
    run_id = "test_multi_call_run"

    # Call 1: Manager (10,000 tokens)
    res1 = ModelResult(
        text="manager_output",
        model_name="fake",
        provider_model_version="v1",
        input_tokens=7000,
        output_tokens=3000,
        total_tokens=10000,
        latency_ms=10,
        request_id="req1",
        estimated_cost=0.0,
    )
    logger.record_call(run_id, "manager", res1)
    tot1 = logger.get_run_totals(run_id)
    assert tot1["total_tokens"] == 10000
    assert tot1["call_count"] == 1

    # Call 2: Developer (25,000 tokens)
    res2 = ModelResult(
        text="dev_output",
        model_name="fake",
        provider_model_version="v1",
        input_tokens=15000,
        output_tokens=10000,
        total_tokens=25000,
        latency_ms=15,
        request_id="req2",
        estimated_cost=0.0,
    )
    logger.record_call(run_id, "developer", res2)
    tot2 = logger.get_run_totals(run_id)
    assert tot2["total_tokens"] == 35000
    assert tot2["call_count"] == 2

    # Call 3: Reviewer (20,000 tokens) -> Total 55,000 tokens (under 60k)
    res3 = ModelResult(
        text="rev_output",
        model_name="fake",
        provider_model_version="v1",
        input_tokens=12000,
        output_tokens=8000,
        total_tokens=20000,
        latency_ms=12,
        request_id="req3",
        estimated_cost=0.0,
    )
    logger.record_call(run_id, "reviewer", res3)
    tot3 = logger.get_run_totals(run_id)
    assert tot3["total_tokens"] == 55000
    assert tot3["call_count"] == 3

    # Call 4: Iteration 2 Developer (8,000 tokens) -> Total 63,000 tokens (crosses 60k ceiling!)
    res4 = ModelResult(
        text="dev_iter2_output",
        model_name="fake",
        provider_model_version="v1",
        input_tokens=5000,
        output_tokens=3000,
        total_tokens=8000,
        latency_ms=10,
        request_id="req4",
        estimated_cost=0.0,
    )
    with pytest.raises(TokenCapExceededError) as exc_info:
        logger.record_call(run_id, "developer", res4)
    assert "exceeded token cap: 63000 > 60000" in str(exc_info.value)

    # Actual provider tokens and call counts are preserved without double counting
    tot4 = logger.get_run_totals(run_id)
    assert tot4["total_tokens"] == 63000
    assert tot4["call_count"] == 4


def test_post_limit_generation_blocking():
    """Test 2: Provider refuses to generate once token cap has been reached or exceeded."""
    from mas.core.llm import token_logger
    run_id = "test_blocked_run"

    # Pre-populate run with 60,000 tokens
    res_max = ModelResult(
        text="heavy_code",
        model_name="fake",
        provider_model_version="v1",
        input_tokens=40000,
        output_tokens=20000,
        total_tokens=60000,
        latency_ms=25,
        request_id="req_max",
        estimated_cost=0.0,
    )
    token_logger.record_call(run_id, "developer", res_max)

    # Subsequent generation dispatch must be blocked immediately before invocation
    provider = FakeLLMProvider()
    with pytest.raises(TokenCapExceededError) as exc_info:
        provider.generate(
            messages=[{"role": "user", "content": "next task"}],
            run_id=run_id,
            agent_name="tester",
        )
    assert "reached per-run token ceiling of 60000 tokens" in str(exc_info.value)


def test_manifest_pairing_excludes_over_budget_run(tmp_path):
    """Test 3: Manifest pairing logic strictly excludes runs exceeding 60,000 tokens."""
    records = [
        # Attempt 1: Failed MAS
        {
            "run_id": "mas_task_r1",
            "task_id": "srdd_test_01",
            "system": "mas",
            "repeat_no": 1,
            "status": "FAILED",
            "execution_mode": "LIVE_API",
            "tokens": 51682,
            "cost": 0.0,
        },
        # Attempt 2: Over-budget MAS (62,871 tokens, STOPPED_BUDGET_CEILING)
        {
            "run_id": "mas_task_r1_attempt2",
            "task_id": "srdd_test_01",
            "system": "mas",
            "repeat_no": 1,
            "status": "STOPPED_BUDGET_CEILING",
            "execution_mode": "STOPPED_BUDGET_CEILING",
            "tokens": 62871,
            "cost": 0.0,
            "quality": 0.4286,
        },
        # ChatDev: Completed within budget (5,228 tokens)
        {
            "run_id": "cd_task_r1",
            "task_id": "srdd_test_01",
            "system": "chatdev",
            "repeat_no": 1,
            "status": "COMPLETED",
            "execution_mode": "LIVE_API",
            "tokens": 5228,
            "cost": 0.0,
            "quality": 0.4286,
        },
    ]

    test_mf_path = str(tmp_path / "test_budget_manifest.json")
    manifest = update_benchmark_manifest(records, manifest_path=test_mf_path)

    # Over-budget attempt must NOT count as a completed paired repeat
    assert manifest["summary"]["completed_paired_repeats"] == 0
    assert manifest["summary"]["mas_completed_live_runs"] == 0
    assert manifest["summary"]["chatdev_completed_live_runs"] == 1

    run_dict = {r["run_id"]: r for r in manifest["runs"]}
    assert run_dict["mas_task_r1"]["is_paired_complete"] is False
    assert run_dict["mas_task_r1_attempt2"]["is_paired_complete"] is False
    assert run_dict["cd_task_r1"]["is_paired_complete"] is False
    assert run_dict["mas_task_r1_attempt2"]["paired_counterpart_run_id"] is None
    assert run_dict["cd_task_r1"]["paired_counterpart_run_id"] is None


def test_evaluator_score_determinism(tmp_path):
    """Test 4: NeutralEvaluator produces deterministic, symmetric scores across repeated evaluations."""
    evaluator = NeutralEvaluator()
    ws = tmp_path / "app"
    ws.mkdir()
    (ws / "main.py").write_text(
        "def solve(q):\n"
        "    return 'Solution for ' + q\n"
        "def main():\n"
        "    print(solve('science'))\n"
        "if __name__ == '__main__':\n"
        "    main()\n",
        encoding="utf-8",
    )

    req = "Step-by-step science question solver providing explanations and solutions."
    res1 = evaluator.evaluate_project(str(ws), req, task_id="test_task", persist_to_db=False)
    res2 = evaluator.evaluate_project(str(ws), req, task_id="test_task", persist_to_db=False)

    assert res1["completeness"] == res2["completeness"]
    assert res1["executability"] == res2["executability"]
    assert res1["consistency"] == res2["consistency"]
    assert res1["quality"] == res2["quality"]
    assert res1["shared_test"] == res2["shared_test"]


def test_pre_call_budget_gate_constrains_max_tokens():
    """Test 5: Pre-call budget gate constrains requested max_tokens to the remaining run allowance under 60k."""
    from mas.core.llm import OpenRouterProvider, token_logger, ModelResult
    from unittest.mock import patch, MagicMock

    run_id = "test_constrained_tokens_run"
    # Pre-record 58,500 tokens for this run (leaving 1,500 tokens before 60k limit)
    res_prior = ModelResult(
        text="prior_code",
        model_name="fake",
        provider_model_version="v1",
        input_tokens=40000,
        output_tokens=18500,
        total_tokens=58500,
        latency_ms=20,
        request_id="req_prior",
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
            "id": "gen-1",
            "model": "cohere/north-mini-code:free",
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        }
        return mock_resp

    with patch("mas.core.governor.GovernedHTTPClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.side_effect = mock_post
        mock_client_cls.return_value = mock_client

        provider.generate(
            messages=[{"role": "user", "content": "test prompt"}],
            run_id=run_id,
            agent_name="developer",
            max_tokens=2000,
        )

    # Requested max_tokens was 2000, remaining allowance is 60000 - 58500 = 1500.
    # Fail-closed gate reserves estimated prompt tokens (38 tokens), constraining max_tokens to 1462 <= 1500
    assert captured_payload.get("max_tokens") <= 1500
    assert captured_payload.get("max_tokens") == 1462

