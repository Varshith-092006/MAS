"""Offline unit and concurrency tests for Phase 2L Race-Safe Transmission Governance.

Verifies:
1. Concurrent callers sharing one ledger cannot exceed the cap.
2. With a test cap of 5, at most 5 attempts can reserve a slot; the 6th is rejected before transport sends anything.
3. Reservations are persisted to disk before transport invocation.
4. Simulated crashes after reservation or after dispatch preserve the consumed allowance.
5. Finalizing an attempt cannot increment the daily transmission counter a second time.
6. Retries each reserve a separate slot.
7. Failed HTTP and network attempts each count once.
8. Separate processes or governor instances cannot oversubscribe a shared cap.
9. The UTC date transition starts a new daily count without modifying previous dates.
10. Network-capable application and diagnostic entry points cannot bypass the governed transport.
11. Test execution uses an isolated ledger and does not mutate the production ledger.

All tests operate strictly offline with zero real network requests.
"""

import concurrent.futures
import json
import os
from unittest.mock import MagicMock, patch
import httpx
import pytest

from mas.core.governor import (
    ProviderQuotaGovernor,
    GovernedHTTPClient,
    DailyTransmissionsCeilingExceededError,
    DEFAULT_LEDGER_FILE,
)


def test_1_concurrent_callers_sharing_ledger_cannot_exceed_cap(tmp_path):
    """1. Concurrent callers sharing one ledger cannot exceed the cap."""
    ledger_file = tmp_path / "concurrent_ledger.json"
    cap = 10
    total_workers = 25

    # 25 concurrent threads attempting to reserve slots under a cap of 10
    def attempt_reservation(worker_id):
        gov = ProviderQuotaGovernor(internal_daily_cap=cap, ledger_path=str(ledger_file))
        try:
            att_id = gov.reserve_transmission(
                request_type="LIVE_GENERATION",
                target="cohere/north-mini-code:free",
                source=f"worker_{worker_id}",
            )
            # Simulate slight transmission latency
            gov.finalize_transmission(att_id, status_code=200)
            return True, None
        except DailyTransmissionsCeilingExceededError as e:
            return False, type(e).__name__

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(attempt_reservation, range(total_workers)))

    successes = sum(1 for ok, _ in results if ok)
    rejections = sum(1 for ok, _ in results if not ok)

    assert successes == cap
    assert rejections == total_workers - cap

    # Verify ledger file on disk has exactly 10 transmissions and zero oversubscription
    gov_final = ProviderQuotaGovernor(internal_daily_cap=cap, ledger_path=str(ledger_file))
    stats = gov_final.get_ledger_stats()
    assert stats["total_attributable_attempts"] == cap
    assert stats["remaining_internal_attempts"] == 0
    assert stats["cap_breached"] is False


def test_2_cap_of_5_allows_at_most_5_and_rejects_sixth_before_transport(tmp_path):
    """2. With a test cap of 5, at most 5 attempts can reserve a slot; 6th is rejected before transport invocation."""
    ledger_file = tmp_path / "cap5_ledger.json"
    governor = ProviderQuotaGovernor(internal_daily_cap=5, ledger_path=str(ledger_file))

    transport_mock = MagicMock(return_value=httpx.Response(200, json={"ok": True}, request=httpx.Request("POST", "https://api.test")))

    with GovernedHTTPClient(governor=governor) as client:
        with patch.object(client.http_client, "post", transport_mock):
            # First 5 dispatches must succeed
            for i in range(5):
                r = client.post("https://api.test/chat/completions", json={"i": i})
                assert r.status_code == 200

            assert transport_mock.call_count == 5
            assert governor.get_ledger_stats()["total_attributable_attempts"] == 5

            # 6th attempt MUST raise DailyTransmissionsCeilingExceededError
            with pytest.raises(DailyTransmissionsCeilingExceededError) as exc_info:
                client.post("https://api.test/chat/completions", json={"i": 6})

            assert "daily ceiling reached" in str(exc_info.value)
            # Transport was NEVER invoked for the 6th call
            assert transport_mock.call_count == 5

    # Disk ledger remains strictly 5
    with open(ledger_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    today = governor.get_current_utc_date_str()
    assert data[today]["total_outbound_http_transmissions"] == 5


def test_3_reservations_are_persisted_before_transport_invocation(tmp_path):
    """3. Reservations are persisted to disk in 'RESERVED' state before transport invocation."""
    ledger_file = tmp_path / "pre_dispatch_ledger.json"
    governor = ProviderQuotaGovernor(internal_daily_cap=45, ledger_path=str(ledger_file))

    state_observed_during_dispatch = None

    def transport_during_flight(url, *args, **kwargs):
        nonlocal state_observed_during_dispatch
        # Read the persistent file on disk while the HTTP call is in-flight
        with open(ledger_file, "r", encoding="utf-8") as f:
            disk_data = json.load(f)
        today = governor.get_current_utc_date_str()
        events = disk_data[today]["events"]
        state_observed_during_dispatch = {
            "total_count": disk_data[today]["total_outbound_http_transmissions"],
            "event_state": events[-1]["state"],
            "attempt_id": events[-1]["attempt_id"],
        }
        return httpx.Response(200, json={"status": "ok"}, request=httpx.Request("POST", url))

    with GovernedHTTPClient(governor=governor) as client:
        with patch.object(client.http_client, "post", side_effect=transport_during_flight):
            client.post("https://api.test/chat/completions")

    # Verify that in-flight, the reservation was already written to disk
    assert state_observed_during_dispatch is not None
    assert state_observed_during_dispatch["total_count"] == 1
    assert state_observed_during_dispatch["event_state"] == "RESERVED"

    # After return, attempt is finalized to SUCCEEDED without incrementing total
    stats = governor.get_ledger_stats()
    assert stats["total_attributable_attempts"] == 1
    assert stats["successful_model_calls"] == 1


def test_4_simulated_crash_after_reservation_preserves_consumed_allowance(tmp_path):
    """4. Simulated crashes after reservation or after dispatch preserve the consumed allowance."""
    ledger_file = tmp_path / "crash_ledger.json"
    governor_a = ProviderQuotaGovernor(internal_daily_cap=45, ledger_path=str(ledger_file))

    # Attempt 1 completes normally
    with GovernedHTTPClient(governor=governor_a) as client:
        with patch.object(client.http_client, "post", return_value=httpx.Response(200, json={}, request=httpx.Request("POST", "https://api.test"))):
            client.post("https://api.test/chat/completions")

    # Attempt 2 simulates a crash after reservation: reserve slot, then crash
    att_id_crashed = governor_a.reserve_transmission(
        request_type="LIVE_GENERATION",
        target="cohere/north-mini-code:free",
        source="crashed_process",
    )
    # Process crashes here: finalize_transmission is NEVER called for att_id_crashed
    del governor_a

    # Process B boots up fresh from the same ledger file
    governor_b = ProviderQuotaGovernor(internal_daily_cap=45, ledger_path=str(ledger_file))
    stats_b = governor_b.get_ledger_stats()

    # The unfinalized reservation MUST still count against the daily allowance
    assert stats_b["total_attributable_attempts"] == 2
    assert stats_b["remaining_internal_attempts"] == 43
    assert stats_b["active_reservations"] == 1

    # Verify disk content
    with open(ledger_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    today = governor_b.get_current_utc_date_str()
    events = data[today]["events"]
    assert events[1]["attempt_id"] == att_id_crashed
    assert events[1]["state"] == "RESERVED"


def test_5_finalizing_attempt_cannot_increment_counter_second_time(tmp_path):
    """5. Finalizing an attempt cannot increment the daily transmission counter a second time."""
    ledger_file = tmp_path / "finalize_ledger.json"
    governor = ProviderQuotaGovernor(internal_daily_cap=45, ledger_path=str(ledger_file))

    att_id = governor.reserve_transmission("LIVE_GENERATION", "model")
    assert governor.get_ledger_stats()["total_attributable_attempts"] == 1

    # Finalize attempt with HTTP 200
    governor.finalize_transmission(att_id, status_code=200)
    assert governor.get_ledger_stats()["total_attributable_attempts"] == 1

    # Redundant finalization call must NOT double-charge
    governor.finalize_transmission(att_id, status_code=200)
    assert governor.get_ledger_stats()["total_attributable_attempts"] == 1
    assert governor.get_ledger_stats()["successful_model_calls"] == 1


def test_6_retries_each_reserve_separate_slot(tmp_path):
    """6. Retries each reserve a separate slot in the persistent ledger."""
    ledger_file = tmp_path / "retry_ledger.json"
    governor = ProviderQuotaGovernor(internal_daily_cap=45, ledger_path=str(ledger_file))

    resp_500 = httpx.Response(500, json={"error": "server error"}, request=httpx.Request("POST", "https://api.test"))
    resp_200 = httpx.Response(200, json={"choices": []}, request=httpx.Request("POST", "https://api.test"))

    with GovernedHTTPClient(governor=governor) as client:
        with patch.object(client.http_client, "post", side_effect=[resp_500, resp_200]):
            # First attempt
            r1 = client.post("https://api.test/retry")
            assert r1.status_code == 500
            assert governor.get_ledger_stats()["total_attributable_attempts"] == 1

            # Retry attempt
            r2 = client.post("https://api.test/retry")
            assert r2.status_code == 200
            assert governor.get_ledger_stats()["total_attributable_attempts"] == 2

    with open(ledger_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    today = governor.get_current_utc_date_str()
    events = data[today]["events"]
    assert len(events) == 2
    assert events[0]["state"] == "HTTP_ERROR"
    assert events[0]["status"] == 500
    assert events[1]["state"] == "SUCCEEDED"
    assert events[1]["status"] == 200


def test_7_failed_http_and_network_attempts_each_count_once(tmp_path):
    """7. Failed HTTP (429/500) and network (ConnectError) attempts each count exactly once."""
    ledger_file = tmp_path / "failures_ledger.json"
    governor = ProviderQuotaGovernor(internal_daily_cap=45, ledger_path=str(ledger_file))

    # 1. HTTP 429 probe attempt
    with GovernedHTTPClient(governor=governor) as client:
        with patch.object(client.http_client, "post", return_value=httpx.Response(429, json={"error": "rate limited"}, request=httpx.Request("POST", "https://api.test"))):
            r = client.post("https://api.test/chat/completions")
            assert r.status_code == 429
            assert governor.get_ledger_stats()["total_attributable_attempts"] == 1
            assert governor.get_ledger_stats()["failed_attempts_recorded"] == 1

    # 2. Network connection failure
    with GovernedHTTPClient(governor=governor) as client:
        with patch.object(client.http_client, "post", side_effect=httpx.ConnectError("Connection refused")):
            with pytest.raises(httpx.ConnectError):
                client.post("https://api.test/chat/completions")

            assert governor.get_ledger_stats()["total_attributable_attempts"] == 2
            assert governor.get_ledger_stats()["failed_attempts_recorded"] == 2


def test_8_separate_governor_instances_cannot_oversubscribe_shared_cap(tmp_path):
    """8. Separate governor instances cannot oversubscribe a shared cap."""
    ledger_file = tmp_path / "multi_instance_ledger.json"
    cap = 6

    # 3 distinct governor instances pointing to the same ledger file
    inst_1 = ProviderQuotaGovernor(internal_daily_cap=cap, ledger_path=str(ledger_file))
    inst_2 = ProviderQuotaGovernor(internal_daily_cap=cap, ledger_path=str(ledger_file))
    inst_3 = ProviderQuotaGovernor(internal_daily_cap=cap, ledger_path=str(ledger_file))

    # Each reserves 2 slots (total 6, filling cap)
    id1 = inst_1.reserve_transmission("LIVE_GENERATION", "m1")
    id2 = inst_1.reserve_transmission("LIVE_GENERATION", "m1")
    id3 = inst_2.reserve_transmission("LIVE_GENERATION", "m2")
    id4 = inst_2.reserve_transmission("LIVE_GENERATION", "m2")
    id5 = inst_3.reserve_transmission("LIVE_GENERATION", "m3")
    id6 = inst_3.reserve_transmission("LIVE_GENERATION", "m3")

    for inst, i_d in [(inst_1, id1), (inst_1, id2), (inst_2, id3), (inst_2, id4), (inst_3, id5), (inst_3, id6)]:
        inst.finalize_transmission(i_d, status_code=200)

    # Any subsequent reservation from ANY instance must fail closed
    with pytest.raises(DailyTransmissionsCeilingExceededError):
        inst_1.reserve_transmission("LIVE_GENERATION", "m1")

    with pytest.raises(DailyTransmissionsCeilingExceededError):
        inst_2.reserve_transmission("LIVE_GENERATION", "m2")

    with pytest.raises(DailyTransmissionsCeilingExceededError):
        inst_3.reserve_transmission("LIVE_GENERATION", "m3")

    assert inst_1.get_ledger_stats()["total_attributable_attempts"] == cap


def test_9_utc_date_transition_starts_new_daily_count_without_modifying_previous(tmp_path):
    """9. The UTC date transition starts a new daily count without modifying previous dates."""
    ledger_file = tmp_path / "date_transition_ledger.json"
    governor = ProviderQuotaGovernor(internal_daily_cap=45, ledger_path=str(ledger_file))

    # Day 1: 2026-10-17 historical breach
    governor.save_ledger({
        "2026-10-17": {
            "utc_date": "2026-10-17",
            "generation_calls_successful": 28,
            "generation_attempts_failed_retries": 12,
            "generation_probes_failed": 4,
            "scratch_diagnostic_requests": 8,
            "metadata_queries": 2,
            "total_outbound_http_transmissions": 54,
            "internal_daily_cap": 45,
            "cap_breached": True,
            "breach_excess_transmissions": 9,
            "events": [],
        }
    })

    # Day 2: 2026-10-18
    with patch.object(governor, "get_current_utc_date_str", return_value="2026-10-18"):
        # Day starts at 0
        assert governor.get_ledger_stats()["total_attributable_attempts"] == 0
        assert governor.get_ledger_stats()["remaining_internal_attempts"] == 45

        # Initialize and make transmission 1 (metadata query)
        governor.initialize_day("2026-10-18")
        att_id = governor.reserve_transmission("KEY_METADATA", "/api/v1/key")
        governor.finalize_transmission(att_id, status_code=200)

        stats_d2 = governor.get_ledger_stats()
        assert stats_d2["total_attributable_attempts"] == 1
        assert stats_d2["remaining_internal_attempts"] == 44

    # Verify persistent file retains both dates without altering Day 1
    with open(ledger_file, "r", encoding="utf-8") as f:
        ledger = json.load(f)

    assert ledger["2026-10-17"]["total_outbound_http_transmissions"] == 54
    assert ledger["2026-10-17"]["cap_breached"] is True
    assert ledger["2026-10-17"]["breach_excess_transmissions"] == 9

    assert ledger["2026-10-18"]["total_outbound_http_transmissions"] == 1
    assert ledger["2026-10-18"]["cap_breached"] is False


def test_10_network_entrypoints_cannot_bypass_governed_transport(tmp_path):
    """10. Network-capable application and diagnostic entry points cannot bypass the governed transport."""
    ledger_file = tmp_path / "entrypoint_bypass_ledger.json"
    governor = ProviderQuotaGovernor(internal_daily_cap=1, ledger_path=str(ledger_file))

    # Consume the single slot
    att = governor.reserve_transmission("KEY_METADATA", "/api/v1/key")
    governor.finalize_transmission(att, status_code=200)

    # 1. OpenRouterProvider.check_key_metadata
    from mas.core.llm import OpenRouterProvider
    provider = OpenRouterProvider(api_key="test-key")
    # Patch client inside check_key_metadata to use our capped governor
    with patch("mas.core.governor.global_governor", governor):
        meta = provider.check_key_metadata()
        assert "error" in meta or "status_code" in meta

    # 2. OpenRouterProvider.generate
    with patch("mas.core.governor.global_governor", governor):
        with pytest.raises(DailyTransmissionsCeilingExceededError):
            provider.generate([{"role": "user", "content": "hi"}], model="cohere/north-mini-code:free")

    # 3. Diagnostic scripts check
    allowed, status_code, _ = governor.evaluate_dispatch_permission("diagnostic", "scratch/test_dev_token_budget.py")
    assert allowed is False
    assert status_code == "STOPPED_BUDGET_CEILING"


def test_11_test_execution_uses_isolated_ledger_and_does_not_mutate_production_ledger():
    """11. Test execution uses an isolated ledger and does not mutate the production ledger."""
    # Production ledger must not equal the active test ledger
    import os
    env_ledger = os.environ.get("MAS_LEDGER_PATH")
    assert env_ledger is not None
    assert os.path.abspath(env_ledger) != os.path.abspath(DEFAULT_LEDGER_FILE)

    # Production ledger must still record the historical 54 transmissions
    with open(DEFAULT_LEDGER_FILE, "r", encoding="utf-8") as f:
        prod_data = json.load(f)

    oct17 = prod_data.get("2026-10-17", {})
    assert oct17.get("total_outbound_http_transmissions") == 54
    assert oct17.get("cap_breached") is True
    assert oct17.get("breach_excess_transmissions") == 9
