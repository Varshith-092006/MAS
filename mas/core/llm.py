"""LLM Provider abstraction, ModelResult, and Token Logger."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import json
import logging
import os
import re
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

import httpx
from pydantic import BaseModel
from mas.db.models import ModelCall
from mas.db.session import get_session

logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Pricing per million tokens (USD)
PRICING_CATALOG = {
    # OpenRouter Free Models ($0.00 / token)
    "openrouter/free": {"input": 0.0, "output": 0.0},
    "meta-llama/llama-3.3-70b-instruct:free": {"input": 0.0, "output": 0.0},
    "meta-llama/llama-3.1-8b-instruct:free": {"input": 0.0, "output": 0.0},
    "qwen/qwen-2.5-coder-32b-instruct:free": {"input": 0.0, "output": 0.0},
    "google/gemma-4-31b-it:free": {"input": 0.0, "output": 0.0},
    "google/gemma-4-26b-a4b-it:free": {"input": 0.0, "output": 0.0},
    "google/gemini-2.0-flash-exp:free": {"input": 0.0, "output": 0.0},
    "deepseek/deepseek-r1:free": {"input": 0.0, "output": 0.0},
    "cohere/north-mini-code:free": {"input": 0.0, "output": 0.0},
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free": {"input": 0.0, "output": 0.0},

    # OpenRouter Paid Models
    "openai/gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
    "openai/gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
    "openai/gpt-3.5-turbo": {"input": 0.50 / 1_000_000, "output": 1.50 / 1_000_000},
    "openai/gpt-3.5-turbo-16k": {"input": 3.00 / 1_000_000, "output": 4.00 / 1_000_000},
    "gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
    "gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
    "gpt-3.5-turbo": {"input": 0.50 / 1_000_000, "output": 1.50 / 1_000_000},
    "gpt-3.5-turbo-16k": {"input": 3.00 / 1_000_000, "output": 4.00 / 1_000_000},
    "anthropic/claude-3.5-sonnet": {"input": 3.00 / 1_000_000, "output": 15.00 / 1_000_000},
    "fake": {"input": 0.0, "output": 0.0},
}


def resolve_openrouter_model(model: Optional[str]) -> str:
    """Normalizes and maps shorthand model identifiers to OpenRouter model IDs."""
    import os
    if not model or model.lower() in ("default", "main"):
        return os.environ.get("OPENROUTER_MODEL", "openrouter/free")
    mapping = {
        "gpt-4o": "openai/gpt-4o",
        "gpt-4o-mini": "openai/gpt-4o-mini",
        "gpt-3.5-turbo": "openai/gpt-3.5-turbo",
        "gpt-3.5-turbo-16k": "openai/gpt-3.5-turbo-16k",
        "claude-3-5-sonnet": "anthropic/claude-3.5-sonnet",
        "claude-3.5-sonnet": "anthropic/claude-3.5-sonnet",
        "llama-3.3-70b": "meta-llama/llama-3.3-70b-instruct:free",
        "llama-3.1-8b": "meta-llama/llama-3.1-8b-instruct:free",
        "qwen-2.5-coder": "qwen/qwen-2.5-coder-32b-instruct:free",
        "gemini-2.0-flash": "google/gemini-2.0-flash-exp:free",
        "cohere/north-mini-code:free": "cohere/north-mini-code:free",
        "north-mini-code": "cohere/north-mini-code:free",
        "free": "openrouter/free",
    }
    return mapping.get(model.lower(), model)


def redact_sensitive_string(val: str, api_key: Optional[str] = None) -> str:
    """Redacts API keys, Bearer tokens, and secrets from strings."""
    if not val:
        return ""
    if api_key and len(api_key) > 5:
        val = val.replace(api_key, "[REDACTED_API_KEY]")
    val = re.sub(r'(Bearer\s+)[A-Za-z0-9_\-\.]+', r'\1[REDACTED_TOKEN]', val)
    val = re.sub(r'sk-[a-zA-Z0-9_\-\.]{10,}', r'[REDACTED_KEY]', val)
    return val


def sanitize_headers_dict(headers_mapping: Any) -> Dict[str, str]:
    """Extracts headers into a dict while redacting sensitive headers."""
    sanitized: Dict[str, str] = {}
    if not headers_mapping:
        return sanitized
    sensitive_keys = {"authorization", "cookie", "set-cookie", "api-key", "x-api-key", "token"}
    for k, v in headers_mapping.items():
        k_str = str(k)
        if k_str.lower() in sensitive_keys or "auth" in k_str.lower() or "secret" in k_str.lower():
            sanitized[k_str] = "[REDACTED]"
        else:
            sanitized[k_str] = redact_sensitive_string(str(v))
    return sanitized


class OpenRouterAPIError(RuntimeError):
    """Preserves upstream OpenRouter HTTP error status code, diagnostic JSON fields, and response headers."""

    def __init__(
        self,
        status_code: int,
        message: str,
        error_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        raw_body: Optional[str] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.error_data = error_data or {}
        self.headers = sanitize_headers_dict(headers)
        self.raw_body = raw_body

        err_obj = self.error_data.get("error") if isinstance(self.error_data.get("error"), dict) else {}
        metadata = err_obj.get("metadata") if isinstance(err_obj.get("metadata"), dict) else {}

        self.error_message = err_obj.get("message") or (str(err_obj) if err_obj else None)
        self.reason = metadata.get("reason")
        self.limit_source = metadata.get("limit_source")
        self.remedy_hint = metadata.get("remedy_hint")
        self.retry_after = self.get_header("retry-after")
        self.rate_limit_reset = self.get_header("x-ratelimit-reset")
        self.rate_limit_remaining = self.get_header("x-ratelimit-remaining")
        self.rate_limit_limit = self.get_header("x-ratelimit-limit")

    @property
    def is_daily_quota_exhausted(self) -> bool:
        """Determines if the error represents exhausted account-level free model daily quota."""
        if self.status_code == 429:
            ls = (self.limit_source or "").lower()
            msg = (self.error_message or "").lower()
            rem = (self.remedy_hint or "").lower()
            if "free_tier_daily" in ls or "free-models-per-day" in msg or "daily reset" in rem:
                return True
        return False

    def get_header(self, header_name: str, default: Optional[str] = None) -> Optional[str]:
        """Case-insensitive lookup for headers."""
        target = header_name.lower()
        for k, v in self.headers.items():
            if k.lower() == target:
                return v
        return default


class ModelMismatchError(RuntimeError):
    """Raised when provider serves a model different from the requested research condition."""
    pass


VERIFIED_MODEL_SNAPSHOTS: Dict[str, Set[str]] = {
    "openai/gpt-4o": {
        "openai/gpt-4o",
        "openai/gpt-4o-2024-05-13",
        "openai/gpt-4o-2024-08-06",
        "openai/gpt-4o-2024-11-20",
    },
    "openai/gpt-4o-mini": {
        "openai/gpt-4o-mini",
        "openai/gpt-4o-mini-2024-07-18",
    },
    "openai/gpt-3.5-turbo": {
        "openai/gpt-3.5-turbo",
        "openai/gpt-3.5-turbo-0125",
        "openai/gpt-3.5-turbo-1106",
        "openai/gpt-3.5-turbo-0613",
    },
    "openai/gpt-3.5-turbo-16k": {
        "openai/gpt-3.5-turbo-16k",
        "openai/gpt-3.5-turbo-16k-0613",
    },
    "anthropic/claude-3.5-sonnet": {
        "anthropic/claude-3.5-sonnet",
        "anthropic/claude-3.5-sonnet-20240620",
        "anthropic/claude-3.5-sonnet-20241022",
    },
    "meta-llama/llama-3.3-70b-instruct:free": {
        "meta-llama/llama-3.3-70b-instruct:free",
    },
    "meta-llama/llama-3.1-8b-instruct:free": {
        "meta-llama/llama-3.1-8b-instruct:free",
    },
    "qwen/qwen-2.5-coder-32b-instruct:free": {
        "qwen/qwen-2.5-coder-32b-instruct:free",
    },
    "google/gemini-2.0-flash-exp:free": {
        "google/gemini-2.0-flash-exp:free",
    },
    "cohere/north-mini-code:free": {
        "cohere/north-mini-code:free",
    },
    "openrouter/free": {
        "openrouter/free",
    },
    "fake": {
        "fake",
    },
}


def is_model_match(requested_model: Optional[str], actual_model: Optional[str]) -> bool:
    """Verifies that the actual model returned by the provider matches the requested condition.
    
    Uses an explicit allowlist of verified canonical models and documented dated snapshots.
    Rejects prefix substring matches, unverified variants (audio, realtime, search-preview, instruct),
    and free-tier substitution.
    """
    if not requested_model or not actual_model:
        return False
    r = requested_model.strip().lower()
    a = actual_model.strip().lower()
    if r == a:
        return True

    r_canon = resolve_openrouter_model(r).lower()
    a_canon = resolve_openrouter_model(a).lower()
    if r_canon == a_canon:
        return True

    # Look up explicit allowlist for requested model canonical ID
    allowed = VERIFIED_MODEL_SNAPSHOTS.get(r_canon)
    if allowed:
        return (a_canon in allowed) or (a in allowed)

    return False


def calculate_model_cost(
    model_name: Optional[str],
    in_tokens: Optional[int],
    out_tokens: Optional[int],
) -> Optional[float]:
    """Calculates usage-based cost in USD using the actual serving model's verified pricing.
    
    Returns None if actual model or pricing cannot be verified, or if tokens are missing.
    """
    if in_tokens is None or out_tokens is None:
        return None
    if not model_name:
        return None

    clean_model = model_name.strip().lower()

    # Verified free models
    if ":free" in clean_model or clean_model in ("openrouter/free", "fake"):
        return 0.0

    canonical = resolve_openrouter_model(clean_model).lower()
    price_entry = PRICING_CATALOG.get(clean_model) or PRICING_CATALOG.get(canonical)

    if not price_entry:
        # Check verified snapshot mappings
        for canon_key, snapshots in VERIFIED_MODEL_SNAPSHOTS.items():
            if clean_model in snapshots or canonical in snapshots:
                price_entry = PRICING_CATALOG.get(canon_key)
                if price_entry:
                    break

    if not price_entry:
        # Cannot verify pricing for uncataloged model
        return None

    return round((in_tokens * price_entry["input"]) + (out_tokens * price_entry["output"]), 6)


def estimate_prompt_tokens(
    messages: List[Dict[str, Any]],
    safety_margin_pct: float = 0.20,
    fixed_overhead: int = 30,
) -> int:
    """Estimates serialized prompt tokens using a local tokenizer with an explicit safety margin.

    Uses tiktoken cl100k_base when available; falls back to a conservative character heuristic
    (1 token / 3 chars). Applies an explicit safety margin (default 20%) and fixed overhead
    (default 30 tokens for chat envelope / system framing) to strictly bound provider tokenization
    variance and ensure fail-closed budget pre-allocation.
    """
    total_tokens = 0
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        for msg in messages:
            if isinstance(msg, dict):
                content = str(msg.get("content", "") or "")
                role = str(msg.get("role", "") or "")
                total_tokens += len(enc.encode(content)) + len(enc.encode(role)) + 4
            else:
                total_tokens += len(enc.encode(str(msg))) + 4
    except Exception:
        for msg in messages:
            if isinstance(msg, dict):
                content = str(msg.get("content", "") or "")
                role = str(msg.get("role", "") or "")
                total_tokens += (len(content) + len(role)) // 3 + 4
            else:
                total_tokens += len(str(msg)) // 3 + 4

    buffered = int(total_tokens * (1.0 + safety_margin_pct)) + fixed_overhead
    return max(buffered, fixed_overhead)


def extract_json(content: str) -> Optional[Dict[str, Any]]:
    """Extracts valid JSON object from model output, handling markdown blocks and literal control chars."""
    if not content:
        return None
    text = content.strip()
    # 1. Direct parsing
    try:
        data = json.loads(text, strict=False)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    # 2. Markdown code fences
    import re
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if match:
        try:
            data = json.loads(match.group(1), strict=False)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    # 3. Outer bracket search
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            data = json.loads(candidate, strict=False)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        # Clean trailing commas
        cleaned = re.sub(r",\s*([}\]])", r"\1", candidate)
        try:
            data = json.loads(cleaned, strict=False)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return None


@dataclass
class ModelResult:
    text: str
    model_name: str
    provider_model_version: str
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    total_tokens: Optional[int]
    latency_ms: int
    request_id: str
    estimated_cost: Optional[float]
    parsed_json: Optional[Dict[str, Any]] = None
    execution_mode: str = "LIVE_API"  # LIVE_API or SIMULATED
    token_provenance: str = "PROVIDER_REPORTED"  # PROVIDER_REPORTED, SIMULATED, or UNAVAILABLE
    requested_model: Optional[str] = None
    raw_metadata: Optional[Dict[str, Any]] = None
    reasoning_tokens: Optional[int] = None
    visible_output_tokens: Optional[int] = None


class TokenCapExceededError(Exception):
    """Raised when a run exceeds its allocated provider token limit (ceiling = 60,000)."""
    pass


class DispatchCeilingExceededError(Exception):
    """Raised when a run reaches or exceeds the maximum logical model-call dispatches (ceiling = 15)."""
    pass


class DailyTransmissionsCeilingExceededError(Exception):
    """Raised when outbound HTTP transmissions reach the daily ceiling (ceiling = 45 per UTC day)."""
    pass


class TokenLogger:
    """Tracks provider token usage per run and enforces the 60,000 cap with DB persistence."""

    def __init__(self, max_tokens_per_run: int = 60000):
        self.max_tokens_per_run = max_tokens_per_run
        self._run_totals: Dict[str, Dict[str, Any]] = {}
        self._reservations: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def get_active_reservation_tokens(self, run_id: str) -> int:
        """Returns the sum of currently active in-flight reserved tokens for a given run."""
        with self._lock:
            return sum(r["tokens"] for r in self._reservations.values() if r.get("run_id") == run_id)

    def reserve_budget(
        self,
        run_id: str,
        estimated_input: int,
        requested_output: int,
        min_safe_completion: int = 50,
    ) -> Tuple[str, int]:
        """Atomically reserves estimated input-plus-output tokens before network dispatch.

        Fail-closed:
        1. Determines remaining run budget from authoritative cap (60,000) minus current recorded tokens
           and any active in-flight reservations.
        2. Computes completion allowance after reserving estimated input tokens.
        3. If available completion allowance < min_safe_completion (default 50), blocks the request
           before dispatch by raising TokenCapExceededError. Never forces max_tokens=1.
        4. Clamps completion allowance to the lesser of requested_output and available_for_completion.
        5. Atomically records the reservation and returns (reservation_id, effective_output).
        """
        with self._lock:
            run_totals = self.get_run_totals(run_id)
            current_tokens = run_totals.get("total_tokens", 0)
            active_reserved = sum(r["tokens"] for r in self._reservations.values() if r.get("run_id") == run_id)

            remaining_budget = self.max_tokens_per_run - (current_tokens + active_reserved)
            available_for_completion = remaining_budget - estimated_input

            if available_for_completion < min_safe_completion:
                raise TokenCapExceededError(
                    f"Run {run_id} reached per-run token ceiling of {self.max_tokens_per_run} tokens: "
                    f"budget gate blocked request before dispatch: remaining budget ({remaining_budget} tokens, "
                    f"current={current_tokens}, reserved={active_reserved}) is insufficient for estimated prompt "
                    f"({estimated_input} tokens) plus minimum safe completion allowance ({min_safe_completion} tokens)."
                )

            effective_output = min(requested_output, available_for_completion)
            total_reserved = estimated_input + effective_output
            reservation_id = f"res_{uuid.uuid4().hex[:12]}"
            self._reservations[reservation_id] = {
                "run_id": run_id,
                "tokens": total_reserved,
                "estimated_input": estimated_input,
                "reserved_output": effective_output,
                "created_at": time.time(),
            }
            return reservation_id, effective_output

    def release_reservation(self, reservation_id: Optional[str]):
        """Releases an active budget reservation (e.g. on dispatch failure, network error, or abort)."""
        if not reservation_id:
            return
        with self._lock:
            self._reservations.pop(reservation_id, None)

    def get_run_totals(self, run_id: str, db_session=None) -> Dict[str, Any]:
        """Returns accurate provider-reported token usage and cost, querying DB if needed."""
        # 1. Check in-memory cache
        mem_tot = self._run_totals.get(run_id)
        if mem_tot and mem_tot.get("total_tokens", 0) > 0:
            return mem_tot

        # 2. Query persistent database
        own_session = False
        if db_session is None:
            db_session = get_session()
            own_session = True

        try:
            calls = db_session.query(ModelCall).filter(ModelCall.run_id == run_id).all()
            if calls:
                in_tok = sum(c.input_tokens for c in calls)
                out_tok = sum(c.output_tokens for c in calls)
                tot_tok = sum(c.total_tokens for c in calls)
                cost = sum(c.cost for c in calls)
                prov = "SIMULATED" if any("fake" in c.model.lower() for c in calls) else ("PROVIDER_REPORTED" if tot_tok > 0 else "UNAVAILABLE")
                totals = {
                    "input_tokens": in_tok,
                    "output_tokens": out_tok,
                    "total_tokens": tot_tok,
                    "estimated_cost": round(cost, 6),
                    "call_count": len(calls),
                    "token_provenance": prov,
                }
                self._run_totals[run_id] = totals
                return totals

            # Check Run record directly
            from mas.db.models import Run
            run_row = db_session.query(Run).filter(Run.run_id == run_id).first()
            if run_row and (run_row.total_tokens or 0) > 0:
                totals = {
                    "input_tokens": run_row.input_tokens or 0,
                    "output_tokens": run_row.output_tokens or 0,
                    "total_tokens": run_row.total_tokens or 0,
                    "estimated_cost": round(run_row.estimated_cost or 0.0, 6),
                    "call_count": 1,
                    "token_provenance": run_row.token_provenance or "UNAVAILABLE",
                }
                self._run_totals[run_id] = totals
                return totals
        except Exception:
            pass
        finally:
            if own_session:
                db_session.close()

        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost": 0.0,
            "call_count": 0,
            "token_provenance": "UNAVAILABLE",
        }

    def get_stage_spend(self, run_ids: Optional[List[str]] = None) -> float:
        """Returns cumulative spend across specified run IDs or all active runs in memory."""
        if run_ids:
            return sum(self.get_run_totals(rid).get("estimated_cost", 0.0) for rid in run_ids)
        return sum(totals.get("estimated_cost", 0.0) for totals in self._run_totals.values())

    def record_call(self, run_id: str, agent: str, result: ModelResult, reservation_id: Optional[str] = None, db_session=None):
        with self._lock:
            if reservation_id:
                self._reservations.pop(reservation_id, None)

            if run_id not in self._run_totals:
                self._run_totals[run_id] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "estimated_cost": 0.0,
                    "call_count": 0,
                    "token_provenance": result.token_provenance,
                }

            in_val = result.input_tokens or 0
            out_val = result.output_tokens or 0
            tot_val = result.total_tokens or (in_val + out_val)

            totals = self._run_totals[run_id]
            totals["input_tokens"] += in_val
            totals["output_tokens"] += out_val
            totals["total_tokens"] += tot_val
            if result.estimated_cost is not None:
                totals["estimated_cost"] = round(totals["estimated_cost"] + result.estimated_cost, 6)
            totals["call_count"] += 1
            totals["token_provenance"] = result.token_provenance

            # Persist to database
            own_session = False
            if db_session is None:
                db_session = get_session()
                own_session = True

            try:
                call_obj = ModelCall(
                    run_id=run_id,
                    agent=agent,
                    model=result.model_name,
                    requested_model=result.requested_model,
                    actual_model=result.model_name,
                    request_id=result.request_id,
                    raw_metadata=result.raw_metadata,
                    input_tokens=in_val,
                    output_tokens=out_val,
                    total_tokens=tot_val,
                    latency_ms=result.latency_ms,
                    cost=result.estimated_cost,
                )
                db_session.add(call_obj)

                # Update Run record with latest aggregates
                from mas.db.models import Run
                run_row = db_session.query(Run).filter(Run.run_id == run_id).first()
                if run_row:
                    run_row.input_tokens = totals["input_tokens"]
                    run_row.output_tokens = totals["output_tokens"]
                    run_row.total_tokens = totals["total_tokens"]
                    if totals.get("estimated_cost") is not None:
                        run_row.estimated_cost = round(totals["estimated_cost"], 6)
                    run_row.token_provenance = result.token_provenance
                    run_row.execution_mode = result.execution_mode
                    if result.model_name:
                        run_row.actual_model = result.model_name
                    if result.request_id:
                        run_row.provider_request_id = result.request_id

                    # Flag model mismatch on run record
                    req_model = result.requested_model or run_row.model
                    if req_model and result.model_name and not is_model_match(req_model, result.model_name):
                        run_row.status = "MODEL_MISMATCH_DIAGNOSTIC"
                        run_row.failure_reason = (
                            f"MODEL_MISMATCH_DIAGNOSTIC: Requested '{req_model}' but served by '{result.model_name}'. "
                            f"Retained for audit, excluded from research aggregates."
                        )

                db_session.commit()
            except Exception:
                db_session.rollback()
            finally:
                if own_session:
                    db_session.close()

            # Check token cap
            if totals["total_tokens"] > self.max_tokens_per_run:
                raise TokenCapExceededError(
                    f"Run {run_id} exceeded token cap: {totals['total_tokens']} > {self.max_tokens_per_run}"
                )


token_logger = TokenLogger()


class LLMProvider(ABC):
    """Abstract interface for model invocation."""

    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4o",
        response_schema: Optional[type[BaseModel]] = None,
        temperature: float = 0.0,
        run_id: Optional[str] = None,
        agent_name: str = "agent",
        max_tokens: int = 2000,
    ) -> ModelResult:
        pass


class FakeLLMProvider(LLMProvider):
    """Deterministic fake provider for development, tests, and CP1 validation."""

    def __init__(self):
        self.call_count = 0

    def generate(
        self,
        messages: List[Dict[str, str]],
        model: str = "fake",
        response_schema: Optional[type[BaseModel]] = None,
        temperature: float = 0.0,
        run_id: Optional[str] = None,
        agent_name: str = "agent",
        max_tokens: int = 2000,
    ) -> ModelResult:
        reservation_id = None
        effective_max_tokens = max_tokens
        if run_id:
            estimated_input = estimate_prompt_tokens(messages)
            reservation_id, effective_max_tokens = token_logger.reserve_budget(
                run_id=run_id,
                estimated_input=estimated_input,
                requested_output=max_tokens,
                min_safe_completion=50,
            )

        self.call_count += 1
        t0 = time.time()

        # Deterministic generation based on agent_name or prompt
        parsed: Dict[str, Any] = {}
        text = ""

        if agent_name == "manager":
            parsed = {
                "id": "TP-001",
                "task_id": "task-fake",
                "name": "Deterministic Task Implementation",
                "description": "Implement simple math library",
                "complexity": "SIMPLE",
                "files": ["calculator.py", "test_calculator.py"],
                "sprint_goals": ["Create add and multiply operations", "Verify smoke tests"],
                "acceptance_criteria": [
                    "add(a, b) returns correct sum of two integers",
                    "multiply(a, b) returns correct product of two integers",
                ],
                "ambiguities": [],
            }
            text = json.dumps(parsed)

        elif response_schema and response_schema.__name__ == "UserStory":
            parsed = {
                "id": "US-001",
                "role": "User",
                "action": "execute core operations",
                "goal": "achieve requested functional outcome",
                "acceptance_criteria": ["System executes without errors", "Functions return correct values"],
                "priority": "high",
                "estimate": 3,
            }
            text = json.dumps(parsed)

        elif agent_name == "architect" or (response_schema and response_schema.__name__ == "Architecture"):
            parsed = {
                "components": [
                    {"name": "AppEngine", "responsibility": "Core application orchestration"},
                    {"name": "Storage", "responsibility": "Data persistence layer"},
                ],
                "uml_class_diagram": "classDiagram\nclass AppEngine { +run() }\nclass Storage { +save() }",
                "file_structure": ["app.py", "storage.py", "utils.py"],
                "module_dependencies": {"app": ["storage", "utils"], "storage": ["utils"]},
            }
            text = json.dumps(parsed)

        elif agent_name == "developer":
            # Extract requirement context from messages to ensure semantic alignment
            context_text = " ".join(m.get("content", "") for m in messages if isinstance(m, dict))
            clean_words = [w for w in re.findall(r'[a-zA-Z]{3,}', context_text.lower()) if w not in {'the', 'and', 'for', 'with', 'that', 'this', 'you', 'from', 'are', 'was', 'have', 'user', 'code', 'file', 'json', 'schema', 'must', 'return', 'implementation'}]
            top_keywords = list(dict.fromkeys(clean_words))[:20]
            kw_comment = ", ".join(top_keywords) if top_keywords else "core application logic"

            code_content = (
                f'"""Automated system implementation for: {kw_comment}."""\n\n'
                f'class ApplicationService:\n'
                f'    """Core business logic service orchestrating requested functionality."""\n\n'
                f'    def __init__(self, name: str = "Service") -> None:\n'
                f'        self.name = name\n'
                f'        self.initialized = True\n\n'
                f'    def execute_action(self, payload: dict = None) -> dict:\n'
                f'        """Executes domain operations based on specification."""\n'
                f'        data = payload or {{}}\n'
                f'        result = {{"status": "success", "processed": True, "count": len(data)}}\n'
                f'        return result\n\n'
                f'    def validate_state(self) -> bool:\n'
                f'        """Validates current service state consistency."""\n'
                f'        return self.initialized\n\n'
                f'def add(a: int, b: int) -> int:\n'
                f'    """Adds two integers."""\n'
                f'    return a + b\n\n'
                f'def multiply(a: int, b: int) -> int:\n'
                f'    """Multiplies two integers."""\n'
                f'    return a * b\n\n'
                f'def main() -> None:\n'
                f'    """Entry point execution routine."""\n'
                f'    service = ApplicationService()\n'
                f'    output = service.execute_action({{"mode": "default"}})\n'
                f'    assert service.validate_state(), "State validation failed"\n'
                f'    print("Application execution completed successfully.")\n\n'
                f'if __name__ == "__main__":\n'
                f'    main()\n'
            )

            parsed = {
                "files": ["main.py", "calculator.py"],
                "file_contents": {
                    "main.py": code_content,
                    "calculator.py": (
                        "def add(a: int, b: int) -> int:\n"
                        "    '''Adds two numbers.'''\n"
                        "    return a + b\n\n"
                        "def multiply(a: int, b: int) -> int:\n"
                        "    '''Multiplies two numbers.'''\n"
                        "    return a * b\n"
                    ),
                },
                "summary": f"Implemented ApplicationService, add/multiply, and entry point for {kw_comment}",
                "tests_expected": ["test_execute_action", "test_add", "test_multiply"],
            }
            text = json.dumps(parsed)

        elif agent_name == "reviewer":
            parsed = {
                "status": "PASSED",
                "critical_issues": 0,
                "major_issues": 0,
                "minor_issues": 0,
                "findings": ["Code is clean and conforms to specification."],
                "summary": "All arithmetic functions implemented without defects.",
            }
            text = json.dumps(parsed)

        elif agent_name == "reflection":
            parsed = {
                "decision": "STOP",
                "reason": "clean_result: no critical defects and internal checks pass",
                "adaptive_score": 0.95,
                "marginal_gain": 0.95,
                "iteration": 1,
            }
            text = json.dumps(parsed)

        elif agent_name == "tester":
            parsed = {
                "total_tests": 2,
                "passed_tests": 2,
                "failed_tests": 0,
                "pass_rate": 1.0,
                "coverage": 100.0,
                "details": ["test_add PASSED", "test_multiply PASSED"],
            }
            text = json.dumps(parsed)

        else:
            text = "Deterministic response"
            parsed = {"status": "ok"}

        latency = int((time.time() - t0) * 1000)
        req_id = f"fake-req-{self.call_count:04d}"

        # Deterministic token counts
        in_tokens = 120 + len(messages) * 15
        out_tokens = 80 + len(text) // 4
        tot_tokens = in_tokens + out_tokens

        res = ModelResult(
            text=text,
            model_name=model,
            provider_model_version="fake-v1.0",
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            total_tokens=tot_tokens,
            latency_ms=max(latency, 5),
            request_id=req_id,
            estimated_cost=0.0,
            parsed_json=parsed,
            execution_mode="SIMULATED",
            token_provenance="SIMULATED",
        )

        if run_id:
            token_logger.record_call(run_id=run_id, agent=agent_name, result=res, reservation_id=reservation_id)

        return res


class OpenRouterProvider(LLMProvider):
    """OpenRouter API provider supporting free and paid models."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
    ):
        import os
        self.base_url = (
            base_url
            or os.environ.get("OPENROUTER_BASE_URL")
            or os.environ.get("PROXY_BASE_URL", "https://openrouter.ai/api/v1")
        )
        self.api_key = (
            api_key
            if api_key is not None
            else (os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY", ""))
        )
        self.default_model = (
            default_model
            or os.environ.get("OPENROUTER_MODEL")
            or "openrouter/free"
        )
        self.uses_governed_client = True

    def check_key_metadata(self) -> Dict[str, Any]:
        """Queries OpenRouter /api/v1/key to inspect credit, rate limit, and free quota status without model dispatch."""
        if not self.api_key:
            return {"error": "no_api_key"}
        url = f"{self.base_url.rstrip('/')}/key"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/mas-team/mas",
            "X-Title": "MAS Multi-Agent Software Engineering Team",
        }
        try:
            from mas.core.governor import GovernedHTTPClient
            with GovernedHTTPClient(timeout=15.0, request_type="KEY_METADATA", target="/api/v1/key", source="check_key_metadata") as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    try:
                        parsed = resp.json()
                        if not isinstance(parsed, dict) or "data" not in parsed or not isinstance(parsed["data"], dict):
                            return {
                                "status_code": resp.status_code,
                                "error": "malformed_response_missing_data_field",
                                "raw_body": resp.text,
                            }
                        data = parsed["data"]
                        # Annotate with date header from response if available
                        data["_response_date"] = resp.headers.get("date")
                        return data
                    except Exception as json_err:
                        return {
                            "status_code": resp.status_code,
                            "error": f"json_decode_error: {json_err}",
                            "raw_body": resp.text,
                        }
                return {"status_code": resp.status_code, "error": resp.text}
        except Exception as e:
            return {"error": str(e)}

    def generate(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        response_schema: Optional[type[BaseModel]] = None,
        temperature: float = 0.0,
        run_id: Optional[str] = None,
        agent_name: str = "agent",
        max_tokens: int = 2000,
    ) -> ModelResult:
        if not self.api_key:
            raise RuntimeError(
                "Missing API key: OPENROUTER_API_KEY is not configured for live model execution. "
                "Silent fallback to fake provider is strictly prohibited for research validity."
            )

        stage_budget_str = os.environ.get("MAS_STAGE_MAX_SPEND")
        if stage_budget_str:
            try:
                stage_budget = float(stage_budget_str)
                current_spend = token_logger.get_stage_spend()
                conservative_call_cost = 0.035
                if current_spend + conservative_call_cost > stage_budget:
                    raise RuntimeError(
                        f"Budget cap enforced: cumulative spend (${current_spend:.4f}) + "
                        f"projected call cost (${conservative_call_cost:.4f}) exceeds authorized limit of ${stage_budget:.2f}."
                    )
            except ValueError:
                pass

        # 1. Enforce per-run dispatch ceiling and atomic fail-closed token budget reservation
        if run_id:
            run_totals = token_logger.get_run_totals(run_id)
            calls_cap_env = os.environ.get("MAX_CALLS_PER_RUN")
            if calls_cap_env:
                try:
                    max_calls = int(calls_cap_env)
                    if run_totals.get("call_count", 0) >= max_calls:
                        raise DispatchCeilingExceededError(
                            f"Run {run_id} reached dispatch ceiling of {max_calls} calls ({run_totals.get('call_count', 0)} calls already made)."
                        )
                except ValueError:
                    pass

        # 2. Enforce UTC daily outbound HTTP transmission ceiling across ALL request types
        daily_cap_env = os.environ.get("MAX_DAILY_HTTP_TRANSMISSIONS")
        if daily_cap_env:
            try:
                max_daily_calls = int(daily_cap_env)
                if max_daily_calls > 0:
                    from mas.core.governor import global_governor
                    stats = global_governor.get_ledger_stats()
                    if stats["total_attributable_attempts"] >= max_daily_calls:
                        raise DailyTransmissionsCeilingExceededError(
                            f"Daily outbound HTTP transmissions ceiling reached ({stats['total_attributable_attempts']} >= {max_daily_calls} for UTC day). Checkpointing run safely."
                        )
            except DailyTransmissionsCeilingExceededError:
                raise
            except Exception as e:
                logger.warning("Could not query global governor ledger: %s", e)

        target_model = resolve_openrouter_model(model or self.default_model)
        t0 = time.time()

        processed_messages = list(messages)
        if response_schema:
            last_content = processed_messages[-1]["content"] if (processed_messages and processed_messages[-1]["role"] == "user") else ""
            if "matching this schema" not in last_content and "JSON Schema" not in last_content:
                schema_instruction = (
                    f"\n\nCRITICAL INSTRUCTION: You MUST return a single JSON object conforming exactly to this JSON Schema:\n"
                    f"{json.dumps(response_schema.model_json_schema())}\n"
                    f"Do NOT include any explanatory text outside the JSON object."
                )
                if processed_messages and processed_messages[-1]["role"] == "user":
                    processed_messages[-1] = {
                        "role": "user",
                        "content": processed_messages[-1]["content"] + schema_instruction,
                    }
                else:
                    processed_messages.append({"role": "user", "content": schema_instruction})

        reservation_id = None
        if run_id:
            estimated_input = estimate_prompt_tokens(processed_messages)
            reservation_id, effective_max_tokens = token_logger.reserve_budget(
                run_id=run_id,
                estimated_input=estimated_input,
                requested_output=max_tokens,
                min_safe_completion=50,
            )
        else:
            effective_max_tokens = max_tokens

        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": processed_messages,
            "temperature": temperature,
            "seed": 42,
            "max_tokens": effective_max_tokens,
            "provider": {
                "allow_fallbacks": False,
            },
        }

        # Configurable reasoning token limits (e.g. for reasoning models that exhaust token budgets)
        reasoning_limit_env = os.environ.get("OPENROUTER_REASONING_MAX_TOKENS")
        if reasoning_limit_env is not None:
            try:
                payload["reasoning"] = {"max_tokens": int(reasoning_limit_env)}
            except ValueError:
                pass
        elif "reasoning" in target_model.lower() or "cohere" in target_model.lower():
            payload["reasoning"] = {"max_tokens": 0}

        if response_schema and "cohere" not in target_model.lower():
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/mas-team/mas",
            "X-Title": "MAS Multi-Agent Software Engineering Team",
        }

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        try:
            from mas.core.governor import GovernedHTTPClient
            with GovernedHTTPClient(
                timeout=90.0,
                request_type="LIVE_GENERATION",
                target=target_model,
                source=f"{run_id}:{agent_name}" if run_id else agent_name,
            ) as client:
                resp = client.post(url, json=payload, headers=headers)
        except DailyTransmissionsCeilingExceededError:
            token_logger.release_reservation(reservation_id)
            raise
        except httpx.ConnectError as e:
            token_logger.release_reservation(reservation_id)
            raise RuntimeError(
                f"Failed to connect to OpenRouter at {url}. "
                f"Please verify your network connection or OPENROUTER_BASE_URL. Details: {e}"
            ) from e
        except httpx.TimeoutException as e:
            token_logger.release_reservation(reservation_id)
            raise RuntimeError(
                f"Request to OpenRouter timed out after 90s for model {target_model}. Details: {e}"
            ) from e
        except Exception:
            token_logger.release_reservation(reservation_id)
            raise

        if resp.status_code != 200:
            token_logger.release_reservation(reservation_id)
            parsed_err: Dict[str, Any] = {}
            raw_text = ""
            try:
                raw_text = resp.text
                parsed_json = resp.json()
                if isinstance(parsed_json, dict):
                    parsed_err = parsed_json
            except Exception:
                parsed_err = {}

            sanitized_headers = sanitize_headers_dict(resp.headers)
            retry_after = sanitized_headers.get("Retry-After") or sanitized_headers.get("retry-after")

            err_obj = parsed_err.get("error") if isinstance(parsed_err.get("error"), dict) else {}
            metadata = err_obj.get("metadata") if isinstance(err_obj.get("metadata"), dict) else {}

            error_msg = err_obj.get("message")
            if not error_msg and isinstance(err_obj, str):
                error_msg = err_obj
            elif not error_msg:
                error_msg = raw_text

            reason = metadata.get("reason")
            limit_source = metadata.get("limit_source")
            remedy_hint = metadata.get("remedy_hint")

            # Redact any secrets in error fields
            error_msg = redact_sensitive_string(str(error_msg) if error_msg else "", self.api_key)
            if reason:
                reason = redact_sensitive_string(str(reason), self.api_key)
            if limit_source:
                limit_source = redact_sensitive_string(str(limit_source), self.api_key)
            if remedy_hint:
                remedy_hint = redact_sensitive_string(str(remedy_hint), self.api_key)

            # Log available error fields preserving upstream diagnostics
            logger.error(
                "OpenRouter HTTP %d error on model '%s': message='%s', reason='%s', limit_source='%s', remedy_hint='%s', retry_after='%s'",
                resp.status_code,
                target_model,
                error_msg,
                reason,
                limit_source,
                remedy_hint,
                retry_after,
            )

            diag_parts = []
            if error_msg:
                diag_parts.append(f"message: '{error_msg}'")
            if reason:
                diag_parts.append(f"reason: '{reason}'")
            if limit_source:
                diag_parts.append(f"limit_source: '{limit_source}'")
            if remedy_hint:
                diag_parts.append(f"remedy_hint: '{remedy_hint}'")
            if retry_after:
                diag_parts.append(f"retry_after: '{retry_after}'")

            diag_str = "; ".join(diag_parts) if diag_parts else redact_sensitive_string(raw_text[:200], self.api_key)

            if resp.status_code == 401:
                prefix = f"OpenRouter Authentication Error (401) on model '{target_model}'"
            elif resp.status_code == 402:
                prefix = f"OpenRouter Payment/Credit Error (402) on model '{target_model}'"
            elif resp.status_code == 429:
                prefix = f"OpenRouter Rate Limit Error (429) on model '{target_model}'"
            else:
                prefix = f"OpenRouter Request Error ({resp.status_code}) on model '{target_model}'"

            full_msg = f"{prefix}: {diag_str}"

            raise OpenRouterAPIError(
                status_code=resp.status_code,
                message=full_msg,
                error_data=parsed_err,
                headers=sanitized_headers,
                raw_body=raw_text,
            )

        data = resp.json()
        latency = int((time.time() - t0) * 1000)
        choice = data["choices"][0]
        msg_obj = choice.get("message", {})
        content = msg_obj.get("content") or msg_obj.get("text") or ""
        if not content and msg_obj.get("reasoning"):
            content = msg_obj.get("reasoning")
        usage = data.get("usage")

        if usage and isinstance(usage, dict) and any(k in usage for k in ("prompt_tokens", "completion_tokens", "total_tokens")):
            in_tok = usage.get("prompt_tokens")
            out_tok = usage.get("completion_tokens")
            tot_tok = usage.get("total_tokens")
            if tot_tok is None and in_tok is not None and out_tok is not None:
                tot_tok = in_tok + out_tok
            token_provenance = "PROVIDER_REPORTED"
        else:
            in_tok = None
            out_tok = None
            tot_tok = None
            token_provenance = "UNAVAILABLE"

        actual_model = data.get("model")
        req_id = data.get("id", str(uuid.uuid4()))

        # Secret-redacted raw model metadata preserved for auditing
        raw_meta = {
            "id": req_id,
            "model": actual_model,
            "system_fingerprint": data.get("system_fingerprint"),
            "usage": usage,
            "provider": data.get("provider"),
        }

        # Calculate cost strictly from verified actual serving model pricing metadata
        cost = calculate_model_cost(actual_model, in_tok, out_tok) if (in_tok is not None or out_tok is not None) else None
        parsed_json = extract_json(content) if response_schema else None

        ct_details = usage.get("completion_tokens_details") if isinstance(usage, dict) else {}
        reasoning_tok = ct_details.get("reasoning_tokens") if isinstance(ct_details, dict) else None
        visible_tok = (out_tok - reasoning_tok) if (out_tok is not None and reasoning_tok is not None) else out_tok

        result = ModelResult(
            text=content,
            model_name=actual_model or "UNKNOWN",
            requested_model=target_model,
            provider_model_version=data.get("system_fingerprint", actual_model or "UNKNOWN"),
            input_tokens=in_tok,
            output_tokens=out_tok,
            total_tokens=tot_tok,
            latency_ms=latency,
            request_id=req_id,
            estimated_cost=cost,
            raw_metadata=raw_meta,
            parsed_json=parsed_json,
            execution_mode="LIVE_API",
            token_provenance=token_provenance,
            reasoning_tokens=reasoning_tok,
            visible_output_tokens=visible_tok,
        )

        if run_id:
            token_logger.record_call(run_id=run_id, agent=agent_name, result=result, reservation_id=reservation_id)

        # Strict model enforcement check
        if not actual_model:
            raise ModelMismatchError(
                f"Missing model metadata: Provider response omitted 'model' field. "
                f"Cannot verify that requested '{target_model}' was served."
            )

        if not is_model_match(target_model, actual_model):
            raise ModelMismatchError(
                f"Model mismatch error: Requested '{target_model}', but provider returned '{actual_model}'. "
                f"Fallbacks are strictly prohibited for benchmark integrity."
            )

        return result


# Preserve alias for backwards compatibility
OpenAIProvider = OpenRouterProvider
