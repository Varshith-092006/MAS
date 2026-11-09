"""Verifies OpenRouter API key authentication and model metadata with strict secret redaction."""

import os
import sys
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

def verify_auth_and_model():
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from mas.core.governor import global_governor
    allowed, status, meta = global_governor.evaluate_dispatch_permission("diagnostic", "verify_openrouter_auth")
    if not allowed:
        print(f"DISPATCH BLOCKED BY GOVERNOR: {status} ({meta.get('reason')})")
        sys.exit(0)

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("[FAIL] OPENROUTER_API_KEY is not set.")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    from mas.core.governor import GovernedHTTPClient
    print("Step 4.1 — Verifying key authentication via /auth/key ...")
    try:
        with GovernedHTTPClient(timeout=30.0, request_type="KEY_METADATA", target="/api/v1/auth/key", source="scratch/verify_openrouter_auth.py") as client:
            resp = client.get("https://openrouter.ai/api/v1/auth/key", headers=headers)
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        sys.exit(1)

    if resp.status_code != 200:
        print(f"[FAIL] OpenRouter authentication failed with HTTP {resp.status_code}")
        try:
            err_data = resp.json()
            err_msg = err_data.get("error", {}).get("message", resp.text)
            print(f"Message: {err_msg}")
        except Exception:
            print(f"Response: {resp.text[:200]}")
        sys.exit(1)

    key_data = resp.json().get("data", {})
    print("[SUCCESS] Authentication verified!")
    print(f"  - Key Label: {key_data.get('label', 'unnamed')}")
    print(f"  - Usage (USD): ${key_data.get('usage', 0.0):.6f}")
    print(f"  - Limit (USD): {key_data.get('limit')}")
    print(f"  - Is Free Tier: {key_data.get('is_free_tier')}")
    rate_limit = key_data.get("rate_limit", {})
    print(f"  - Rate Limit Requests: {rate_limit.get('requests')} per {rate_limit.get('interval')}")

    print("\nStep 4.2 — Verifying model metadata for 'qwen/qwen-2.5-coder-32b-instruct:free' ...")
    try:
        with GovernedHTTPClient(timeout=30.0, request_type="SCRATCH_DIAGNOSTIC", target="openrouter/models", source="scratch/verify_openrouter_auth.py") as client:
            m_resp = client.get("https://openrouter.ai/api/v1/models")
    except Exception as e:
        print(f"[ERROR] Failed to fetch models catalog: {e}")
        sys.exit(1)

    if m_resp.status_code != 200:
        print(f"[FAIL] Failed to retrieve models catalog: HTTP {m_resp.status_code}")
        sys.exit(1)

    models_list = m_resp.json().get("data", [])
    target_id = "qwen/qwen-2.5-coder-32b-instruct:free"
    matched = next((m for m in models_list if m.get("id") == target_id), None)

    if not matched:
        print(f"[WARN] Exact model '{target_id}' not found in active catalog. Checking other free models...")
        free_models = [m.get("id") for m in models_list if ":free" in m.get("id", "")]
        print(f"Available free models: {free_models[:10]}")
        sys.exit(1)

    pricing = matched.get("pricing", {})
    prompt_price = float(pricing.get("prompt", 0.0))
    completion_price = float(pricing.get("completion", 0.0))
    context_length = matched.get("context_length", 0)

    print(f"[SUCCESS] Model '{target_id}' found and verified!")
    print(f"  - Model ID: {matched.get('id')}")
    print(f"  - Name: {matched.get('name')}")
    print(f"  - Context Window: {context_length:,} tokens")
    print(f"  - Advertised Prompt Price / Token: ${prompt_price}")
    print(f"  - Advertised Completion Price / Token: ${completion_price}")
    print(f"  - Verified Advertised Zero Cost: {prompt_price == 0.0 and completion_price == 0.0}")

if __name__ == "__main__":
    verify_auth_and_model()
