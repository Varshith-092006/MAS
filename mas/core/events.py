"""Append-only run event logging and notification system."""

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
import re

from mas.db.models import AgentEvent
from mas.db.session import get_session

# Secret patterns to redact from summaries
SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE),
    re.compile(r"password=['\"][^'\"]+['\"]", re.IGNORECASE),
    re.compile(r"bearer\s+[a-zA-Z0-9\._\-]+", re.IGNORECASE),
]


def redact_secrets(text: str) -> str:
    """Redacts API keys and secrets from logged text."""
    if not text:
        return ""
    result = text
    for pattern in SECRET_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result


class EventLogger:
    """Manages append-only events for runs."""

    def __init__(self):
        self._subscribers: List[Callable[[Dict[str, Any]], None]] = []

    def subscribe(self, callback: Callable[[Dict[str, Any]], None]):
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[Dict[str, Any]], None]):
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def emit(
        self,
        run_id: str,
        agent: str,
        event: str,
        status: str = "success",
        summary: str = "",
        db_session=None,
    ) -> AgentEvent:
        redacted = redact_secrets(summary)
        now = datetime.utcnow()

        event_obj = AgentEvent(
            run_id=run_id,
            agent=agent,
            event=event,
            status=status,
            redacted_summary=redacted,
            created_at=now,
        )

        # Save to DB
        own_session = False
        if db_session is None:
            db_session = get_session()
            own_session = True

        try:
            db_session.add(event_obj)
            db_session.commit()
            seq = event_obj.seq
        except Exception:
            db_session.rollback()
            seq = None
        finally:
            if own_session:
                db_session.close()

        # Notify subscribers
        event_dict = {
            "seq": seq,
            "run_id": run_id,
            "agent": agent,
            "event": event,
            "status": status,
            "summary": redacted,
            "timestamp": now.isoformat(),
        }

        for sub in self._subscribers:
            try:
                sub(event_dict)
            except Exception:
                pass

        return event_obj


event_logger = EventLogger()
