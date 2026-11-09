"""Diagnostic test script for OpenRouter response formats, governed by ProviderQuotaGovernor."""

import os
import sys
import json
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()

from mas.core.governor import global_governor, GovernedHTTPClient

allowed, status, meta = global_governor.evaluate_dispatch_permission("scratch", "test_or")
if not allowed:
    print(f"DISPATCH BLOCKED BY GOVERNOR: {status} ({meta.get('reason')})")
    sys.exit(0)

key = os.environ.get("OPENROUTER_API_KEY")
print("Key length:", len(key) if key else 0)

target_model = "cohere/north-mini-code:free"

with GovernedHTTPClient(request_type="SCRATCH_DIAGNOSTIC", target=target_model, source="scratch/test_or.py") as client:
    # Test 1: json_object
    r1 = client.post(
        "https://openrouter.ai/api/v1/chat/completions",
        json={
            "model": target_model,
            "messages": [{"role": "user", "content": 'Return JSON: {"status": "ok"}'}],
            "response_format": {"type": "json_object"},
            "provider": {"allow_fallbacks": False},
        },
        headers={"Authorization": f"Bearer {key}"},
        timeout=30.0,
    )
    print("Test 1 status:", r1.status_code, r1.text[:200])

    # Test 2: json_schema
    r2 = client.post(
        "https://openrouter.ai/api/v1/chat/completions",
        json={
            "model": target_model,
            "messages": [{"role": "user", "content": 'Return JSON: {"status": "ok"}'}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "StatusSchema",
                    "schema": {"type": "object", "properties": {"status": {"type": "string"}}},
                    "strict": True,
                },
            },
            "provider": {"allow_fallbacks": False},
        },
        headers={"Authorization": f"Bearer {key}"},
        timeout=30.0,
    )
    print("Test 2 status:", r2.status_code, r2.text[:200])
