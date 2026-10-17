"""Unit and integration tests for ProviderQuotaGovernor and terminal state taxonomy."""

import pytest
from unittest.mock import MagicMock
from mas.core.governor import ProviderQuotaGovernor
from mas.core.llm import OpenRouterAPIError, OpenRouterProvider


def test_openrouter_api_error_daily_quota_detection():
    """Verify OpenRouterAPIError correctly detects daily free tier quota exhaustion."""
    err_data = {
        "error": {
            "message": "Rate limit exceeded: free-models-per-day. Add 10 credits to unlock 1000 free model requests per day",
            "metadata": {
                "limit_source": "openrouter_free_tier_daily",
                "remedy_hint": "Wait for the daily reset (see X-RateLimit-Reset), or purchase credits to raise your free-model daily limit.",
            },
        }
    }
    headers = {
        "x-ratelimit-reset": "1792272000",
        "x-ratelimit-remaining": "0",
        "x-ratelimit-limit": "50",
    }
    err = OpenRouterAPIError(
        status_code=429,
        message="OpenRouter Rate Limit Error (429)",
        error_data=err_data,
        headers=headers,
    )

    assert err.is_daily_quota_exhausted is True
    assert err.status_code == 429
    assert err.limit_source == "openrouter_free_tier_daily"
    assert err.rate_limit_reset == "1792272000"
    assert err.rate_limit_remaining == "0"
    assert err.rate_limit_limit == "50"


def test_openrouter_api_error_standard_rate_limit():
    """Verify non-daily 429 errors (e.g. per-minute burst) are not misclassified as daily quota exhaustion."""
    err_data = {
        "error": {
            "message": "Rate limit exceeded: 20 requests per minute",
            "metadata": {"limit_source": "rpm_burst"},
        }
    }
    err = OpenRouterAPIError(
        status_code=429,
        message="OpenRouter Rate Limit Error (429)",
        error_data=err_data,
    )

    assert err.is_daily_quota_exhausted is False
    assert err.status_code == 429


def test_governor_blocks_on_exhausted_quota(tmp_path):
    """Verify governor blocks dispatch when upstream key metadata indicates 0 remaining free requests."""
    ledger_file = tmp_path / "ledger.json"
    governor = ProviderQuotaGovernor(internal_daily_cap=45, ledger_path=str(ledger_file))
    mock_provider = MagicMock(spec=OpenRouterProvider)
    mock_provider.check_key_metadata.return_value = {
        "is_free_tier": True,
        "free_model_daily_requests": {
            "used": 50,
            "limit": 50,
            "remaining": 0,
        },
        "_response_date": "Sat, 17 Oct 2026 08:00:00 GMT",
    }

    allowed, status_code, meta = governor.evaluate_dispatch_permission(
        slot_name="Task A",
        task_id="dev_markdown_toc_01",
        provider=mock_provider,
    )

    assert allowed is False
    assert status_code == "STOPPED_PROVIDER_QUOTA"
    assert governor.stopped_for_day is True
    assert "Upstream free-model daily quota exhausted" in governor.stopped_reason

    # Subsequent tasks are also blocked immediately without provider queries
    allowed_b, status_code_b, meta_b = governor.evaluate_dispatch_permission(
        slot_name="Task B",
        task_id="dev_inventory_system_01",
    )
    assert allowed_b is False
    assert status_code_b == "STOPPED_PROVIDER_QUOTA"


def test_governor_blocks_on_internal_daily_cap():
    """Verify governor blocks dispatch when internal daily attempt cap of 45 is reached."""
    governor = ProviderQuotaGovernor(internal_daily_cap=10)
    governor.get_ledger_stats = MagicMock(return_value={
        "utc_date": "2026-10-17",
        "successful_model_calls": 10,
        "failed_attempts_recorded": 0,
        "total_attributable_attempts": 10,
        "internal_daily_cap": 10,
    })

    allowed, status_code, meta = governor.evaluate_dispatch_permission(
        slot_name="Task A",
        task_id="dev_markdown_toc_01",
    )

    assert allowed is False
    assert status_code == "STOPPED_BUDGET_CEILING"
    assert governor.stopped_for_day is True
    assert "Internal daily transmission ceiling reached" in governor.stopped_reason


def test_governor_handles_live_429_error():
    """Verify governor handles live 429 error by triggering global stop."""
    governor = ProviderQuotaGovernor(internal_daily_cap=45)
    err = OpenRouterAPIError(
        status_code=429,
        message="Rate limit exceeded: free-models-per-day",
        error_data={
            "error": {
                "message": "Rate limit exceeded: free-models-per-day",
                "metadata": {"limit_source": "openrouter_free_tier_daily"},
            }
        },
        headers={"x-ratelimit-reset": "1792272000"},
    )

    terminal_status = governor.handle_api_error(err, slot_name="Task A", task_id="dev_markdown_toc_01")
    assert terminal_status == "STOPPED_PROVIDER_QUOTA"
    assert governor.stopped_for_day is True
    assert governor.reset_metadata.get("rate_limit_reset") == "1792272000"


def test_ledger_preserves_historical_cap_breach(tmp_path):
    """Verify that the historical 2026-10-17 cap breach (54 attempts) is permanently preserved in the ledger."""
    from mas.core.governor import ProviderQuotaGovernor
    ledger_file = tmp_path / "ledger.json"
    governor = ProviderQuotaGovernor(ledger_path=str(ledger_file))

    # Pre-populate historical breach
    initial_data = {
        "2026-10-17": {
            "total_outbound_http_transmissions": 54,
            "internal_daily_cap": 45,
            "cap_breached": True,
            "breach_excess_transmissions": 9,
        }
    }
    import json
    with open(ledger_file, "w") as f:
        json.dump(initial_data, f)

    ledger = governor.load_ledger()
    assert "2026-10-17" in ledger
    assert ledger["2026-10-17"]["total_outbound_http_transmissions"] == 54
    assert ledger["2026-10-17"]["cap_breached"] is True
    assert ledger["2026-10-17"]["breach_excess_transmissions"] == 9


def test_counter_does_not_reset_after_metadata_query(tmp_path):
    """Verify that a metadata query increments the ledger transmission count and does NOT reset it."""
    from mas.core.governor import ProviderQuotaGovernor
    ledger_file = tmp_path / "ledger.json"
    governor = ProviderQuotaGovernor(ledger_path=str(ledger_file))

    # Record first key metadata transmission
    count1 = governor.record_transmission("KEY_METADATA", "/api/v1/key", status_code=200)
    assert count1 == 1

    stats1 = governor.get_ledger_stats()
    assert stats1["total_attributable_attempts"] == 1
    assert stats1["remaining_internal_attempts"] == 44

    # Record second request (generation)
    count2 = governor.record_transmission("LIVE_GENERATION", "cohere/north-mini-code:free", status_code=200)
    assert count2 == 2

    stats2 = governor.get_ledger_stats()
    assert stats2["total_attributable_attempts"] == 2
    assert stats2["remaining_internal_attempts"] == 43

