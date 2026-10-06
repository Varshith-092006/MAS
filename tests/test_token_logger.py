"""Unit tests for TokenLogger and per-run token cap enforcement."""

import pytest
from mas.core.llm import ModelResult, TokenCapExceededError, TokenLogger


def test_token_logger_accumulation():
    logger = TokenLogger(max_tokens_per_run=1000)
    res1 = ModelResult(
        text="resp1",
        model_name="gpt-4o",
        provider_model_version="v1",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        latency_ms=20,
        request_id="req-1",
        estimated_cost=0.001,
    )
    logger.record_call("test-run-1", "developer", res1)

    totals = logger.get_run_totals("test-run-1")
    assert totals["input_tokens"] == 100
    assert totals["output_tokens"] == 50
    assert totals["total_tokens"] == 150
    assert totals["call_count"] == 1


def test_token_cap_exceeded():
    logger = TokenLogger(max_tokens_per_run=200)
    res_large = ModelResult(
        text="resp_large",
        model_name="gpt-4o",
        provider_model_version="v1",
        input_tokens=150,
        output_tokens=100,
        total_tokens=250,
        latency_ms=20,
        request_id="req-2",
        estimated_cost=0.002,
    )
    with pytest.raises(TokenCapExceededError):
        logger.record_call("test-run-cap", "developer", res_large)
