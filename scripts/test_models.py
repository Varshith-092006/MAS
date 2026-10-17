"""Check model availability and verify real API responses on OpenRouter, governed by ProviderQuotaGovernor."""

import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()

from mas.core.governor import global_governor, GovernedHTTPClient

allowed, status, meta = global_governor.evaluate_dispatch_permission("diagnostic", "scripts/test_models.py")
if not allowed:
    print(f"DISPATCH BLOCKED BY GOVERNOR: {status} ({meta.get('reason')})")
    sys.exit(0)

api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    print("[ERROR] OPENROUTER_API_KEY not found in environment!")
    sys.exit(1)

model_name = "cohere/north-mini-code:free"
headers = {
    "Authorization": f"Bearer {api_key}",
    "HTTP-Referer": "http://localhost:8000",
    "X-Title": "MAS Multi-Agent Research Platform",
}

print(f"\n--- Testing model: {model_name} ---")
payload = {
    "model": model_name,
    "messages": [
        {"role": "user", "content": "Return a JSON object with key 'status' equal to 'ok'."}
    ],
    "response_format": {"type": "json_object"},
    "temperature": 0.0,
    "max_tokens": 50,
    "provider": {"allow_fallbacks": False},
}

with GovernedHTTPClient(timeout=30.0, request_type="SCRATCH_DIAGNOSTIC", target=model_name, source="scripts/test_models.py") as client:
    resp = client.post(
        "https://openrouter.ai/api/v1/chat/completions",
        json=payload,
        headers=headers,
    )
print(f"Status Code: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    ret_model = data.get("model", "unknown")
    usage = data.get("usage", {})
    req_id = data.get("id", "none")
    content = data["choices"][0]["message"]["content"]
    print(f"Success! Model ID returned: {ret_model}")
    print(f"Request ID: {req_id}")
    print(f"Usage: {usage}")
    print(f"Sample output: {content.strip()[:60]}")
else:
    print(f"Failed ({resp.status_code}): {resp.text[:200]}")
