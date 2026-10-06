"""End-to-end integration tests for Checkpoint 1 (CP1).

Verifies:
- 'mas run --model fake' works end-to-end on one SIMPLE task.
- 'mas run --model fake' works end-to-end on one STRUCTURED task.
- Schema validation, token logging, and event logs are recorded.
"""

import os
import shutil
import pytest
from mas.core.llm import FakeLLMProvider
from mas.core.workflow import MASWorkflow
from mas.db.models import Run, AgentEvent
from mas.db.session import get_session, init_db


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    db_file = tmp_path / "test_mas.db"
    db_url = f"sqlite:///{db_file}"
    from mas.db.session import get_engine
    engine = get_engine(db_url)
    init_db(engine)
    yield engine


def test_simple_task_end_to_end(tmp_path):
    workspace = str(tmp_path / "workspace_simple")
    os.makedirs(workspace, exist_ok=True)

    llm = FakeLLMProvider()
    workflow = MASWorkflow(llm=llm)

    simple_req = "Write a python calculator that performs basic arithmetic addition."
    state = workflow.run(
        requirement=simple_req,
        task_id="task_simple_01",
        model_name="fake",
        workspace_base=workspace,
    )

    assert state["status"] == "COMPLETED"
    assert state["complexity"] == "SIMPLE"
    assert state["architecture"] is None  # Architect should NOT run on SIMPLE
    assert "TaskPlan" in state["artifacts"]
    assert "CodePatch" in state["artifacts"]
    assert "ReviewReport" in state["artifacts"]
    assert "ReflectionDecision" in state["artifacts"]
    assert state["total_tokens"] > 0

    # Verify database records
    with get_session() as session:
        run = session.query(Run).filter(Run.run_id == state["run_id"]).first()
        assert run is not None
        assert run.status == "COMPLETED"

        events = session.query(AgentEvent).filter(AgentEvent.run_id == state["run_id"]).all()
        assert len(events) >= 5
        event_types = [e.event for e in events]
        assert "run_started" in event_types
        assert "run_completed" in event_types


def test_structured_task_end_to_end(tmp_path):
    workspace = str(tmp_path / "workspace_structured")
    os.makedirs(workspace, exist_ok=True)

    llm = FakeLLMProvider()
    workflow = MASWorkflow(llm=llm)

    structured_req = (
        "Build a multi-user inventory system with a SQLite database, "
        "user login authentication, admin and staff roles, REST API endpoints, "
        "analytics metrics reporting, and an approval workflow lifecycle."
    )
    state = workflow.run(
        requirement=structured_req,
        task_id="task_structured_01",
        model_name="fake",
        workspace_base=workspace,
    )

    assert state["status"] == "COMPLETED"
    assert state["complexity"] == "STRUCTURED"
    assert state["architecture"] is not None  # Architect MUST run on STRUCTURED
    assert "Architecture" in state["artifacts"]
    assert "UserStory" in state["artifacts"]
    assert "CodePatch" in state["artifacts"]
    assert "ReviewReport" in state["artifacts"]
    assert "ReflectionDecision" in state["artifacts"]
    assert state["total_tokens"] > 0

    # Verify database records
    with get_session() as session:
        run = session.query(Run).filter(Run.run_id == state["run_id"]).first()
        assert run is not None
        assert run.status == "COMPLETED"

        events = session.query(AgentEvent).filter(AgentEvent.run_id == state["run_id"]).all()
        architect_events = [e for e in events if e.agent == "architect"]
        assert len(architect_events) > 0, "Architect must emit events on STRUCTURED path"
