"""List available models from the configured provider endpoint.

Reads provider settings via eval.provider_config (PROVIDER_* precedence over OPENROUTER_*).
Prints "Provider: <type> (<host>)" at the top so a wrong provider is immediately obvious.
NEVER prints, logs, or discloses the API key or any part of it.
"""

import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import httpx

# Use the central provider config module
sys.path.insert(0, os.path.abspath("."))
from eval.provider_config import resolve_provider_settings, provider_summary_line


def list_models() -> None:
    settings = resolve_provider_settings()

    # Print provider info first so a wrong endpoint is immediately obvious.
    print(f"Provider: {settings.provider_type} ({settings.host})")
    print(f"Endpoint: {settings.base_url}/models")
    print(f"Key length: {settings.key_length()} (value not shown)")
    print("-" * 60)

    if not settings.api_key:
        print("[ERROR] No API key found in environment.")
        print("Set PROVIDER_API_KEY in your .env file (copy from .env.example).")
        sys.exit(1)

    url = f"{settings.base_url}/models"
    headers = {"Authorization": f"Bearer {settings.api_key}"}

    try:
        resp = httpx.get(url, headers=headers, timeout=30.0)
        if resp.status_code != 200:
            print(f"[ERROR] Provider returned HTTP {resp.status_code}: {resp.text[:300]}")
            sys.exit(1)

        data = resp.json()

        # Both OpenAI-compatible ({"data": [...]}) and plain list responses
        models = data.get("data", [])
        if not models and isinstance(data, list):
            models = data

        print(f"\nFound {len(models)} models at this endpoint:\n" + "-" * 60)
        for m in models:
            if isinstance(m, dict):
                m_id = m.get("id", "unknown")
                # For Gemini responses: strip "models/" prefix to get the bare ID to use in BENCH_MODEL
                display_id = m_id[len("models/"):] if m_id.startswith("models/") else m_id
                owned_by = m.get("owned_by", "")
                note = f" (by {owned_by})" if owned_by else ""
                print(f" - {display_id}{note}")
            else:
                print(f" - {m}")
        print("-" * 60)
        print("Copy the exact Flash Lite model ID above and set it as BENCH_MODEL in your .env.")
        if settings.provider_type == "gemini":
            print("Note: Gemini IDs do NOT include a 'google/' prefix. Example: gemini-3.5-flash-lite")
        elif settings.provider_type == "openrouter":
            print("Note: OpenRouter is NOT the benchmark provider. Switch to the Gemini API for official runs.")
    except Exception as exc:
        print(f"[ERROR] Failed to connect to provider endpoint: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    list_models()
