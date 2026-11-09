"""List available models from the configured OpenAI-compatible provider endpoint.

Reads PROVIDER_API_KEY (or GEMINI_API_KEY / OPENROUTER_API_KEY) and PROVIDER_BASE_URL from the environment.
NEVER prints, logs, or discloses the API key.
"""

import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import httpx


def list_models():
    api_key = (
        os.environ.get("PROVIDER_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("OPENROUTER_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )

    if not api_key:
        print("[ERROR] No API key found in environment.")
        print("Please set PROVIDER_API_KEY (or GEMINI_API_KEY) in your environment or .env file.")
        sys.exit(1)

    base_url = (
        os.environ.get("PROVIDER_BASE_URL")
        or os.environ.get("OPENROUTER_BASE_URL")
        or "https://generativelanguage.googleapis.com/v1beta/openai/"
    ).rstrip("/")

    url = f"{base_url}/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    print(f"Querying models endpoint: {url} ...")
    try:
        resp = httpx.get(url, headers=headers, timeout=30.0)
        if resp.status_code != 200:
            print(f"[ERROR] Provider returned HTTP {resp.status_code}: {resp.text[:300]}")
            sys.exit(1)

        data = resp.json()
        models = data.get("data", [])
        if not models and isinstance(data, list):
            models = data

        print(f"\nFound {len(models)} models available at endpoint:\n" + "-" * 60)
        for m in models:
            if isinstance(m, dict):
                m_id = m.get("id", "unknown")
                owned_by = m.get("owned_by", "")
                display = f" - {m_id}" + (f" (by {owned_by})" if owned_by else "")
                print(display)
            else:
                print(f" - {m}")
        print("-" * 60)
        print("Select an exact Flash Lite model ID and set it as BENCH_MODEL in your environment/.env.")
    except Exception as exc:
        print(f"[ERROR] Failed to connect to provider endpoint: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    list_models()
