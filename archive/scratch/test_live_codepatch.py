"""Diagnostic test for live CodePatch generation, governed by ProviderQuotaGovernor."""

import os
import sys
import json
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mas.core.governor import global_governor, GovernedHTTPClient


def run_test():
    allowed, status, meta = global_governor.evaluate_dispatch_permission("diagnostic", "test_live_codepatch")
    if not allowed:
        print(f"DISPATCH BLOCKED BY GOVERNOR: {status} ({meta.get('reason')})")
        sys.exit(0)

    key = os.environ.get("OPENROUTER_API_KEY")
    model_id = "cohere/north-mini-code:free"

    prompt = (
        "Task Requirement:\n"
        "Create a Python application with a function `compute_sum(a: int, b: int) -> int` that returns the sum of two integers.\n"
        "Include an executable entry point in `main.py` with `if __name__ == '__main__':` that asserts `compute_sum(10, 25) == 35` and prints 'Sum verified successfully.'.\n\n"
        "Return a valid JSON object matching this schema:\n"
        "{\n"
        '  "files": ["main.py"],\n'
        '  "file_contents": {"main.py": "<full python code>"},\n'
        '  "summary": "Implementation of compute_sum",\n'
        '  "tests_expected": ["compute_sum(10, 25) == 35"]\n'
        "}\n"
        "Output ONLY the JSON object. Do not include markdown or reasoning outside the JSON."
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are DeveloperAgent. Output ONLY a valid JSON object matching CodePatch. "
                "Do NOT include conversational text, reasoning, or markdown formatting outside the JSON object."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    payload = {
        "model": model_id,
        "messages": messages,
        "temperature": 0.0,
        "seed": 42,
        "max_tokens": 2000,
        "reasoning": {"max_tokens": 0},
        "provider": {"allow_fallbacks": False},
    }

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/mas-team/mas",
        "X-Title": "MAS Multi-Agent Software Engineering Team",
    }

    print(f"Dispatching live CodePatch generation to {model_id}...")
    with GovernedHTTPClient(timeout=90.0, request_type="SCRATCH_DIAGNOSTIC", target=model_id, source="scratch/test_live_codepatch.py") as client:
        resp = client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers=headers,
        )
    print("Status Code:", resp.status_code)
    if resp.status_code == 200:
        data = resp.json()
        choice = data["choices"][0]
        content = choice["message"].get("content", "")
        print("Model Response:\n", content[:300])
        print("Usage:", data.get("usage"))
    else:
        print("Error:", resp.text)


if __name__ == "__main__":
    run_test()
