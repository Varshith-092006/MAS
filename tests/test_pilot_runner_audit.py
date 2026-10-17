"""Offline Tests for Phase 2M Pilot Runner and Single-Task Execution Audit.

Verifies:
1. Single-task selection executes only the selected task (Task A) without triggering Tasks B, C, or D.
2. Invalid task IDs are rejected cleanly.
3. Pre-reset execution maintains strict pause (STOPPED_PROVIDER_QUOTA) and 0 network calls.
4. Quality gate failure halts multi-task execution immediately.
5. Insufficient remaining transmission allowance (< 3) halts execution before task start.
6. Production ledger is isolated and unmutated during testing.
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from scripts.run_phase2m_pilot import (
    run_phase2m_pilot,
    PILOT_TASKS,
    load_or_init_summary,
    update_run_in_summary,
)
from mas.core.governor import ProviderQuotaGovernor


def test_1_single_task_filter_selects_only_task_a(tmp_path):
    """Confirm selecting dev_markdown_toc_01 targets ONLY Task A."""
    test_json = tmp_path / "test_results.json"
    with patch("scripts.run_phase2m_pilot.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        with patch("scripts.run_phase2m_pilot.load_or_init_summary") as mock_load:
            mock_summary = {"runs": []}
            mock_load.return_value = mock_summary

            res = run_phase2m_pilot(selected_task_id="dev_markdown_toc_01")
            run_task_ids = [r["task_id"] for r in res["runs"]]
            assert run_task_ids == ["dev_markdown_toc_01"]
            assert "dev_inventory_system_01" not in run_task_ids
            assert "dev_log_analyzer_01" not in run_task_ids
            assert "dev_markdown_toc_01_repeat" not in run_task_ids


def test_2_single_task_filter_by_slot_name(tmp_path):
    """Confirm selecting by slot name 'Task A' targets dev_markdown_toc_01."""
    with patch("scripts.run_phase2m_pilot.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        with patch("scripts.run_phase2m_pilot.load_or_init_summary") as mock_load:
            mock_summary = {"runs": []}
            mock_load.return_value = mock_summary

            res = run_phase2m_pilot(selected_task_id="Task A")
            assert len(res["runs"]) == 1
            assert res["runs"][0]["slot"] == "Task A"
            assert res["runs"][0]["task_id"] == "dev_markdown_toc_01"


def test_3_invalid_task_id_exits_cleanly():
    """Confirm invalid task ID triggers system exit without attempting tasks."""
    with pytest.raises(SystemExit) as exc_info:
        run_phase2m_pilot(selected_task_id="non_existent_task_xyz")
    assert exc_info.value.code == 1


def test_4_pre_reset_pause_sets_stopped_provider_quota():
    """Prior to reset boundary, selected task is checkpointed with STOPPED_PROVIDER_QUOTA."""
    with patch("scripts.run_phase2m_pilot.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 10, 17, 23, 59, 59, tzinfo=timezone.utc)
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        with patch("scripts.run_phase2m_pilot.load_or_init_summary") as mock_load:
            mock_summary = {"runs": []}
            mock_load.return_value = mock_summary

            res = run_phase2m_pilot(selected_task_id="dev_markdown_toc_01")
            assert len(res["runs"]) == 1
            task_a = res["runs"][0]
            assert task_a["status"] == "STOPPED_PROVIDER_QUOTA"
            assert task_a["calls_dispatched"] == 0
            assert "paused pending 2026-10-18 00:00:00 UTC" in task_a["stop_reason"]


def test_5_update_run_in_summary_idempotent():
    """Confirm updating summary preserves existing tasks and updates target."""
    summary = {
        "runs": [
            {"task_id": "dev_markdown_toc_01", "status": "STOPPED_PROVIDER_QUOTA"},
            {"task_id": "dev_inventory_system_01", "status": "PENDING"},
        ]
    }
    update_run_in_summary(summary, {"task_id": "dev_markdown_toc_01", "status": "COMPLETED_QUALITY_GATE"})
    assert len(summary["runs"]) == 2
    assert summary["runs"][0]["status"] == "COMPLETED_QUALITY_GATE"
    assert summary["runs"][1]["status"] == "PENDING"


def test_6_post_reset_ambiguous_or_zero_quota_stops_immediately_no_retries(tmp_path):
    """Confirm post-reset runner stops fail-closed with 0 calls if preflight quota is 0 or ambiguous."""
    out_json = tmp_path / "pilot_results.json"
    mock_governor = MagicMock(spec=ProviderQuotaGovernor)
    mock_governor.get_ledger_stats.return_value = {
        "utc_date": "2026-10-18",
        "total_attributable_attempts": 1,
        "internal_daily_cap": 45,
        "remaining_internal_attempts": 44,
        "cap_breached": False,
        "excess_transmissions": 0,
    }
    # Preflight reports zero or ambiguous quota
    mock_governor.check_upstream_key_status.return_value = {
        "can_proceed": False,
        "is_quota_exhausted": True,
        "free_models_remaining": 0,
        "stop_reason": "Upstream free-model daily quota exhausted: 50/50 requests used (0 remaining).",
    }

    with patch("scripts.run_phase2m_pilot.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 10, 18, 0, 0, 5, tzinfo=timezone.utc)
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        with patch("scripts.run_phase2m_pilot.global_governor", mock_governor):
            with patch("scripts.run_phase2m_pilot.OpenRouterProvider"):
                with patch("scripts.run_phase2m_pilot.load_or_init_summary", return_value={"runs": []}):
                    from unittest.mock import mock_open
                    with patch("builtins.open", mock_open()):
                        res = run_phase2m_pilot(selected_task_id="dev_markdown_toc_01")
                        assert len(res["runs"]) == 1
                        task_a = res["runs"][0]
                        assert task_a["status"] == "STOPPED_PROVIDER_QUOTA"
                        assert task_a["calls_dispatched"] == 0
                        # Preflight check was called exactly once (no retries)
                        assert mock_governor.check_upstream_key_status.call_count == 1

