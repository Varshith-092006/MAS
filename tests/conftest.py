"""Pytest configuration for MAS test suite.
Ensures tests run in an isolated test database (test_mas.db) and never pollute active research records.
"""

import os
import pytest

# Force isolated test database before importing any database modules
os.environ["DATABASE_URL"] = "sqlite:///./test_mas.db"
os.environ["MAS_DISABLE_TORCH"] = "1"
os.environ["MAS_ALLOW_SUBPROCESS_SANDBOX"] = "1"
os.environ["MAS_LEDGER_PATH"] = os.path.abspath("./test_ledger.json")

# Hermetic provider settings (DEC-042). Several modules call load_dotenv() on import; dotenv never
# overrides variables that already exist, so pinning them here keeps the maintainer's real .env
# (real key, real BENCH_MODEL) out of the test run. Empty means "not configured".
for _var in (
    "PROVIDER_API_KEY", "PROVIDER_BASE_URL", "BENCH_MODEL", "GEMINI_API_KEY",
    "OPENROUTER_BASE_URL", "OPENROUTER_MODEL", "OPENROUTER_CHEAP_MODEL", "PROXY_BASE_URL", "OPENAI_API_KEY",
):
    os.environ[_var] = ""
# ChatDev's camel library only checks that a key variable exists; its model backend is mocked in tests.
os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"

# AGENTS.md rule 7: tests must not make network calls. Block every non-loopback connection.
import socket as _socket

_real_connect = _socket.socket.connect
_real_connect_ex = _socket.socket.connect_ex


def _is_loopback(address) -> bool:
    host = address[0] if isinstance(address, tuple) else address
    return isinstance(host, str) and (host in ("localhost", "::1") or host.startswith("127."))


def _guarded_connect(self, address):
    if self.family in (_socket.AF_INET, _socket.AF_INET6) and not _is_loopback(address):
        raise RuntimeError(f"Network access blocked in tests (attempted connection to {address!r})")
    return _real_connect(self, address)


def _guarded_connect_ex(self, address):
    if self.family in (_socket.AF_INET, _socket.AF_INET6) and not _is_loopback(address):
        raise RuntimeError(f"Network access blocked in tests (attempted connection to {address!r})")
    return _real_connect_ex(self, address)


_socket.socket.connect = _guarded_connect
_socket.socket.connect_ex = _guarded_connect_ex

from mas.db import session as db_session
from mas.db.models import Base

@pytest.fixture(scope="session", autouse=True)
def setup_isolated_test_database():
    """Initializes the isolated test database."""
    # Reset any cached engines
    db_session._engine = None
    db_session._SessionFactory = None
    engine = db_session.get_engine("sqlite:///./test_mas.db")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    # Cleanup after session
    try:
        Base.metadata.drop_all(bind=engine)
        if os.path.exists("test_mas.db"):
            os.remove("test_mas.db")
    except Exception:
        pass
    try:
        test_ledger = os.path.abspath("./test_ledger.json")
        if os.path.exists(test_ledger):
            os.remove(test_ledger)
    except Exception:
        pass
