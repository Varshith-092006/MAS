import os
import sys
import json
import httpx
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mas.core.governor import global_governor
allowed, status, meta = global_governor.evaluate_dispatch_permission("diagnostic", "diagnose_reasoning")
if not allowed:
    print(f"DISPATCH BLOCKED BY GOVERNOR: {status} ({meta.get('reason')})")
    sys.exit(0)

key = os.environ.get("OPENROUTER_API_KEY")
if not key:
    print("NO_KEY")
    exit(1)

model_id = "cohere/north-mini-code:free"
headers = {
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://github.com/mas-team/mas",
    "X-Title": "MAS Multi-Agent Research",
}

configurations = [
    ("default (none)", None),
    ("effort: low", {"effort": "low"}),
    ("max_tokens: 100", {"max_tokens": 100}),
    ("max_tokens: 0", {"max_tokens": 0}),
    ("exclude: true", {"exclude": True}),
]

for label, r_cfg in configurations:
    print(f"\n--- Testing configuration: {label} ---")
    payload = {
        "model": model_id,
        "messages": [
            {"role": "user", "content": "Return a JSON object with key 'result' and value 42. Output only JSON."}
        ],
        "temperature": 0.0,
        "seed": 42,
        "max_tokens": 500,
        "provider": {"allow_fallbacks": False},
    }
    if r_cfg is not None:
        payload["reasoning"] = r_cfg

    try:
        from mas.core.governor import GovernedHTTPClient
        with GovernedHTTPClient(timeout=30.0, request_type="SCRATCH_DIAGNOSTIC", target=model_id, source="scratch/diagnose_reasoning.py") as client:
            resp = client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=payload,
                headers=headers,
            )
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            choice = data["choices"][0]
            finish_reason = choice.get("finish_reason")
            msg = choice.get("message", {})
            content = msg.get("content", "")
            reasoning = msg.get("reasoning", "")
            usage = data.get("usage", {})
            ct_details = usage.get("completion_tokens_details", {})
            
            print(f"Finish Reason: {finish_reason}")
            print(f"Content: {repr(content[:100])}")
            print(f"Has reasoning field in message: {bool(reasoning)} (len={len(reasoning)})")
            print(f"Prompt Tokens: {usage.get('prompt_tokens')}")
            print(f"Completion Tokens: {usage.get('completion_tokens')}")
            print(f"Reasoning Tokens: {ct_details.get('reasoning_tokens')}")
            print(f"Total Tokens: {usage.get('total_tokens')}")
            print(f"Cost: {usage.get('cost')}")
        else:
            print(f"Error ({resp.status_code}): {resp.text[:200]}")
    except Exception as e:
        print(f"Exception: {e}")
