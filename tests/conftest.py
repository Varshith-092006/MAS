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
