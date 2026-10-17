"""Offline unit tests for OpenRouter HTTP error handling in mas/core/llm.py."""

from unittest.mock import patch
import httpx
import pytest

from mas.core.llm import (
    OpenRouterAPIError,
    OpenRouterProvider,
    redact_sensitive_string,
    sanitize_headers_dict,
)


def test_openrouter_error_402_preserves_diagnostics_and_metadata():
    """Verify that HTTP 402 captures message, reason, limit_source, and remedy_hint."""
    error_payload = {
        "error": {
            "message": "Key monthly spending limit reached",
            "code": 402,
            "metadata": {
                "reason": "monthly_key_budget_exceeded",
                "limit_source": "key_limit",
                "remedy_hint": "Increase the spending limit for this key in the OpenRouter dashboard.",
            },
        }
    }
    response_headers = {
        "Content-Type": "application/json",
        "X-Request-ID": "gen-test-402-diag",
        "Retry-After": "3600",
    }
    mock_resp = httpx.Response(
        402,
        json=error_payload,
        headers=response_headers,
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
    )

    provider = OpenRouterProvider(api_key="sk-or-v1-testkey12345678901234567890")

    with patch("httpx.Client.post", return_value=mock_resp):
        with pytest.raises(OpenRouterAPIError) as exc_info:
            provider.generate(
                [{"role": "user", "content": "hello"}],
                model="openai/gpt-4o",
            )

    err = exc_info.value
    # 1. Preserves upstream status code
    assert err.status_code == 402
    assert isinstance(err, RuntimeError)

    # 2. Captures all diagnostic fields
    assert err.error_message == "Key monthly spending limit reached"
    assert err.reason == "monthly_key_budget_exceeded"
    assert err.limit_source == "key_limit"
    assert err.remedy_hint == "Increase the spending limit for this key in the OpenRouter dashboard."
    assert err.retry_after == "3600"

    # 3. Message contains actual upstream cause, not a generic account credits assumption
    err_str = str(err)
    assert "(402)" in err_str
    assert "Key monthly spending limit reached" in err_str
    assert "monthly_key_budget_exceeded" in err_str
    assert "key_limit" in err_str
    assert "Increase the spending limit for this key" in err_str
    assert "Account credits depleted" not in err_str  # No false generic assumption!


def test_openrouter_error_429_rate_limit_with_retry_after():
    """Verify HTTP 429 captures rate limit message and Retry-After header."""
    error_payload = {
        "error": {
            "message": "Rate limit exceeded: 20 requests per minute allowed.",
            "code": 429,
        }
    }
    mock_resp = httpx.Response(
        429,
        json=error_payload,
        headers={"Retry-After": "60", "Content-Type": "application/json"},
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
    )

    provider = OpenRouterProvider(api_key="test-api-key")
    with patch("httpx.Client.post", return_value=mock_resp):
        with pytest.raises(OpenRouterAPIError) as exc_info:
            provider.generate([{"role": "user", "content": "hi"}], model="openai/gpt-4o")

    err = exc_info.value
    assert err.status_code == 429
    assert err.error_message == "Rate limit exceeded: 20 requests per minute allowed."
    assert err.retry_after == "60"
    assert "429" in str(err)


def test_openrouter_error_401_authentication():
    """Verify HTTP 401 captures authentication failure."""
    error_payload = {
        "error": {
            "message": "User API key not found or expired.",
            "code": 401,
        }
    }
    mock_resp = httpx.Response(
        401,
        json=error_payload,
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
    )

    provider = OpenRouterProvider(api_key="test-api-key")
    with patch("httpx.Client.post", return_value=mock_resp):
        with pytest.raises(OpenRouterAPIError) as exc_info:
            provider.generate([{"role": "user", "content": "hi"}], model="openai/gpt-4o")

    err = exc_info.value
    assert err.status_code == 401
    assert "User API key not found" in str(err)


def test_openrouter_error_redacts_api_keys_and_auth_headers():
    """Verify authorization headers, Bearer tokens, and secrets are redacted."""
    raw_secret_key = "sk-or-v1-abcdef1234567890abcdef1234567890"
    error_payload = {
        "error": {
            "message": f"Invalid key: Bearer {raw_secret_key} rejected",
            "metadata": {
                "reason": f"rejected key {raw_secret_key}",
            },
        }
    }
    mock_resp = httpx.Response(
        401,
        json=error_payload,
        headers={
            "Authorization": f"Bearer {raw_secret_key}",
            "X-Api-Key": raw_secret_key,
            "Set-Cookie": "session=secret_cookie_val",
            "Server": "OpenRouter-Edge",
        },
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
    )

    provider = OpenRouterProvider(api_key=raw_secret_key)
    with patch("httpx.Client.post", return_value=mock_resp):
        with pytest.raises(OpenRouterAPIError) as exc_info:
            provider.generate([{"role": "user", "content": "hi"}], model="openai/gpt-4o")

    err = exc_info.value
    err_str = str(err)

    # Secret key must NOT appear in message string
    assert raw_secret_key not in err_str
    assert "[REDACTED" in err_str

    # Sensitive headers must be sanitized
    assert err.get_header("Authorization") == "[REDACTED]"
    assert err.get_header("X-Api-Key") == "[REDACTED]"
    assert err.get_header("Set-Cookie") == "[REDACTED]"
    assert err.get_header("Server") == "OpenRouter-Edge"


def test_openrouter_error_handles_non_json_response():
    """Verify non-JSON error responses (e.g. HTML 502/503) are safely handled."""
    html_body = "<html><body><h1>502 Bad Gateway</h1>Cloudflare edge error</body></html>"
    mock_resp = httpx.Response(
        502,
        text=html_body,
        headers={"Content-Type": "text/html"},
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
    )

    provider = OpenRouterProvider(api_key="test-key")
    with patch("httpx.Client.post", return_value=mock_resp):
        with pytest.raises(OpenRouterAPIError) as exc_info:
            provider.generate([{"role": "user", "content": "hi"}], model="openai/gpt-4o")

    err = exc_info.value
    assert err.status_code == 502
    assert "502" in str(err)
    assert err.raw_body == html_body


def test_redact_sensitive_string_helper():
    """Verify redaction helper handles Bearer tokens and sk- keys."""
    raw = "Key sk-or-v1-abcdef1234567890 and Bearer 12345abcde67890-token"
    redacted = redact_sensitive_string(raw, api_key="sk-or-v1-abcdef1234567890")
    assert "sk-or-v1-abcdef1234567890" not in redacted
    assert "12345abcde67890-token" not in redacted
