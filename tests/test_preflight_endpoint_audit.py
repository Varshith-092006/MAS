"""Tests for Phase 2N: Final Preflight Endpoint Audit and Fail-Closed Quota Parsing.

Verifies:
1. Endpoint correctness: GET https://openrouter.ai/api/v1/key (not /auth/key).
2. Quota parsing: Reads data.free_model_daily_requests.remaining.
3. Fail-closed behavior: Stops on zero quota, missing fields, malformed JSON, auth errors.
4. Exact-once request accounting: No retries, no duplicate metadata requests.
5. Model availability decoupling: Key preflight does not claim model availability;
   generation strictly validates served identity with allow_fallbacks=False.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
import httpx

from mas.core.llm import OpenRouterProvider, ModelMismatchError, OpenRouterAPIError
from mas.core.governor import ProviderQuotaGovernor, GovernedHTTPClient


@pytest.fixture
def isolated_governor(tmp_path):
    """Provides a fresh ProviderQuotaGovernor backed by an isolated temporary ledger."""
    ledger_path = tmp_path / "audit_test_ledger.json"
    gov = ProviderQuotaGovernor(internal_daily_cap=45, ledger_path=str(ledger_path))
    gov.initialize_day("2026-10-18")
    return gov


def test_01_endpoint_is_documented_api_v1_key(tmp_path):
    """1. Verify OpenRouterProvider.check_key_metadata queries GET https://openrouter.ai/api/v1/key."""
    ledger_path = tmp_path / "endpoint_ledger.json"
    governor = ProviderQuotaGovernor(internal_daily_cap=45, ledger_path=str(ledger_path))
    governor.initialize_day("2026-10-18")

    provider = OpenRouterProvider(api_key="test-sk-12345", base_url="https://openrouter.ai/api/v1")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.headers = {"date": "Sun, 18 Oct 2026 00:00:01 GMT"}
    mock_resp.json.return_value = {
        "data": {
            "label": "test-key",
            "usage": 0.0,
            "is_free_tier": True,
            "free_model_daily_requests": {
                "limit": 50,
                "used": 5,
                "remaining": 45,
            },
        }
    }

    recorded_urls = []
    recorded_targets = []

    def mock_get(url, *args, **kwargs):
        recorded_urls.append(url)
        return mock_resp

    with patch("mas.core.governor.global_governor", governor):
        with patch.object(httpx.Client, "get", side_effect=mock_get):
            data = provider.check_key_metadata()

    # Verify URL called
    assert len(recorded_urls) == 1
    assert recorded_urls[0] == "https://openrouter.ai/api/v1/key"
    assert "/auth/key" not in recorded_urls[0]

    # Verify persistent ledger recorded target as /api/v1/key
    stats = governor.get_ledger_stats()
    assert stats["total_attributable_attempts"] == 1
    current_date = governor.get_current_utc_date_str()
    ledger = governor.load_ledger()
    day_events = ledger[current_date]["events"]
    assert len(day_events) == 1
    assert day_events[0]["target"] == "/api/v1/key"
    assert day_events[0]["type"] == "KEY_METADATA"


def test_02_quota_parsing_positive_remaining_proceeds(isolated_governor):
    """2. Valid response with positive remaining quota allows execution to proceed."""
    provider = MagicMock(spec=OpenRouterProvider)
    provider.uses_governed_client = True
    provider.check_key_metadata.return_value = {
        "label": "research-key",
        "is_free_tier": True,
        "free_model_daily_requests": {
            "limit": 50,
            "used": 12,
            "remaining": 38,
        },
        "_response_date": "Sun, 18 Oct 2026 00:00:05 GMT",
    }

    status = isolated_governor.check_upstream_key_status(provider)

    assert status["can_proceed"] is True
    assert status["is_quota_exhausted"] is False
    assert status["free_models_remaining"] == 38
    assert status["free_models_used"] == 12
    assert status["free_models_limit"] == 50
    assert isolated_governor.stopped_for_day is False


def test_03_quota_parsing_zero_remaining_stops_fail_closed(isolated_governor):
    """3. Response with remaining == 0 stops execution immediately."""
    provider = MagicMock(spec=OpenRouterProvider)
    provider.uses_governed_client = True
    provider.check_key_metadata.return_value = {
        "label": "research-key",
        "is_free_tier": True,
        "free_model_daily_requests": {
            "limit": 50,
            "used": 50,
            "remaining": 0,
        },
        "_response_date": "Sun, 18 Oct 2026 00:00:05 GMT",
    }

    status = isolated_governor.check_upstream_key_status(provider)

    assert status["can_proceed"] is False
    assert status["is_quota_exhausted"] is True
    assert status["free_models_remaining"] == 0
    assert isolated_governor.stopped_for_day is True
    assert "Upstream free-model daily quota exhausted" in isolated_governor.stopped_reason


def test_04_quota_parsing_missing_free_model_daily_requests_stops_fail_closed(isolated_governor):
    """4. Response missing 'free_model_daily_requests' stops fail-closed, does not assume available."""
    provider = MagicMock(spec=OpenRouterProvider)
    provider.uses_governed_client = True
    provider.check_key_metadata.return_value = {
        "label": "paid-or-unconfigured-key",
        "usage": 0.0,
        "limit": None,
        "is_free_tier": False,
    }

    status = isolated_governor.check_upstream_key_status(provider)

    assert status["can_proceed"] is False
    assert status["is_quota_exhausted"] is True
    assert status["free_models_remaining"] == 0
    assert isolated_governor.stopped_for_day is True
    assert "missing 'free_model_daily_requests'" in isolated_governor.stopped_reason


def test_05_quota_parsing_missing_remaining_field_stops_fail_closed(isolated_governor):
    """5. Response with missing 'remaining' field stops fail-closed, does not compute limit-used."""
    provider = MagicMock(spec=OpenRouterProvider)
    provider.uses_governed_client = True
    provider.check_key_metadata.return_value = {
        "free_model_daily_requests": {
            "limit": 50,
            "used": 10,
            # 'remaining' omitted
        }
    }

    status = isolated_governor.check_upstream_key_status(provider)

    assert status["can_proceed"] is False
    assert status["is_quota_exhausted"] is True
    assert status["free_models_remaining"] == 0
    assert isolated_governor.stopped_for_day is True
    assert "missing or invalid 'remaining' field" in isolated_governor.stopped_reason


def test_06_malformed_json_response_stops_fail_closed(isolated_governor, tmp_path):
    """6. Malformed JSON or missing 'data' envelope in HTTP response stops fail-closed."""
    provider = OpenRouterProvider(api_key="test-key", base_url="https://openrouter.ai/api/v1")

    # Case A: JSON missing "data" key
    mock_resp_bad = MagicMock(spec=httpx.Response)
    mock_resp_bad.status_code = 200
    mock_resp_bad.json.return_value = {"error": "unexpected_schema"}
    mock_resp_bad.text = '{"error": "unexpected_schema"}'
    mock_resp_bad.headers = {}

    with patch("mas.core.governor.global_governor", isolated_governor):
        with patch.object(httpx.Client, "get", return_value=mock_resp_bad):
            meta = provider.check_key_metadata()
            assert meta.get("error") == "malformed_response_missing_data_field"
            status = isolated_governor.check_upstream_key_status(provider)
            assert status["can_proceed"] is False
            assert status["is_quota_exhausted"] is True

    # Case B: JSON decode error
    mock_resp_raw = MagicMock(spec=httpx.Response)
    mock_resp_raw.status_code = 200
    mock_resp_raw.json.side_effect = json.JSONDecodeError("Expecting value", "bad json", 0)
    mock_resp_raw.text = "bad json"
    mock_resp_raw.headers = {}

    with patch("mas.core.governor.global_governor", isolated_governor):
        with patch.object(httpx.Client, "get", return_value=mock_resp_raw):
            meta = provider.check_key_metadata()
            assert "json_decode_error" in meta.get("error", "")
            status = isolated_governor.check_upstream_key_status(provider)
            assert status["can_proceed"] is False
            assert status["is_quota_exhausted"] is True


def test_07_auth_error_stops_fail_closed(isolated_governor):
    """7. HTTP 401 Unauthorized or missing API key stops execution fail-closed."""
    provider = OpenRouterProvider(api_key="invalid-key", base_url="https://openrouter.ai/api/v1")

    mock_resp_401 = MagicMock(spec=httpx.Response)
    mock_resp_401.status_code = 401
    mock_resp_401.text = '{"error": {"message": "Invalid API key"}}'
    mock_resp_401.headers = {}

    with patch("mas.core.governor.global_governor", isolated_governor):
        with patch.object(httpx.Client, "get", return_value=mock_resp_401):
            status = isolated_governor.check_upstream_key_status(provider)

    assert status["can_proceed"] is False
    assert status["is_quota_exhausted"] is True
    assert isolated_governor.stopped_for_day is True
    assert "Upstream key preflight query failed" in isolated_governor.stopped_reason


def test_08_exact_once_accounting_no_retries_no_duplicates(tmp_path):
    """8. Preflight executes exactly ONE transmission; no retries; no duplicate metadata calls on task dispatches."""
    ledger_path = tmp_path / "accounting_ledger.json"
    governor = ProviderQuotaGovernor(internal_daily_cap=45, ledger_path=str(ledger_path))
    governor.initialize_day("2026-10-18")

    provider = OpenRouterProvider(api_key="valid-key", base_url="https://openrouter.ai/api/v1")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.headers = {"date": "Sun, 18 Oct 2026 00:00:01 GMT"}
    mock_resp.json.return_value = {
        "data": {
            "free_model_daily_requests": {"limit": 50, "used": 1, "remaining": 49}
        }
    }

    call_count = 0

    def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return mock_resp

    with patch("mas.core.governor.global_governor", governor):
        with patch.object(httpx.Client, "get", side_effect=mock_get):
            # 1. Execute single preflight check
            status = governor.check_upstream_key_status(provider, record_attempt=True)
            assert status["can_proceed"] is True

            # Verify exactly 1 network call occurred
            assert call_count == 1
            stats = governor.get_ledger_stats()
            assert stats["total_attributable_attempts"] == 1
            assert stats["remaining_internal_attempts"] == 44

            # 2. Sequential task evaluations pass provider=None (no duplicate metadata queries)
            for slot, task_id in [("Task A", "dev_markdown_toc_01"), ("Task B", "dev_inventory_system_01")]:
                allowed, code, _ = governor.evaluate_dispatch_permission(slot, task_id, provider=None)
                assert allowed is True

            # Verify STILL exactly 1 network call
            assert call_count == 1
            stats_after = governor.get_ledger_stats()
            assert stats_after["total_attributable_attempts"] == 1


def test_09_model_availability_and_fallback_strictness():
    """9. Key preflight does not confirm model availability.
    Generation dispatches with allow_fallbacks=False and raises ModelMismatchError if provider serves another model.
    """
    provider = OpenRouterProvider(
        api_key="test-key",
        default_model="cohere/north-mini-code:free",
        base_url="https://openrouter.ai/api/v1",
    )

    captured_payloads = []

    mock_resp_mismatch = MagicMock(spec=httpx.Response)
    mock_resp_mismatch.status_code = 200
    mock_resp_mismatch.headers = {}
    mock_resp_mismatch.json.return_value = {
        "id": "gen-12345",
        "model": "meta-llama/llama-3-8b:free",  # Different model returned!
        "choices": [{"message": {"content": "hello"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }

    def mock_post(url, json=None, *args, **kwargs):
        captured_payloads.append(json)
        return mock_resp_mismatch

    with patch.object(httpx.Client, "post", side_effect=mock_post):
        with pytest.raises(ModelMismatchError) as exc_info:
            provider.generate([{"role": "user", "content": "test"}], run_id="test_run_1")

    # Verify allow_fallbacks was explicitly False
    assert len(captured_payloads) == 1
    assert captured_payloads[0]["provider"]["allow_fallbacks"] is False
    assert captured_payloads[0]["model"] == "cohere/north-mini-code:free"

    # Verify ModelMismatchError was raised to prevent silent fallback
    assert "Requested 'cohere/north-mini-code:free', but provider returned 'meta-llama/llama-3-8b:free'" in str(exc_info.value)


def test_10_absent_is_free_tier_does_not_claim_free_tier(isolated_governor):
    """10. An absent 'is_free_tier' field cannot silently cause an unsupported claim that the key is a free-tier key."""
    provider = MagicMock(spec=OpenRouterProvider)
    provider.uses_governed_client = True
    provider.check_key_metadata.return_value = {
        "label": "unspecified-tier-key",
        # 'is_free_tier' omitted
        "free_model_daily_requests": {
            "limit": 50,
            "used": 5,
            "remaining": 45,
        },
        "_response_date": "Sun, 18 Oct 2026 00:00:05 GMT",
    }

    status = isolated_governor.check_upstream_key_status(provider)

    # Must NOT claim is_free_tier is True when the provider omitted the field
    assert status["is_free_tier"] is False
    assert status["free_models_remaining"] == 45
    assert status["can_proceed"] is True

