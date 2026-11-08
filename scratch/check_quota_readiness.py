import os
from datetime import datetime, timezone
import httpx
from mas.core.governor import global_governor

utc_now = datetime.now(timezone.utc)
stats = global_governor.get_stats()

print("Current UTC:", utc_now.isoformat())
print("Current UTC Date:", utc_now.strftime("%Y-%m-%d"))
print("Current UTC Time:", utc_now.strftime("%H:%M:%S"))
print("Governor UTC Date:", stats["utc_date"])
print("Transmissions Used Today:", stats["successful_model_calls"])
print("Daily Cap:", stats["internal_daily_cap"])
print("Remaining Transmissions Today:", stats["remaining_internal_attempts"])

# Seconds until UTC midnight reset
midnight_utc = datetime(utc_now.year, utc_now.month, utc_now.day, 23, 59, 59, 999999, tzinfo=timezone.utc)
seconds_remaining = (midnight_utc - utc_now).total_seconds()
hours = int(seconds_remaining // 3600)
mins = int((seconds_remaining % 3600) // 60)
secs = int(seconds_remaining % 60)
print(f"Time until UTC midnight reset: {hours}h {mins}m {secs}s")

# Check upstream OpenRouter key metadata via governor-compliant query if key is available
api_key = os.environ.get("OPENROUTER_API_KEY")
if api_key:
    try:
        resp = httpx.get(
            "https://openrouter.ai/api/v1/auth/key",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
        if resp.status_code == 200:
            kdata = resp.json().get("data", {})
            print("Upstream key label:", kdata.get("label"))
            print("Upstream usage (USD):", kdata.get("usage"))
            print("Upstream limit (USD):", kdata.get("limit"))
            print("Upstream is_free_tier:", kdata.get("is_free_tier"))
            rate_limit = kdata.get("rate_limit", {})
            print("Upstream rate_limit requests:", rate_limit.get("requests"))
            print("Upstream rate_limit interval:", rate_limit.get("interval"))
        else:
            print("Upstream key status code:", resp.status_code)
    except Exception as e:
        print("Upstream check error:", e)

