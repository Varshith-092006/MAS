"""Inspect OpenRouter model catalog, governed by ProviderQuotaGovernor."""

import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()

from mas.core.governor import global_governor, GovernedHTTPClient

allowed, status, meta = global_governor.evaluate_dispatch_permission("scratch", "check_catalog")
if not allowed:
    print(f"DISPATCH BLOCKED BY GOVERNOR: {status} ({meta.get('reason')})")
    sys.exit(0)

key = os.environ.get("OPENROUTER_API_KEY")
if not key:
    print("NO_KEY")
    sys.exit(1)

headers = {"Authorization": f"Bearer {key}"}

with GovernedHTTPClient(request_type="SCRATCH_DIAGNOSTIC", target="openrouter/models", source="scratch/check_catalog.py") as client:
    resp = client.get("https://openrouter.ai/api/v1/models", headers=headers)
    if resp.status_code != 200:
        print(f"ERROR: {resp.status_code}")
        sys.exit(1)

    data = resp.json().get("data", [])
    free_models = [m for m in data if ":free" in m.get("id", "")]
    print(f"Total free models: {len(free_models)}")
    for m in free_models:
        mid = m.get("id")
        ctx = m.get("context_length")
        prompt_p = m.get("pricing", {}).get("prompt")
        comp_p = m.get("pricing", {}).get("completion")
        print(f"  {mid:50} | ctx={ctx:<7} | prompt={prompt_p} comp={comp_p}")
