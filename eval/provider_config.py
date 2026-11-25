"""Provider configuration: precedence resolution, type detection, and safety validation.

Rules enforced here:
  1. PROVIDER_API_KEY / PROVIDER_BASE_URL / BENCH_MODEL are the primary group.
     OPENROUTER_* names are a fallback only when NONE of the PROVIDER_* names is set.
     Values from the two groups are NEVER mixed.
  2. For benchmark/live runs, BENCH_MODEL must be non-empty and must not be an auto-router
     alias ("openrouter/free", empty, or the placeholder).
  3. Provider type is detected from PROVIDER_BASE_URL host only.
  4. For the Gemini provider the model ID must NOT start with "google/" (strip it and warn),
     and the key must start with "AIza" or "AQ." (checked without printing any part of the key).
  5. An OpenRouter key (starts with "sk-or-") used with the Gemini endpoint is an error.
  6. Using provider=openrouter for a benchmark run is an error unless --allow-openrouter.

This module has NO side-effects on import. All validation is opt-in via the helper functions.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Provider type detection
# ---------------------------------------------------------------------------

# Prefixes of Google AI Studio API keys: classic and newer format.
GOOGLE_KEY_PREFIXES = ("AIza", "AQ.")


def _detect_provider_type(base_url: str) -> str:
    """Returns 'gemini', 'openrouter', or 'other' based on the host name."""
    if not base_url:
        return "other"
    try:
        host = urlparse(base_url).hostname or ""
    except Exception:
        host = ""
    host = host.lower()
    if "generativelanguage.googleapis.com" in host:
        return "gemini"
    if "openrouter.ai" in host:
        return "openrouter"
    return "other"


# ---------------------------------------------------------------------------
# Precedence resolution — public API
# ---------------------------------------------------------------------------

class ProviderSettings:
    """Holds the resolved provider configuration (no secrets stored here)."""

    __slots__ = (
        "api_key",          # actual secret — only used by callers that need it
        "base_url",
        "bench_model",
        "provider_type",    # 'gemini' | 'openrouter' | 'other'
        "host",
        "source",           # 'PROVIDER' | 'OPENROUTER_LEGACY'
        "openrouter_legacy_vars_set",  # True if any OPENROUTER_* env vars present
    )

    def __init__(
        self,
        api_key: str,
        base_url: str,
        bench_model: str,
        source: str,
        openrouter_legacy_vars_set: bool,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.bench_model = bench_model
        self.source = source
        self.openrouter_legacy_vars_set = openrouter_legacy_vars_set
        self.provider_type = _detect_provider_type(self.base_url)
        try:
            self.host = urlparse(self.base_url).hostname or "(unknown)"
        except Exception:
            self.host = "(unknown)"

    # ------------------------------------------------------------------
    # Convenience query helpers (never expose the key value)
    # ------------------------------------------------------------------

    def key_length(self) -> int:
        return len(self.api_key) if self.api_key else 0

    def key_starts_with_AIza(self) -> bool:
        return bool(self.api_key) and self.api_key.startswith("AIza")

    def key_looks_like_google(self) -> bool:
        """Google AI Studio keys: classic 'AIza...' or the newer 'AQ.' format (DEC-042)."""
        return bool(self.api_key) and self.api_key.startswith(GOOGLE_KEY_PREFIXES)

    def key_looks_like_openrouter(self) -> bool:
        return bool(self.api_key) and self.api_key.startswith("sk-or-")

    def bench_model_normalized(self) -> str:
        """Strips the 'google/' owner prefix for Gemini models if present."""
        m = self.bench_model or ""
        if self.provider_type == "gemini" and m.lower().startswith("google/"):
            return m[len("google/"):]
        return m

    def bench_model_has_google_prefix(self) -> bool:
        m = self.bench_model or ""
        return self.provider_type == "gemini" and m.lower().startswith("google/")


def resolve_provider_settings(env: Optional[dict] = None) -> ProviderSettings:
    """Resolves provider settings applying the PROVIDER_* > OPENROUTER_* precedence rule.

    Args:
        env: mapping to read from (defaults to os.environ). Pass a dict in tests.

    Returns:
        ProviderSettings instance. Never raises; callers must call validate_* separately.
    """
    e = env if env is not None else os.environ

    # --- Primary group ---
    p_key = e.get("PROVIDER_API_KEY", "").strip()
    p_url = e.get("PROVIDER_BASE_URL", "").strip()
    p_model = e.get("BENCH_MODEL", "").strip()

    # --- Legacy group ---
    or_key = e.get("OPENROUTER_API_KEY", "").strip()
    or_url = e.get("OPENROUTER_BASE_URL", "").strip()
    or_model = e.get("OPENROUTER_MODEL", "").strip()

    # Detect whether any OPENROUTER_* variable is set
    or_vars_set = bool(or_key or or_url or or_model or e.get("OPENROUTER_CHEAP_MODEL", "").strip())

    # Decide source: use PROVIDER_* if ANY of the PROVIDER_* names is non-empty.
    provider_primary_set = bool(p_key or p_url or p_model)

    if provider_primary_set:
        source = "PROVIDER"
        api_key = p_key
        base_url = p_url or "https://generativelanguage.googleapis.com/v1beta/openai/"
        bench_model = p_model
    else:
        # Fallback to OPENROUTER_* names (legacy / non-benchmark path)
        source = "OPENROUTER_LEGACY"
        api_key = or_key
        base_url = or_url or "https://openrouter.ai/api/v1"
        bench_model = or_model

    return ProviderSettings(
        api_key=api_key,
        base_url=base_url,
        bench_model=bench_model,
        source=source,
        openrouter_legacy_vars_set=or_vars_set,
    )


# ---------------------------------------------------------------------------
# Validation helpers — return (passed: bool, messages: list[str])
# ---------------------------------------------------------------------------

# Models that are always rejected for official benchmark runs.
_REJECTED_BENCH_MODELS = frozenset({
    "",
    "openrouter/free",
    "__set_bench_model_in_env__",
    "<exact-model-id-from-list_models>",
})

# Models with ":free" router suffix (auto-router aliases on OpenRouter)
def _is_autorouter_alias(model: str) -> bool:
    return model.lower().endswith(":free") or model.lower() == "openrouter/free"


def validate_for_live_run(
    settings: ProviderSettings,
    allow_openrouter: bool = False,
) -> Tuple[bool, list]:
    """Runs all checks required before a live/benchmark run.

    Returns (all_passed, list_of_message_strings).
    Messages starting with '[FAIL]' are errors; '[WARN]' are non-fatal warnings.
    """
    messages: list = []
    all_passed = True

    # --- BENCH_MODEL must be set and not a banned alias ---
    model_norm = settings.bench_model_normalized()
    if not settings.bench_model or settings.bench_model.strip().lower() in _REJECTED_BENCH_MODELS:
        messages.append("[FAIL] BENCH_MODEL is empty or unset — set it to an exact model ID from scripts/list_models.py")
        all_passed = False
    elif _is_autorouter_alias(settings.bench_model) and settings.bench_model.lower() != settings.bench_model_normalized().lower():
        # Only reject the ":free" suffix if it's the full token (auto-router alias)
        pass  # Gemini models never end in :free
    elif settings.bench_model.lower() in _REJECTED_BENCH_MODELS:
        messages.append(f"[FAIL] BENCH_MODEL '{settings.bench_model}' is a banned alias — use an explicit model ID")
        all_passed = False

    # --- Provider must be explicitly configured ---
    if not settings.base_url:
        messages.append("[FAIL] PROVIDER_BASE_URL is not set — the benchmark provider must be declared explicitly")
        all_passed = False

    if not settings.api_key:
        messages.append("[FAIL] No API key configured — set PROVIDER_API_KEY in your .env file")
        all_passed = False

    # --- OpenRouter is not allowed for official benchmark unless --allow-openrouter ---
    if settings.provider_type == "openrouter" and not allow_openrouter:
        messages.append(
            "[FAIL] Benchmark must run on the Gemini free tier; OpenRouter is not allowed for official results"
        )
        all_passed = False

    # --- Gemini-specific checks ---
    if settings.provider_type == "gemini":
        # Key must look like a Google key
        if settings.api_key and not settings.key_looks_like_google():
            if settings.key_looks_like_openrouter():
                messages.append(
                    f"[FAIL] OpenRouter key (sk-or-...) used with Google endpoint — "
                    f"set PROVIDER_API_KEY to a Google AI Studio key (starts with 'AIza' or 'AQ.')"
                )
            else:
                messages.append(
                    f"[FAIL] PROVIDER_API_KEY does not look like a Google key (expected prefix 'AIza' or 'AQ.', "
                    f"key length={settings.key_length()})"
                )
            all_passed = False

        # Model must not use the "google/" owner prefix on Gemini's own endpoint
        if settings.bench_model_has_google_prefix():
            messages.append(
                f"[WARN] BENCH_MODEL '{settings.bench_model}' has an 'google/' prefix which is "
                f"not used by the Gemini endpoint. Normalised to '{model_norm}'. "
                f"Update BENCH_MODEL in your .env to remove the prefix."
            )
            # This is a warning, not a fail — normalized value will be used at runtime

        # openrouter/free is explicitly banned even if provider is gemini
        if settings.bench_model.lower() == "openrouter/free":
            messages.append("[FAIL] BENCH_MODEL 'openrouter/free' is an OpenRouter alias, not a Gemini model ID")
            all_passed = False

    # --- Warn if legacy OPENROUTER_* vars are also set while PROVIDER_* wins ---
    if settings.source == "PROVIDER" and settings.openrouter_legacy_vars_set:
        messages.append(
            "[WARN] One or more OPENROUTER_* environment variables are set alongside PROVIDER_* variables. "
            "PROVIDER_* takes precedence; the OPENROUTER_* values are ignored."
        )

    return all_passed, messages


def validate_key_only(settings: ProviderSettings) -> Tuple[bool, list]:
    """Lightweight key presence check (used by preflight item #2).

    Returns (passed, messages). Never prints the key value.
    """
    messages: list = []
    if not settings.api_key:
        return False, ["[FAIL] Provider API Key: Missing or empty in environment"]

    # Reject obvious placeholder strings
    if settings.api_key.lower() in {
        "your_google_ai_studio_key_here",
        "your_openrouter_api_key_here",
        "dummy",
        "mock",
    }:
        return False, ["[FAIL] Provider API Key: Placeholder value detected — fill in a real key"]

    verdict_parts = [f"length={settings.key_length()}"]
    if settings.provider_type == "gemini":
        if settings.key_looks_like_google():
            verdict_parts.append("looks like a Google key ✓")
        elif settings.key_looks_like_openrouter():
            verdict_parts.append("WARNING: looks like an OpenRouter key on the Gemini endpoint!")
            messages.append(
                "[FAIL] Provider API Key: OpenRouter key (sk-or-...) used with the Google endpoint"
            )
            return False, messages
        else:
            verdict_parts.append("WARNING: does not start with 'AIza' or 'AQ.'")
    elif settings.provider_type == "openrouter":
        if settings.key_looks_like_openrouter():
            verdict_parts.append("looks like an OpenRouter key ✓")
        else:
            verdict_parts.append("non-standard key shape")

    messages.append(f"[PASS] Provider API Key: Configured ({', '.join(verdict_parts)})")
    return True, messages


# ---------------------------------------------------------------------------
# Human-readable provider summary line (safe to print in logs/preflight)
# ---------------------------------------------------------------------------

def provider_summary_line(settings: ProviderSettings) -> str:
    """Returns a one-line summary safe to print (no key content)."""
    return (
        f"Provider: {settings.provider_type} ({settings.host})  "
        f"| Model: {settings.bench_model or '(unset)'}  "
        f"| Key length: {settings.key_length()}"
    )


# ---------------------------------------------------------------------------
# Normalize model ID for actual use in API calls
# ---------------------------------------------------------------------------

def effective_model_id(settings: ProviderSettings) -> str:
    """Returns the model ID to actually send to the provider.

    For Gemini, strips the redundant 'google/' prefix if present.
    For all others, returns bench_model unchanged.
    """
    return settings.bench_model_normalized() or settings.bench_model

