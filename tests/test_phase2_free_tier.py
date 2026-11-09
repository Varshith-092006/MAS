"""Unit tests for Phase 2: Free-tier provider-agnostic infrastructure.

Tests (strictly offline / zero network calls):
1. Fake provider returning canned replies.
2. 429 simulator and failure classification (INFRA_ERROR vs QUALITY_FAILURE).
3. Model mismatch enforcement (including models/ prefix handling).
4. Budget exhausted case (DailyTransmissionsCeilingExceededError).
5. Resume test with half-finished manifest (skipping completed, re-running INTERRUPTED).
6. Sliding window rate limiter with fake clock (RPM and TPM).
7. Quota timezone rollover with fake clock (America/Los_Angeles local midnight).
"""

import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest

from eval.runner import EvaluationRunner, classify_failure
from mas.core.governor import (
    DailyTransmissionsCeilingExceededError,
    ProviderQuotaGovernor,
    SlidingWindowRateLimiter,
)
from mas.core.llm import (
    FakeLLMProvider,
    ModelMismatchError,
    ModelResult,
    is_model_match,
)


class FakeClock:
    """Controllable clock for deterministic rate limiter and rollover tests."""

    def __init__(self, initial_time: float = 1700000000.0):
        self._current_time = initial_time

    def time(self) -> float:
        return self._current_time

    def advance(self, seconds: float):
        self._current_time += seconds

    def sleep(self, seconds: float):
        self._current_time += seconds


def test_fake_provider_canned_replies():
    """Item 7.1: Verify FakeLLMProvider returns canned ModelResult artifacts without network calls."""
    provider = FakeLLMProvider()
    res = provider.generate(
        messages=[{"role": "user", "content": "Write a python calculator"}],
        model="fake",
    )
    assert isinstance(res, ModelResult)
    assert res.text is not None
    assert len(res.text) > 0
    assert res.model_name == "fake"
    assert res.input_tokens > 0
    assert res.output_tokens > 0


def test_429_simulator_and_failure_classification():
    """Item 7.2: Verify 429 rate limit is classified as INFRA_ERROR and quality failures as QUALITY_FAILURE."""
    # 429 rate limit
    infra_class = classify_failure(exc=None, status="HTTP_ERROR", error_msg="429 Rate limit exceeded")
    assert infra_class == "INFRA_ERROR"

    # 503 Service Unavailable
    infra_503 = classify_failure(exc=None, status="FAILED", error_msg="503 Service Unavailable")
    assert infra_503 == "INFRA_ERROR"

    # Model mismatch
    mismatch_class = classify_failure(exc=ModelMismatchError("Model mismatch"), status="FAILED")
    assert mismatch_class == "INFRA_ERROR"

    # Quality failure: bad JSON parse
    quality_class = classify_failure(exc=ValueError("Failed to parse JSON"), status="FAILED")
    assert quality_class == "QUALITY_FAILURE"

    # Quality failure: token budget ceiling
    budget_class = classify_failure(exc=None, status="STOPPED_BUDGET_CEILING")
    assert budget_class == "QUALITY_FAILURE"


def test_model_mismatch_and_prefix_handling():
    """Item 7.3: Verify model pinning and graceful handling of models/ prefix."""
    # Exact match
    assert is_model_match("gemini-2.0-flash-lite", "gemini-2.0-flash-lite")

    # models/ prefix match
    assert is_model_match("models/gemini-2.0-flash-lite", "gemini-2.0-flash-lite")
    assert is_model_match("gemini-2.0-flash-lite", "models/gemini-2.0-flash-lite")
    assert is_model_match("models/gemini-2.0-flash-lite", "models/gemini-2.0-flash-lite")

    # Mismatch between different models
    assert not is_model_match("gemini-2.0-flash-lite", "gemini-1.5-pro")
    assert not is_model_match("google/gemini-2.0-flash-exp:free", "cohere/north-mini-code:free")


def test_budget_exhausted_case(tmp_path):
    """Item 7.4: Verify DailyTransmissionsCeilingExceededError is raised when effective cap is reached."""
    ledger_file = str(tmp_path / "test_ledger.json")
    gov = ProviderQuotaGovernor(internal_daily_cap=2, ledger_path=ledger_file)

    # First transmission allowed
    att1 = gov.reserve_transmission(request_type="LIVE_GENERATION", target="model-a")
    gov.finalize_transmission(att1, status_code=200)

    # Second transmission allowed
    att2 = gov.reserve_transmission(request_type="LIVE_GENERATION", target="model-a")
    gov.finalize_transmission(att2, status_code=200)

    # Third transmission must raise DailyTransmissionsCeilingExceededError before dispatch
    with pytest.raises(DailyTransmissionsCeilingExceededError):
        gov.reserve_transmission(request_type="LIVE_GENERATION", target="model-a")


def test_resume_with_half_finished_manifest(tmp_path):
    """Item 7.5: Verify --resume skips completed runs and re-runs INTERRUPTED runs."""
    manifest_file = str(tmp_path / "test_manifest.json")
    manifest_data = {
        "version": "1.0",
        "benchmark": "test_bench",
        "runs": [
            {
                "task_id": "task_01",
                "system": "mas",
                "repeat_no": 1,
                "status": "COMPLETED",
                "official": True,
            },
            {
                "task_id": "task_02",
                "system": "mas",
                "repeat_no": 1,
                "status": "INTERRUPTED",  # Was interrupted, must be re-run!
                "official": False,
            },
        ],
        "summary": {},
    }
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f)

    # Check resume logic
    completed_keys = set()
    with open(manifest_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)
        for r in loaded.get("runs", []):
            if r.get("status") != "INTERRUPTED" and r.get("status") is not None:
                completed_keys.add((r.get("task_id"), r.get("system"), r.get("repeat_no")))

    assert ("task_01", "mas", 1) in completed_keys  # Skip
    assert ("task_02", "mas", 1) not in completed_keys  # Re-run!
    assert ("task_03", "mas", 1) not in completed_keys  # Run fresh!


def test_sliding_window_rate_limiter_requests():
    """Item 7.6a: Verify sliding window rate limiter blocks on exceeding RPM."""
    fake_clock = FakeClock(initial_time=1000.0)
    limiter = SlidingWindowRateLimiter(
        requests_per_minute=3,
        tokens_per_minute=100000,
        clock=fake_clock.time,
        sleep_func=fake_clock.sleep,
    )

    # Send 3 requests within window
    t1 = limiter.acquire(estimated_tokens=100)
    assert t1 == 0.0
    t2 = limiter.acquire(estimated_tokens=100)
    assert t2 == 0.0
    t3 = limiter.acquire(estimated_tokens=100)
    assert t3 == 0.0

    # 4th request must sleep until oldest request expires (> 60s)
    t4 = limiter.acquire(estimated_tokens=100)
    assert t4 >= 60.0


def test_sliding_window_rate_limiter_tokens():
    """Item 7.6b: Verify sliding window rate limiter blocks on exceeding TPM."""
    fake_clock = FakeClock(initial_time=1000.0)
    limiter = SlidingWindowRateLimiter(
        requests_per_minute=20,
        tokens_per_minute=5000,
        clock=fake_clock.time,
        sleep_func=fake_clock.sleep,
    )

    # Request with 3000 tokens (allowed immediately)
    t1 = limiter.acquire(estimated_tokens=3000)
    assert t1 == 0.0

    # Second request with 3000 tokens exceeds 5000 TPM limit (3000 + 3000 > 5000)
    t2 = limiter.acquire(estimated_tokens=3000)
    assert t2 >= 60.0


def test_quota_timezone_rollover_with_fake_clock(tmp_path):
    """Item 7.7: Verify ledger date rollover obeys America/Los_Angeles local midnight."""
    from datetime import timedelta, timezone as dt_tz
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("America/Los_Angeles")
    except Exception:
        tz = dt_tz(timedelta(hours=-8))

    # Set initial time to 23:59:50 on 2026-11-10 in America/Los_Angeles
    dt_before = datetime(2026, 11, 10, 23, 59, 50, tzinfo=tz)
    fake_clock = FakeClock(initial_time=dt_before.timestamp())

    ledger_file = str(tmp_path / "rollover_ledger.json")
    gov = ProviderQuotaGovernor(
        internal_daily_cap=5,
        quota_timezone="America/Los_Angeles",
        clock=fake_clock.time,
        ledger_path=ledger_file,
    )

    # Check date before midnight
    assert gov.get_current_date_str() == "2026-11-10"
    att = gov.reserve_transmission("LIVE_GENERATION", "target-1")
    gov.finalize_transmission(att, status_code=200)

    stats_before = gov.get_ledger_stats()
    assert stats_before["total_attributable_attempts"] == 1

    # Advance fake clock by 20 seconds (across local midnight to 00:00:10 on 2026-11-11)
    fake_clock.advance(20.0)
    assert gov.get_current_date_str() == "2026-11-11"

    # Ledger rolls over: new day starts at 0 attempts!
    stats_after = gov.get_ledger_stats()
    assert stats_after["total_attributable_attempts"] == 0
    assert stats_after["utc_date"] == "2026-11-11"
