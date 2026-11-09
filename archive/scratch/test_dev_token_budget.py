"""Diagnostic test for token budget with Developer prompt, governed by ProviderQuotaGovernor."""

import os
import sys
import json
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mas.core.governor import global_governor, GovernedHTTPClient


def run_test():
    allowed, status, meta = global_governor.evaluate_dispatch_permission("diagnostic", "test_dev_token_budget")
    if not allowed:
        print(f"DISPATCH BLOCKED BY GOVERNOR: {status} ({meta.get('reason')})")
        sys.exit(0)

    key = os.environ.get("OPENROUTER_API_KEY")
    model_id = "cohere/north-mini-code:free"

    prompt = (
        "Task Requirement:\n"
        "CSV Sales Summary CLI: Read a CSV file containing product name, quantity, and unit price. "
        "Validate required columns and numeric inputs. "
        "Compute per-product revenue (quantity * unit_price) and total revenue correctly. "
        "Handle an empty CSV cleanly without crashing. "
        "Handle malformed rows without silently inventing data. "
        "Provide a usable command-line entry point in main.py. "
        "Include automated behavioral tests in test_main.py for normal and failure cases. "
        "Use the Python standard library.\n\n"
        "Return a valid JSON object matching CodePatch:\n"
        "{\n"
        '  "files": ["main.py", "test_main.py"],\n'
        '  "file_contents": {"main.py": "<code string>", "test_main.py": "<code string>"},\n'
        '  "summary": "Implementation of CSV Sales Summary CLI and behavioral tests",\n'
        '  "tests_expected": ["test_normal_sales", "test_empty_csv", "test_malformed_csv"]\n'
        "}\n"
        "Output ONLY the JSON object."
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are DeveloperAgent. Output ONLY a valid JSON object matching CodePatch. "
                "Do NOT include conversational text, reasoning, or markdown formatting outside the JSON object. "
                "Provide complete, executable code without ellipsis or placeholders."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    payload = {
        "model": model_id,
        "messages": messages,
        "temperature": 0.0,
        "seed": 42,
        "max_tokens": 5000,
        "provider": {"allow_fallbacks": False},
    }

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/mas-team/mas",
        "X-Title": "MAS Multi-Agent Research",
    }

    print(f"Testing Developer prompt with max_tokens=5000 on {model_id}...")
    with GovernedHTTPClient(timeout=90.0, request_type="SCRATCH_DIAGNOSTIC", target=model_id, source="scratch/test_dev_token_budget.py") as client:
        resp = client.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers)
    print("Status Code:", resp.status_code)
    if resp.status_code == 200:
        data = resp.json()
        choice = data["choices"][0]
        msg = choice.get("message", {})
        content = msg.get("content")
        reasoning = msg.get("reasoning")
        print("Finish Reason:", choice.get("finish_reason"))
        print("Content:", repr(content[:400] if content else None))
        print("Reasoning preview:", repr(reasoning[:200] if reasoning else None))
        print("Usage:", data.get("usage"))
        print("Actual model:", data.get("model"))
        print("Parsed JSON keys:")
        try:
            parsed = json.loads(content)
            print("Keys:", list(parsed.keys()))
            print("Files in file_contents:", list(parsed.get("file_contents", {}).keys()))
        except Exception as e:
            print("JSON parse error:", e)
    else:
        print("Error:", resp.text)


if __name__ == "__main__":
    run_test()
