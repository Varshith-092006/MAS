"""Pilot test for Gate E: Live free OpenRouter model probe.
Verifies model identity, pricing, availability, and schema handling without burning quota.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

from mas.core.llm import OpenRouterProvider, calculate_model_cost
from mas.core.schemas import TaskPlan

def test_qwen_pilot():
    from mas.core.governor import global_governor
    allowed, status, meta = global_governor.evaluate_dispatch_permission("diagnostic", "test_pilot_qwen")
    if not allowed:
        print(f"DISPATCH BLOCKED BY GOVERNOR: {status} ({meta.get('reason')})")
        return

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("SKIP: OPENROUTER_API_KEY not configured.")
        return

    model_id = "qwen/qwen-2.5-coder-32b-instruct:free"
    print(f"Testing live pilot call for free model: {model_id}")

    provider = OpenRouterProvider(default_model=model_id)
    messages = [
        {"role": "system", "content": "You are ManagerAgent. Output a valid TaskPlan JSON."},
        {"role": "user", "content": "Task: Create a simple function that adds two numbers. Return a TaskPlan JSON object with id, task_id, name, description, complexity, files, sprint_goals, acceptance_criteria, and ambiguities."},
    ]

    try:
        res = provider.generate(
            messages=messages,
            model=model_id,
            response_schema=TaskPlan,
            run_id="pilot-test-run-01",
            agent_name="manager",
            max_tokens=500,
        )
        print("=== PILOT CALL SUCCESSFUL ===")
        print(f"Requested Model: {res.requested_model}")
        print(f"Actual Served Model: {res.model_name}")
        print(f"Input Tokens: {res.input_tokens}")
        print(f"Output Tokens: {res.output_tokens}")
        print(f"Cost: ${res.estimated_cost}")
        print(f"Latency: {res.latency_ms} ms")
        print(f"Parsed JSON keys: {list(res.parsed_json.keys()) if res.parsed_json else None}")
        print(f"Content preview: {res.text[:200]}")
    except Exception as e:
        print(f"=== PILOT CALL FAILED ===")
        print(f"Error type: {type(e).__name__}")
        print(f"Error details: {e}")

if __name__ == "__main__":
    test_qwen_pilot()
