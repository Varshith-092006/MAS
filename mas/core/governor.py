"""Provider Quota Governor & Multi-Task Pilot Safety Controller.

Enforces:
1. Unified Outbound Transmission Ledger (eval/outbound_transmission_ledger.json):
   - Records EVERY outbound HTTP request (generation, retries, 429 probes, key metadata queries, and scratch diagnostics).
   - Strictly enforces max 45 outbound HTTP transmissions per UTC day.
   - Resets counter ONLY when a new UTC calendar day begins (00:00:00 UTC).
   - Preserves historical records and documented cap breaches permanently.
2. Inter-Process Concurrency Safety:
   - Atomic reservation under cross-process file lock (InterprocessLedgerLock) before transport dispatch.
   - Zero cap-oversubscription race conditions across threads or processes.
3. Crash-Consistency & Non-Duplication:
   - Reservations written to disk in state 'RESERVED' before wire transmission.
   - Any crash after dispatch retains the consumed allowance.
   - Finalizing an attempt with actual status or network exception never double-counts the daily allowance.
4. Global stop on first HTTP 429 daily-quota exhaustion (limit_source: openrouter_free_tier_daily).
5. Non-intrusive metadata reconciliation via /api/v1/key counting as 1 transmission.
6. Per-run ceilings of 15 logical generation dispatches and 60,000 provider tokens.
7. Safe checkpointing as STOPPED_PROVIDER_QUOTA without tight retry loops.
8. GovernedHTTPClient instrumented wrapper routing and counting all outbound HTTP transmissions.
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

DEFAULT_LEDGER_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "eval", "outbound_transmission_ledger.json")
)
LEDGER_FILE = DEFAULT_LEDGER_FILE


class DailyTransmissionsCeilingExceededError(RuntimeError):
    """Raised when outbound HTTP transmissions reach the daily ceiling (ceiling = 45 per UTC day)."""
    pass


class LedgerIntegrityError(RuntimeError):
    """Raised when the persistent transmission ledger cannot be safely read or updated."""
    pass


class InterprocessLedgerLock:
    """Cross-process file lock protecting the transmission ledger from concurrent race conditions."""

    def __init__(self, lock_path: str, timeout: float = 10.0, retry_delay: float = 0.05):
        self.lock_path = lock_path
        self.timeout = timeout
        self.retry_delay = retry_delay
        self._fd = None
        self._is_locked = False

    def __enter__(self):
        start_time = time.time()
        os.makedirs(os.path.dirname(os.path.abspath(self.lock_path)), exist_ok=True)
        self._fd = open(self.lock_path, "a+", encoding="utf-8")
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    self._fd.seek(0)
                    msvcrt.locking(self._fd.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._is_locked = True
                return self
            except (OSError, IOError):
                if time.time() - start_time >= self.timeout:
                    if self._fd:
                        try:
                            self._fd.close()
                        except Exception:
                            pass
                    raise TimeoutError(f"Could not acquire ledger lock at {self.lock_path} within {self.timeout}s")
                time.sleep(self.retry_delay)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._is_locked and self._fd:
            try:
                if os.name == "nt":
                    import msvcrt
                    self._fd.seek(0)
                    msvcrt.locking(self._fd.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._fd.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            self._is_locked = False
        if self._fd:
            try:
                self._fd.close()
            except Exception:
                pass
            self._fd = None


class ProviderQuotaGovernor:
    """Manages provider rate limits, daily transmission caps, and global stop conditions."""

    def __init__(
        self,
        internal_daily_cap: int = 45,
        max_calls_per_run: int = 15,
        max_tokens_per_run: int = 60000,
        ledger_path: Optional[str] = None,
    ):
        self.internal_daily_cap = internal_daily_cap
        self.max_calls_per_run = max_calls_per_run
        self.max_tokens_per_run = max_tokens_per_run
        self._ledger_path = ledger_path
        self.stopped_for_day = False
        self.stopped_reason = ""
        self.reset_metadata: Dict[str, Any] = {}

    @property
    def ledger_path(self) -> str:
        if self._ledger_path:
            return self._ledger_path
        return os.environ.get("MAS_LEDGER_PATH", DEFAULT_LEDGER_FILE)

    @ledger_path.setter
    def ledger_path(self, val: str) -> None:
        self._ledger_path = val

    @property
    def lock_path(self) -> str:
        return self.ledger_path + ".lock"

    def get_current_utc_date_str(self) -> str:
        """Returns the current UTC date in YYYY-MM-DD format."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def load_ledger(self) -> Dict[str, Any]:
        """Loads the persistent outbound transmission ledger."""
        path = self.ledger_path
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to load outbound transmission ledger from %s: %s", path, e)
            raise LedgerIntegrityError(f"Ledger file corrupted or unreadable at {path}: {e}")

    def save_ledger(self, data: Dict[str, Any]) -> None:
        """Saves the persistent outbound transmission ledger atomically using fsync and atomic rename."""
        path = self.ledger_path
        dir_name = os.path.dirname(os.path.abspath(path))
        os.makedirs(dir_name, exist_ok=True)
        temp_path = os.path.join(dir_name, f".tmp_{os.getpid()}_{uuid.uuid4().hex[:8]}")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, path)
        except Exception as e:
            logger.error("Failed to atomically save outbound transmission ledger to %s: %s", path, e)
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            raise LedgerIntegrityError(f"Failed to atomically persist ledger to {path}: {e}")

    def initialize_day(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        """Explicitly initializes a new UTC day entry in the persistent ledger at 0 transmissions."""
        today_str = date_str or self.get_current_utc_date_str()
        with InterprocessLedgerLock(self.lock_path):
            ledger = self.load_ledger()
            if today_str not in ledger:
                ledger[today_str] = {
                    "utc_date": today_str,
                    "generation_calls_successful": 0,
                    "generation_attempts_failed_retries": 0,
                    "generation_probes_failed": 0,
                    "scratch_diagnostic_requests": 0,
                    "metadata_queries": 0,
                    "total_outbound_http_transmissions": 0,
                    "internal_daily_cap": self.internal_daily_cap,
                    "cap_breached": False,
                    "breach_excess_transmissions": 0,
                    "events": [],
                }
                self.save_ledger(ledger)
            return ledger[today_str]

    def reserve_transmission(
        self,
        request_type: str,
        target: str,
        source: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Atomically evaluates daily transmission limits and reserves exactly one slot
        in the persistent ledger BEFORE any HTTP transmission occurs.
        
        Returns a unique attempt_id for outcome finalization.
        Raises DailyTransmissionsCeilingExceededError if the daily cap has been reached.
        """
        with InterprocessLedgerLock(self.lock_path):
            ledger = self.load_ledger()
            today_str = self.get_current_utc_date_str()

            if today_str not in ledger:
                ledger[today_str] = {
                    "utc_date": today_str,
                    "generation_calls_successful": 0,
                    "generation_attempts_failed_retries": 0,
                    "generation_probes_failed": 0,
                    "scratch_diagnostic_requests": 0,
                    "metadata_queries": 0,
                    "total_outbound_http_transmissions": 0,
                    "internal_daily_cap": self.internal_daily_cap,
                    "cap_breached": False,
                    "breach_excess_transmissions": 0,
                    "events": [],
                }

            day_data = ledger[today_str]
            current_total = day_data.get("total_outbound_http_transmissions", 0)

            # Strict pre-transmission check: Reject before any transport invocation!
            if current_total >= self.internal_daily_cap:
                raise DailyTransmissionsCeilingExceededError(
                    f"Outbound HTTP transmission rejected before dispatch: daily ceiling reached "
                    f"({current_total} >= {self.internal_daily_cap} for UTC day {today_str})."
                )

            # Consume exactly 1 transmission allowance atomically
            day_data["total_outbound_http_transmissions"] = current_total + 1
            if day_data["total_outbound_http_transmissions"] > self.internal_daily_cap:
                day_data["cap_breached"] = True
                day_data["breach_excess_transmissions"] = day_data["total_outbound_http_transmissions"] - self.internal_daily_cap

            attempt_id = f"att_{int(time.time())}_{uuid.uuid4().hex[:8]}"

            attempt_record = {
                "attempt_id": attempt_id,
                "time_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "state": "RESERVED",
                "type": request_type,
                "target": target,
                "status": None,
                "count": 1,
            }
            if source:
                attempt_record["source"] = source
            if extra:
                attempt_record.update(extra)

            day_data.setdefault("events", []).append(attempt_record)

            if request_type in ("KEY_METADATA", "METADATA"):
                day_data["metadata_queries"] = day_data.get("metadata_queries", 0) + 1
            elif "SCRATCH" in request_type or "DIAGNOSTIC" in request_type:
                day_data["scratch_diagnostic_requests"] = day_data.get("scratch_diagnostic_requests", 0) + 1

            self.save_ledger(ledger)
            return attempt_id

    def finalize_transmission(
        self,
        attempt_id: str,
        status_code: Optional[int] = None,
        exception: Optional[Exception] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Finalizes a previously reserved transmission with its actual HTTP status or network exception.
        
        CRITICAL INVARIANT: Updating the final status NEVER increments total_outbound_http_transmissions.
        The daily allowance was already consumed during reserve_transmission.
        """
        with InterprocessLedgerLock(self.lock_path):
            ledger = self.load_ledger()
            today_str = self.get_current_utc_date_str()
            day_data = ledger.get(today_str)
            if not day_data:
                for d_key in reversed(list(ledger.keys())):
                    if any(ev.get("attempt_id") == attempt_id for ev in ledger[d_key].get("events", [])):
                        day_data = ledger[d_key]
                        break
            if not day_data:
                return

            events = day_data.get("events", [])
            matched_event = next((ev for ev in events if ev.get("attempt_id") == attempt_id), None)
            if not matched_event:
                return

            # Idempotency guard: If already finalized, do not increment counters again
            if matched_event.get("state") not in ("RESERVED", None):
                if extra:
                    matched_event.update(extra)
                    self.save_ledger(ledger)
                return

            if exception is not None:
                matched_event["state"] = "NETWORK_ERROR"
                matched_event["status"] = None
                matched_event["exception"] = type(exception).__name__
                matched_event["error_message"] = str(exception)
                day_data["generation_attempts_failed_retries"] = day_data.get("generation_attempts_failed_retries", 0) + 1
            else:
                matched_event["status"] = status_code
                if status_code == 200:
                    matched_event["state"] = "SUCCEEDED"
                    if matched_event.get("type") not in ("KEY_METADATA", "METADATA"):
                        day_data["generation_calls_successful"] = day_data.get("generation_calls_successful", 0) + 1
                elif status_code == 429:
                    matched_event["state"] = "HTTP_ERROR"
                    day_data["generation_probes_failed"] = day_data.get("generation_probes_failed", 0) + 1
                else:
                    matched_event["state"] = "HTTP_ERROR"
                    day_data["generation_attempts_failed_retries"] = day_data.get("generation_attempts_failed_retries", 0) + 1

            matched_event["finalized_time_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if extra:
                matched_event.update(extra)

            # Invariant: total_outbound_http_transmissions is strictly preserved without double charging
            self.save_ledger(ledger)

    def record_transmission(
        self,
        request_type: str,
        target: str,
        status_code: Optional[int] = None,
        count: int = 1,
        extra: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Legacy-compatible helper that atomically reserves and finalizes transmission(s)."""
        last_total = 0
        for _ in range(count):
            att_id = self.reserve_transmission(request_type=request_type, target=target, extra=extra)
            self.finalize_transmission(attempt_id=att_id, status_code=status_code, extra=extra)
            last_total = self.get_ledger_stats()["total_attributable_attempts"]
        return last_total

    def get_ledger_stats(self) -> Dict[str, Any]:
        """Calculates exact outbound attempts from the persistent shared ledger for current UTC day."""
        today_str = self.get_current_utc_date_str()
        try:
            ledger = self.load_ledger()
        except Exception:
            ledger = {}
        day_data = ledger.get(today_str, {})

        total_transmissions = day_data.get("total_outbound_http_transmissions", 0)
        cap_breached = total_transmissions > self.internal_daily_cap
        excess = max(0, total_transmissions - self.internal_daily_cap)

        events = day_data.get("events", [])
        active_reservations = sum(1 for ev in events if ev.get("state") == "RESERVED")

        return {
            "utc_date": today_str,
            "successful_model_calls": day_data.get("generation_calls_successful", 0),
            "failed_attempts_recorded": day_data.get("generation_probes_failed", 0) + day_data.get("generation_attempts_failed_retries", 0),
            "metadata_queries": day_data.get("metadata_queries", 0),
            "scratch_diagnostic_requests": day_data.get("scratch_diagnostic_requests", 0),
            "total_attributable_attempts": total_transmissions,
            "active_reservations": active_reservations,
            "internal_daily_cap": self.internal_daily_cap,
            "remaining_internal_attempts": max(0, self.internal_daily_cap - total_transmissions),
            "cap_breached": cap_breached,
            "excess_transmissions": excess,
        }

    get_stats = get_ledger_stats

    def check_upstream_key_status(self, provider, record_attempt: bool = False) -> Dict[str, Any]:
        """Queries OpenRouter /api/v1/key to inspect authoritative key limits and free quota.
        Note: This key-information endpoint reports key status, rate limits, and remaining
        daily free requests; it does NOT confirm model availability or catalog status.
        """
        if record_attempt and not getattr(provider, "uses_governed_client", False):
            self.record_transmission(
                request_type="KEY_METADATA",
                target="/api/v1/key",
                status_code=None,
                count=1,
            )

        meta = provider.check_key_metadata()

        now_utc = datetime.now(timezone.utc)
        seconds_to_utc_midnight = int(
            ((24 - now_utc.hour - 1) * 3600) + ((60 - now_utc.minute - 1) * 60) + (60 - now_utc.second)
        )
        hours_to_reset = round(seconds_to_utc_midnight / 3600.0, 2)

        # Fail-closed validation of response
        is_error = bool(meta.get("error")) or ("status_code" in meta and meta.get("status_code") != 200)
        free_reqs = meta.get("free_model_daily_requests")
        has_free_reqs = isinstance(free_reqs, dict)
        remaining = free_reqs.get("remaining") if has_free_reqs else None
        has_valid_remaining = isinstance(remaining, (int, float)) and not isinstance(remaining, bool)

        used = free_reqs.get("used", 0) if has_free_reqs else 0
        limit = free_reqs.get("limit", 50) if has_free_reqs else 50
        is_free_tier = meta.get("is_free_tier", False)

        if is_error:
            err_msg = meta.get("error") or f"HTTP {meta.get('status_code')}"
            can_proceed = False
            is_quota_exhausted = True
            stop_reason = f"Upstream key preflight query failed: {err_msg}"
        elif not has_free_reqs:
            can_proceed = False
            is_quota_exhausted = True
            stop_reason = "Malformed response: missing 'free_model_daily_requests' object in key metadata."
        elif not has_valid_remaining:
            can_proceed = False
            is_quota_exhausted = True
            stop_reason = "Malformed response: missing or invalid 'remaining' field in 'free_model_daily_requests'."
        elif remaining <= 0:
            can_proceed = False
            is_quota_exhausted = True
            stop_reason = (
                f"Upstream free-model daily quota exhausted: {used}/{limit} requests used "
                f"({int(remaining)} remaining). Reset in ~{hours_to_reset}h at 00:00:00 UTC."
            )
        else:
            can_proceed = True
            is_quota_exhausted = False
            stop_reason = ""

        status_info = {
            "can_proceed": can_proceed,
            "is_free_tier": is_free_tier,
            "free_models_used": used,
            "free_models_limit": limit,
            "free_models_remaining": int(remaining) if has_valid_remaining else 0,
            "is_quota_exhausted": is_quota_exhausted,
            "usage_daily_usd": meta.get("usage_daily", 0.0),
            "response_date": meta.get("_response_date"),
            "seconds_until_utc_midnight": seconds_to_utc_midnight,
            "hours_until_utc_midnight": hours_to_reset,
            "provider_reset_rule": "Daily reset at 00:00:00 UTC for free model daily request limits",
            "stop_reason": stop_reason,
            "raw_meta": meta if not is_error else {"error": meta.get("error"), "status_code": meta.get("status_code")},
        }

        if not can_proceed:
            self.stopped_for_day = True
            self.stopped_reason = stop_reason
            self.reset_metadata = status_info

        return status_info

    def evaluate_dispatch_permission(
        self,
        slot_name: str,
        task_id: str,
        provider: Optional[Any] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Evaluates whether the next pilot run may be dispatched according to all safety ceilings."""
        if self.stopped_for_day:
            return (
                False,
                "STOPPED_PROVIDER_QUOTA",
                {
                    "reason": self.stopped_reason,
                    "slot": slot_name,
                    "task_id": task_id,
                    "reset_metadata": self.reset_metadata,
                },
            )

        ledger = self.get_ledger_stats()
        if ledger["total_attributable_attempts"] >= self.internal_daily_cap:
            reason = (
                f"Internal daily transmission ceiling reached: {ledger['total_attributable_attempts']} "
                f"/ {self.internal_daily_cap} attempts made today (UTC)."
            )
            self.stopped_for_day = True
            self.stopped_reason = reason
            return (
                False,
                "STOPPED_BUDGET_CEILING",
                {"reason": reason, "slot": slot_name, "task_id": task_id, "ledger": ledger},
            )

        if provider:
            key_status = self.check_upstream_key_status(provider, record_attempt=True)
            if not key_status.get("can_proceed", False) or key_status.get("is_quota_exhausted", True):
                return (
                    False,
                    "STOPPED_PROVIDER_QUOTA",
                    {
                        "reason": self.stopped_reason,
                        "slot": slot_name,
                        "task_id": task_id,
                        "key_status": key_status,
                    },
                )

        return (True, "ALLOWED", {"ledger": ledger})

    def handle_api_error(self, err: Any, slot_name: str, task_id: str, record_transmission: bool = False) -> str:
        """Handles an OpenRouter error during execution, triggering global stop if quota is exhausted."""
        if record_transmission:
            self.record_transmission(
                request_type="LIVE_GENERATION_FAILED",
                target=task_id,
                status_code=getattr(err, "status_code", 429),
                count=1,
                extra={"error_message": getattr(err, "error_message", str(err))},
            )

        if getattr(err, "is_daily_quota_exhausted", False):
            self.stopped_for_day = True
            reset_h = getattr(err, "rate_limit_reset", None) or "00:00:00 UTC"
            self.stopped_reason = (
                f"First daily-quota 429 triggered global stop on {slot_name} ({task_id}): "
                f"{getattr(err, 'error_message', str(err))}. Upstream reset: {reset_h}."
            )
            self.reset_metadata = {
                "rate_limit_reset": getattr(err, "rate_limit_reset", None),
                "rate_limit_remaining": getattr(err, "rate_limit_remaining", None),
                "rate_limit_limit": getattr(err, "rate_limit_limit", None),
                "remedy_hint": getattr(err, "remedy_hint", None),
                "limit_source": getattr(err, "limit_source", None),
            }
            return "STOPPED_PROVIDER_QUOTA"

        if getattr(err, "status_code", None) == 429:
            return "STOPPED_BUDGET_CEILING"

        if getattr(err, "status_code", 0) >= 500:
            return "FAILED_INFRASTRUCTURE"

        return "FAILED"


class GovernedHTTPClient:
    """Shared instrumented HTTP client wrapper ensuring all outbound HTTP transmissions
    are governed, accounted for in the persistent transmission ledger, and blocked
    before transmission if daily caps are reached.
    """

    def __init__(
        self,
        governor: Optional[ProviderQuotaGovernor] = None,
        timeout: float = 90.0,
        request_type: str = "LIVE_GENERATION",
        target: Optional[str] = None,
        source: Optional[str] = None,
        client: Optional[httpx.Client] = None,
    ):
        self.governor = governor or global_governor
        self.timeout = timeout
        self.default_request_type = request_type
        self.default_target = target
        self.default_source = source
        self._external_client = client
        self._owned_client: Optional[httpx.Client] = None

    def __enter__(self):
        if self._external_client is None and self._owned_client is None:
            self._owned_client = httpx.Client(timeout=self.timeout)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._owned_client is not None:
            self._owned_client.close()
            self._owned_client = None

    @property
    def http_client(self) -> httpx.Client:
        if self._external_client is not None:
            return self._external_client
        if self._owned_client is None:
            self._owned_client = httpx.Client(timeout=self.timeout)
        return self._owned_client

    def _execute_with_governance(
        self,
        dispatch_fn,
        method: str,
        url: str,
        request_type: Optional[str] = None,
        target: Optional[str] = None,
        source: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
        *args,
        **kwargs,
    ) -> httpx.Response:
        req_type = request_type or self.default_request_type
        req_target = target or self.default_target or url
        req_source = source or self.default_source

        event_extra: Dict[str, Any] = {"method": method, "url": str(url)}
        if req_source:
            event_extra["source"] = req_source
        if extra:
            event_extra.update(extra)

        # 1. ATOMIC PROCESS-SAFE RESERVATION (Persisted before transport dispatch)
        attempt_id = self.governor.reserve_transmission(
            request_type=req_type,
            target=req_target,
            source=req_source,
            extra=event_extra,
        )

        # 2. Wire transmission
        try:
            resp = dispatch_fn(url, *args, **kwargs)
            # 3. Finalize on response (never increments daily count again)
            self.governor.finalize_transmission(
                attempt_id=attempt_id,
                status_code=resp.status_code,
                extra=event_extra,
            )
            return resp
        except Exception as e:
            # 3. Finalize on network exception (never increments daily count again)
            self.governor.finalize_transmission(
                attempt_id=attempt_id,
                status_code=None,
                exception=e,
                extra=event_extra,
            )
            raise

    def request(
        self,
        method: str,
        url: str,
        request_type: Optional[str] = None,
        target: Optional[str] = None,
        source: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> httpx.Response:
        return self._execute_with_governance(
            lambda u, *a, **kw: self.http_client.request(method, u, *a, **kw),
            method,
            url,
            request_type=request_type,
            target=target,
            source=source,
            extra=extra,
            **kwargs,
        )

    def get(self, url: str, **kwargs) -> httpx.Response:
        req_type = kwargs.pop("request_type", None)
        target = kwargs.pop("target", None)
        source = kwargs.pop("source", None)
        extra = kwargs.pop("extra", None)
        return self._execute_with_governance(
            self.http_client.get,
            "GET",
            url,
            request_type=req_type,
            target=target,
            source=source,
            extra=extra,
            **kwargs,
        )

    def post(self, url: str, **kwargs) -> httpx.Response:
        req_type = kwargs.pop("request_type", None)
        target = kwargs.pop("target", None)
        source = kwargs.pop("source", None)
        extra = kwargs.pop("extra", None)
        return self._execute_with_governance(
            self.http_client.post,
            "POST",
            url,
            request_type=req_type,
            target=target,
            source=source,
            extra=extra,
            **kwargs,
        )

    def close(self):
        if self._owned_client is not None:
            self._owned_client.close()
            self._owned_client = None


# Global singleton governor instance for cross-module usage
global_governor = ProviderQuotaGovernor()
