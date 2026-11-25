"""Per-agent telemetry read from the persisted model_calls table (provider-reported usage).

Nothing here estimates tokens: every number is summed from ModelCall rows written by
TokenLogger.record_call, which stores the usage block returned by the provider.
"""

from typing import Any, Dict, Optional


def get_agent_breakdown(run_id: str, db_session=None) -> Dict[str, Dict[str, Any]]:
    """Returns {agent: {calls, input_tokens, output_tokens, total_tokens, latency_ms, cost}}."""
    from mas.db.models import ModelCall
    from mas.db.session import get_session

    own = db_session is None
    s = db_session or get_session()
    out: Dict[str, Dict[str, Any]] = {}
    try:
        for c in s.query(ModelCall).filter(ModelCall.run_id == run_id).all():
            a = out.setdefault(c.agent or "unknown", {
                "calls": 0, "input_tokens": 0, "output_tokens": 0,
                "total_tokens": 0, "latency_ms": 0, "cost": 0.0,
            })
            a["calls"] += 1
            a["input_tokens"] += c.input_tokens or 0
            a["output_tokens"] += c.output_tokens or 0
            a["total_tokens"] += c.total_tokens or 0
            a["latency_ms"] += c.latency_ms or 0
            a["cost"] = round(a["cost"] + (c.cost or 0.0), 6)
    except Exception:
        return {}
    finally:
        if own:
            s.close()
    return out


def summarize_breakdown(breakdown: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    tot = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "latency_ms": 0, "cost": 0.0}
    for v in breakdown.values():
        for k in tot:
            tot[k] += v.get(k, 0) or 0
    tot["cost"] = round(tot["cost"], 6)
    return tot


def pct_change(new: Optional[float], old: Optional[float]) -> Optional[float]:
    """Relative change in percent, None when undefined (missing data or old == 0)."""
    if new is None or old is None or old == 0:
        return None
    return round((new - old) / abs(old) * 100.0, 2)
