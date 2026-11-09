import json
import os
import sys
from dotenv import load_dotenv

load_dotenv(override=True)

from mas.core.llm import OpenRouterProvider
from mas.core.governor import global_governor

def run_preflight():
    provider = OpenRouterProvider()
    meta = provider.check_key_metadata()
    
    # Redact any key string if returned in raw form
    sanitized = dict(meta)
    if "key" in sanitized:
        sanitized["key"] = "REDACTED"
        
    print("--- PREFLIGHT KEY METADATA ---")
    print(json.dumps(sanitized, indent=2))
    
    print("\n--- GOVERNOR LEDGER STATS AFTER PREFLIGHT ---")
    stats = global_governor.get_ledger_stats()
    print(json.dumps(stats, indent=2))

if __name__ == "__main__":
    run_preflight()
