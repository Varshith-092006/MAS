"""Diagnostic test for developer prompt reasoning effort=low, governed by ProviderQuotaGovernor."""

import os
import sys
import json
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mas.core.governor import global_governor, GovernedHTTPClient


def run_test():
    allowed, status, meta = global_governor.evaluate_dispatch_permission("diagnostic", "test_dev_effort_low")
    if not allowed:
        print(f"DISPATCH BLOCKED BY GOVERNOR: {status} ({meta.get('reason')})")
        sys.exit(0)

    key = os.environ.get("OPENROUTER_API_KEY")
    model_id = "cohere/north-mini-code:free"

    prompt = (
        "Task: CSV Sales Summary CLI\n"
        "Write a concise, complete Python script `main.py` that:\n"
        "1. Reads a CSV with product, quantity, unit_price.\n"
        "2. Validates columns and numeric inputs.\n"
        "3. Computes per-product revenue (quantity * unit_price) and total revenue.\n"
        "4. Handles empty CSV (total 0) and skips malformed rows without crashing.\n"
        "5. Has a CLI entry point: `if __name__ == '__main__':` that accepts a csv path from sys.argv.\n"
        "6. Has a self-test function `run_tests()` that tests normal, empty, and malformed CSV.\n\n"
        "Return JSON matching CodePatch:\n"
        '{"files": ["main.py"], "file_contents": {"main.py": "<python code>"}, "summary": "Sales CLI implementation", "tests_expected": ["test_sales"]}\n'
        "Output ONLY the JSON object. Keep reasoning brief."
    )

    messages = [
        {
            "role": "system",
            "content": "You are DeveloperAgent. Output ONLY valid CodePatch JSON. Be concise in reasoning.",
        },
        {"role": "user", "content": prompt},
    ]

    payload = {
        "model": model_id,
        "messages": messages,
        "temperature": 0.0,
        "seed": 42,
        "max_tokens": 4000,
        "reasoning": {"effort": "low"},
        "provider": {"allow_fallbacks": False},
    }

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/mas-team/mas",
        "X-Title": "MAS Multi-Agent Research",
    }

    print(f"Testing Developer prompt with effort=low, max_tokens=4000...")
    with GovernedHTTPClient(timeout=90.0, request_type="SCRATCH_DIAGNOSTIC", target=model_id, source="scratch/test_dev_effort_low.py") as client:
        resp = client.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers)
    print("Status Code:", resp.status_code)
    if resp.status_code == 200:
        data = resp.json()
        choice = data["choices"][0]
        msg = choice.get("message", {})
        content = msg.get("content")
        reasoning = msg.get("reasoning")
        print("Finish Reason:", choice.get("finish_reason"))
        print("Content preview:", repr(content[:300] if content else None))
        print("Reasoning preview:", repr(reasoning[:200] if reasoning else None))
        print("Usage:", data.get("usage"))
    else:
        print("Error:", resp.text)


if __name__ == "__main__":
    run_test()
