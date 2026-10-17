"""Controlled live smoke test using verified free model cohere/north-mini-code:free.
Executes Step 7 validation on a small self-contained artifact in an isolated workspace.
"""

import os
import sys
import json
import tempfile
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()

from mas.core.llm import OpenRouterProvider, token_logger
from mas.core.schemas import CodePatch
from mas.analysis.sandbox import SandboxRunner
from eval.neutral_evaluator import NeutralEvaluator

def run_live_smoke_pilot():
    from mas.core.governor import global_governor
    allowed, status, meta = global_governor.evaluate_dispatch_permission("diagnostic", "test_pilot_live_smoke")
    if not allowed:
        print(f"DISPATCH BLOCKED BY GOVERNOR: {status} ({meta.get('reason')})")
        return

    model_id = "cohere/north-mini-code:free"
    print(f"=== STEP 6 & 7: LIVE SMOKE GENERATION ON {model_id} ===")

    provider = OpenRouterProvider(default_model=model_id)

    prompt = (
        "Task Requirement:\n"
        "Create a Python application with a function `compute_sum(a: int, b: int) -> int` that returns the sum of two integers.\n"
        "Include an executable entry point in `main.py` with `if __name__ == '__main__':` that asserts `compute_sum(10, 25) == 35` and prints 'Sum verified successfully.'.\n\n"
        "Acceptance Criteria:\n"
        "- compute_sum(a, b) returns a + b\n"
        "- main.py executes cleanly without errors\n\n"
        "Return a valid CodePatch JSON with keys: files, file_contents, summary, tests_expected."
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are DeveloperAgent. Output ONLY a valid JSON object matching the CodePatch schema, starting with { and ending with }. "
                "Do NOT write any thinking, explanation, or conversational markdown outside the JSON object. "
                "Generate complete, executable Python code with entry point main.py. Do NOT use placeholders."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    print("Dispatching single live generation request...")
    res = provider.generate(
        messages=messages,
        model=model_id,
        response_schema=CodePatch,
        run_id="live-smoke-pilot-01",
        agent_name="developer",
        max_tokens=2500,
    )

    print("\n[LIVE RESPONSE METADATA]")
    print(f"  - Requested Model: {res.requested_model}")
    print(f"  - Actual Served Model: {res.model_name}")
    print(f"  - Request ID: {res.request_id}")
    print(f"  - Input Tokens: {res.input_tokens}")
    print(f"  - Output Tokens: {res.output_tokens}")
    print(f"  - Total Tokens: {res.total_tokens}")
    print(f"  - Verified Generation Cost: ${res.estimated_cost}")
    print(f"  - Latency: {res.latency_ms} ms")

    if not res.parsed_json or "file_contents" not in res.parsed_json:
        print("[FAIL] Output did not contain valid CodePatch file_contents.")
        print(f"Raw response preview: {res.text[:300]}")
        return

    patch_data = res.parsed_json
    print(f"\n[GENERATED ARTIFACT FILES]: {list(patch_data.get('file_contents', {}).keys())}")

    # Write to disposable sandbox directory
    with tempfile.TemporaryDirectory() as tmp_dir:
        for fname, content in patch_data["file_contents"].items():
            fpath = os.path.join(tmp_dir, fname)
            os.makedirs(os.path.dirname(fpath), exist_ok=True)
            with open(fpath, "w", encoding="utf-8") as fh:
                fh.write(content)

        print("\n[SANDBOX EXECUTION]")
        sandbox = SandboxRunner()
        exec_res = sandbox.smoke_run(tmp_dir, allow_fallback=True)
        print(f"  - Exit Code: {exec_res.exit_code}")
        print(f"  - Is Success: {exec_res.is_success}")
        print(f"  - Duration: {exec_res.duration_ms} ms")
        print(f"  - Stdout: {exec_res.stdout.strip()}")
        if exec_res.stderr:
            print(f"  - Stderr: {exec_res.stderr.strip()}")

        print("\n[NEUTRAL EVALUATOR AUDIT]")
        evaluator = NeutralEvaluator()
        eval_res = evaluator.evaluate_project(
            workspace_path=tmp_dir,
            requirement="Create compute_sum function that returns sum of two integers.",
            persist_to_db=False,
        )
        print(f"  - Evaluator Version: {eval_res.get('evaluator_version')}")
        print(f"  - Completeness (C): {eval_res.get('completeness')}")
        print(f"  - Executability (E): {eval_res.get('executability')}")
        print(f"  - Consistency (S): {eval_res.get('consistency')}")
        print(f"  - Quality (Q = C*E*S): {eval_res.get('quality')}")
        print(f"  - Level 1 Shared Smoke: {eval_res.get('shared_test')}")

if __name__ == "__main__":
    run_live_smoke_pilot()
