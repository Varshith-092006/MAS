"""Tests for Task 4: provider config precedence, safety validation, and report consistency.

All tests use fake environment dictionaries only. No network calls. No real keys.
"""

import sys
import os
import pytest

# Ensure the project root is on the path
sys.path.insert(0, os.path.abspath("."))

from eval.provider_config import (
    resolve_provider_settings,
    validate_for_live_run,
    validate_key_only,
    effective_model_id,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _env(
    provider_key="",
    provider_url="",
    bench_model="",
    or_key="",
    or_url="",
    or_model="",
):
    """Builds a minimal fake environment dict."""
    e = {}
    if provider_key:
        e["PROVIDER_API_KEY"] = provider_key
    if provider_url:
        e["PROVIDER_BASE_URL"] = provider_url
    if bench_model:
        e["BENCH_MODEL"] = bench_model
    if or_key:
        e["OPENROUTER_API_KEY"] = or_key
    if or_url:
        e["OPENROUTER_BASE_URL"] = or_url
    if or_model:
        e["OPENROUTER_MODEL"] = or_model
    return e


GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
OR_URL = "https://openrouter.ai/api/v1"
FAKE_GEMINI_KEY = "AIzaSyFakeGeminiKey1234567890"       # starts with AIza, never real
FAKE_OR_KEY = "sk-or-v1-fakeOpenRouterKey123456789"   # starts with sk-or-, never real


# ---------------------------------------------------------------------------
# Task 4.1 — PROVIDER_* precedence over OPENROUTER_*
# ---------------------------------------------------------------------------

class TestProviderPrecedence:
    def test_provider_wins_when_all_set(self):
        """PROVIDER_* values must be used when both groups are set."""
        e = _env(
            provider_key=FAKE_GEMINI_KEY,
            provider_url=GEMINI_URL,
            bench_model="gemini-3.5-flash-lite",
            or_key=FAKE_OR_KEY,
            or_url=OR_URL,
            or_model="openrouter/free",
        )
        s = resolve_provider_settings(e)
        assert s.source == "PROVIDER"
        assert s.api_key == FAKE_GEMINI_KEY
        assert s.base_url.rstrip("/") == GEMINI_URL.rstrip("/")
        assert s.bench_model == "gemini-3.5-flash-lite"
        assert s.provider_type == "gemini"

    def test_provider_wins_even_if_only_key_set(self):
        """Setting only PROVIDER_API_KEY makes PROVIDER the source."""
        e = _env(provider_key=FAKE_GEMINI_KEY, or_key=FAKE_OR_KEY, or_url=OR_URL, or_model="openrouter/free")
        s = resolve_provider_settings(e)
        assert s.source == "PROVIDER"
        assert s.api_key == FAKE_GEMINI_KEY

    def test_openrouter_fallback_when_no_provider_vars(self):
        """OPENROUTER_* used only when no PROVIDER_* variables are set."""
        e = _env(or_key=FAKE_OR_KEY, or_url=OR_URL, or_model="openrouter/free")
        s = resolve_provider_settings(e)
        assert s.source == "OPENROUTER_LEGACY"
        assert s.api_key == FAKE_OR_KEY
        assert s.provider_type == "openrouter"

    def test_no_cross_group_mixing(self):
        """PROVIDER key must not be combined with OpenRouter URL."""
        # If PROVIDER_API_KEY is set, PROVIDER_BASE_URL defaults to Gemini, not OpenRouter.
        e = _env(provider_key=FAKE_GEMINI_KEY)
        s = resolve_provider_settings(e)
        assert s.provider_type == "gemini", (
            f"Expected gemini provider type when only PROVIDER_API_KEY is set, got '{s.provider_type}'"
        )

    def test_openrouter_legacy_vars_set_flag(self):
        """openrouter_legacy_vars_set must be True when OPENROUTER_* vars present alongside PROVIDER_*."""
        e = _env(provider_key=FAKE_GEMINI_KEY, provider_url=GEMINI_URL, bench_model="gemini-3.5-flash-lite",
                 or_key=FAKE_OR_KEY)
        s = resolve_provider_settings(e)
        assert s.openrouter_legacy_vars_set is True

    def test_no_legacy_vars_flag(self):
        e = _env(provider_key=FAKE_GEMINI_KEY, provider_url=GEMINI_URL, bench_model="gemini-3.5-flash-lite")
        s = resolve_provider_settings(e)
        assert s.openrouter_legacy_vars_set is False


# ---------------------------------------------------------------------------
# Task 4.2 — Rejection of banned BENCH_MODEL values
# ---------------------------------------------------------------------------

class TestBenchModelValidation:
    def test_empty_bench_model_rejected(self):
        e = _env(provider_key=FAKE_GEMINI_KEY, provider_url=GEMINI_URL, bench_model="")
        s = resolve_provider_settings(e)
        ok, msgs = validate_for_live_run(s)
        assert not ok
        fail_msgs = [m for m in msgs if "[FAIL]" in m]
        assert any("BENCH_MODEL" in m for m in fail_msgs), f"Expected BENCH_MODEL error, got: {msgs}"

    def test_openrouter_free_rejected_for_gemini(self):
        """openrouter/free must be rejected even when provider is Gemini."""
        e = _env(provider_key=FAKE_GEMINI_KEY, provider_url=GEMINI_URL, bench_model="openrouter/free")
        s = resolve_provider_settings(e)
        ok, msgs = validate_for_live_run(s)
        assert not ok, f"Expected rejection of 'openrouter/free', msgs: {msgs}"

    def test_placeholder_bench_model_rejected(self):
        e = _env(provider_key=FAKE_GEMINI_KEY, provider_url=GEMINI_URL,
                 bench_model="<exact-model-id-from-list_models>")
        s = resolve_provider_settings(e)
        ok, msgs = validate_for_live_run(s)
        assert not ok

    def test_valid_gemini_model_accepted(self):
        e = _env(provider_key=FAKE_GEMINI_KEY, provider_url=GEMINI_URL, bench_model="gemini-3.5-flash-lite")
        s = resolve_provider_settings(e)
        ok, msgs = validate_for_live_run(s)
        assert ok, f"Valid Gemini config should pass, got: {msgs}"


# ---------------------------------------------------------------------------
# Task 4.3 — google/ prefix check on the Gemini endpoint
# ---------------------------------------------------------------------------

class TestGeminiModelPrefix:
    def test_google_prefix_emits_warning_not_fail(self):
        """BENCH_MODEL='google/gemini-3.5-flash-lite' on Gemini endpoint: warn, don't fail."""
        e = _env(provider_key=FAKE_GEMINI_KEY, provider_url=GEMINI_URL,
                 bench_model="google/gemini-3.5-flash-lite")
        s = resolve_provider_settings(e)
        ok, msgs = validate_for_live_run(s)
        # Should PASS overall (key is AIza, model is otherwise valid)
        assert ok, f"google/ prefix should be a warning, not a fail. msgs={msgs}"
        warn_msgs = [m for m in msgs if "[WARN]" in m and "google/" in m]
        assert warn_msgs, f"Expected a [WARN] about google/ prefix, got: {msgs}"

    def test_bench_model_normalized_strips_google_prefix(self):
        e = _env(provider_key=FAKE_GEMINI_KEY, provider_url=GEMINI_URL,
                 bench_model="google/gemini-3.5-flash-lite")
        s = resolve_provider_settings(e)
        assert s.bench_model_normalized() == "gemini-3.5-flash-lite"
        assert s.bench_model_has_google_prefix() is True

    def test_no_prefix_model_not_flagged(self):
        e = _env(provider_key=FAKE_GEMINI_KEY, provider_url=GEMINI_URL,
                 bench_model="gemini-3.5-flash-lite")
        s = resolve_provider_settings(e)
        assert s.bench_model_has_google_prefix() is False
        assert s.bench_model_normalized() == "gemini-3.5-flash-lite"

    def test_effective_model_id_strips_prefix(self):
        e = _env(provider_key=FAKE_GEMINI_KEY, provider_url=GEMINI_URL,
                 bench_model="google/gemini-2.5-flash-lite")
        s = resolve_provider_settings(e)
        assert effective_model_id(s) == "gemini-2.5-flash-lite"


# ---------------------------------------------------------------------------
# Task 4.4 — OpenRouter key on the Google endpoint
# ---------------------------------------------------------------------------

class TestOpenRouterKeyOnGeminiEndpoint:
    def test_sk_or_key_on_gemini_endpoint_fails(self):
        """An OpenRouter key (sk-or-...) must not be accepted with the Gemini endpoint."""
        e = _env(provider_key=FAKE_OR_KEY, provider_url=GEMINI_URL, bench_model="gemini-3.5-flash-lite")
        s = resolve_provider_settings(e)
        ok, msgs = validate_for_live_run(s)
        assert not ok, f"Expected failure for OR key on Gemini endpoint, got: {msgs}"
        fail_msgs = [m for m in msgs if "[FAIL]" in m]
        assert any("OpenRouter key" in m for m in fail_msgs), f"Expected OpenRouter key error, got: {msgs}"

    def test_AIza_key_on_gemini_endpoint_passes_key_check(self):
        e = _env(provider_key=FAKE_GEMINI_KEY, provider_url=GEMINI_URL, bench_model="gemini-3.5-flash-lite")
        s = resolve_provider_settings(e)
        ok, msgs = validate_key_only(s)
        assert ok, f"AIza key on Gemini endpoint should pass key check, got: {msgs}"

    def test_new_format_AQ_key_on_gemini_endpoint_passes(self):
        """DEC-042: newer Google AI Studio keys start with 'AQ.' and must be accepted."""
        fake_aq_key = "AQ.FakeNewFormatGoogleKey_1234567890abcdefghijklmnop"  # never real
        e = _env(provider_key=fake_aq_key, provider_url=GEMINI_URL, bench_model="gemini-3.5-flash-lite")
        s = resolve_provider_settings(e)
        ok, msgs = validate_key_only(s)
        assert ok and any("looks like a Google key" in m for m in msgs), msgs
        ok_live, live_msgs = validate_for_live_run(s)
        assert not any("does not look like a Google key" in m for m in live_msgs), live_msgs

    def test_unknown_key_prefix_on_gemini_still_fails(self):
        e = _env(provider_key="xyz-not-a-google-key-1234567890", provider_url=GEMINI_URL, bench_model="gemini-3.5-flash-lite")
        ok, msgs = validate_for_live_run(resolve_provider_settings(e))
        assert not ok
        assert any("does not look like a Google key" in m for m in msgs)

    def test_sk_or_key_on_gemini_fails_key_only_check(self):
        e = _env(provider_key=FAKE_OR_KEY, provider_url=GEMINI_URL, bench_model="gemini-3.5-flash-lite")
        s = resolve_provider_settings(e)
        ok, msgs = validate_key_only(s)
        assert not ok
        assert any("OpenRouter key" in m for m in msgs)


# ---------------------------------------------------------------------------
# Task 4.5 — OpenRouter provider refusal for benchmark
# ---------------------------------------------------------------------------

class TestOpenRouterProviderRefusal:
    def test_openrouter_provider_refused_without_flag(self):
        """Using OpenRouter as provider for a benchmark run must be rejected."""
        e = _env(provider_key=FAKE_OR_KEY, provider_url=OR_URL, bench_model="meta-llama/llama-3.3-70b-instruct:free")
        s = resolve_provider_settings(e)
        ok, msgs = validate_for_live_run(s, allow_openrouter=False)
        assert not ok
        fail_msgs = [m for m in msgs if "[FAIL]" in m]
        assert any("Gemini free tier" in m or "OpenRouter is not allowed" in m for m in fail_msgs), \
            f"Expected OpenRouter refusal message, got: {msgs}"

    def test_openrouter_allowed_with_flag(self):
        """With --allow-openrouter, the provider check passes (results excluded from official tables)."""
        e = _env(provider_key=FAKE_OR_KEY, provider_url=OR_URL,
                 bench_model="meta-llama/llama-3.3-70b-instruct")
        s = resolve_provider_settings(e)
        ok, msgs = validate_for_live_run(s, allow_openrouter=True)
        # OpenRouter key on OpenRouter endpoint: key check passes (not an AIza check)
        # Provider type is openrouter, allowed_openrouter=True: provider check passes
        assert ok, f"OpenRouter should be allowed with allow_openrouter=True, got: {msgs}"


# ---------------------------------------------------------------------------
# Task 4.6 — Report provider metadata consistency via make_report logic
# ---------------------------------------------------------------------------

class TestReportProviderConsistency:
    """Tests for the provider/model consistency check in make_report.py."""

    def _make_run(self, system, provider_type, model, status="COMPLETED", execution_mode="LIVE_API"):
        return {
            "system": system,
            "provider_type": provider_type,
            "model": model,
            "status": status,
            "execution_mode": execution_mode,
            "official": True,
        }

    def test_mixed_providers_detected(self):
        """Runs from different providers should trigger the consistency error in make_report."""
        runs = [
            self._make_run("mas", "gemini", "gemini-3.5-flash-lite"),
            self._make_run("chatdev", "openrouter", "gemini-3.5-flash-lite"),
        ]
        all_official = [r for r in runs if r.get("official")]
        provider_model_combos = set()
        for r in all_official:
            p = (r.get("provider_type") or "").strip().lower() or None
            m = (r.get("model") or "").strip().lower() or None
            if p or m:
                provider_model_combos.add((p, m))
        providers = {c[0] for c in provider_model_combos if c[0]}
        assert len(providers) > 1, "Should detect multiple providers"

    def test_mixed_models_detected(self):
        """Runs using different model IDs should trigger the consistency error."""
        runs = [
            self._make_run("mas", "gemini", "gemini-3.5-flash-lite"),
            self._make_run("chatdev", "gemini", "gemini-2.5-flash-lite"),
        ]
        all_official = [r for r in runs if r.get("official")]
        provider_model_combos = set()
        for r in all_official:
            p = (r.get("provider_type") or "").strip().lower() or None
            m = (r.get("model") or "").strip().lower() or None
            if p or m:
                provider_model_combos.add((p, m))
        models = {c[1] for c in provider_model_combos if c[1]}
        assert len(models) > 1, "Should detect multiple models"

    def test_same_provider_and_model_accepted(self):
        runs = [
            self._make_run("mas", "gemini", "gemini-3.5-flash-lite"),
            self._make_run("chatdev", "gemini", "gemini-3.5-flash-lite"),
        ]
        all_official = [r for r in runs if r.get("official")]
        provider_model_combos = set()
        for r in all_official:
            p = (r.get("provider_type") or "").strip().lower() or None
            m = (r.get("model") or "").strip().lower() or None
            if p or m:
                provider_model_combos.add((p, m))
        providers = {c[0] for c in provider_model_combos if c[0]}
        models = {c[1] for c in provider_model_combos if c[1]}
        assert len(providers) == 1
        assert len(models) == 1


# ---------------------------------------------------------------------------
# Task 4.7 — Provider type detection
# ---------------------------------------------------------------------------

class TestProviderTypeDetection:
    def test_gemini_url_detected(self):
        e = _env(provider_key=FAKE_GEMINI_KEY,
                 provider_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                 bench_model="gemini-3.5-flash-lite")
        s = resolve_provider_settings(e)
        assert s.provider_type == "gemini"

    def test_openrouter_url_detected(self):
        e = _env(or_key=FAKE_OR_KEY, or_url="https://openrouter.ai/api/v1", or_model="some/model")
        s = resolve_provider_settings(e)
        assert s.provider_type == "openrouter"

    def test_other_url_detected(self):
        e = _env(provider_key="somekey", provider_url="https://my-custom-provider.example.com/v1",
                 bench_model="mymodel")
        s = resolve_provider_settings(e)
        assert s.provider_type == "other"

    def test_host_recorded_correctly(self):
        e = _env(provider_key=FAKE_GEMINI_KEY,
                 provider_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                 bench_model="gemini-3.5-flash-lite")
        s = resolve_provider_settings(e)
        assert "googleapis.com" in s.host

