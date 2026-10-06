"""Integration and fault test for invalid artifact detection, retry, rollback, and recovery."""

import os
from pydantic import BaseModel, Field
import pytest

from mas.agents.base import BaseAgent
from mas.core.checkpoints import CheckpointManager
from mas.core.events import event_logger
from mas.core.llm import FakeLLMProvider
from mas.core.schemas import UserStory
from mas.core.state import create_initial_state
from mas.db.models import AgentEvent
from mas.db.session import get_session, init_db


class DummyTestAgent(BaseAgent):
    def run(self, state):
        return state


def test_invalid_artifact_retry_rollback_recovery(tmp_path):
    workspace = str(tmp_path / "ws_rollback")
    os.makedirs(workspace, exist_ok=True)
    test_file = os.path.join(workspace, "state.txt")
    with open(test_file, "w") as f:
        f.write("checkpoint_v1")

    cp_mgr = CheckpointManager(workspace)
    agent = DummyTestAgent(name="test_producer", llm=FakeLLMProvider(), checkpoint_manager=cp_mgr)

    run_id = "test-run-fault-rec"
    state = create_initial_state(run_id=run_id, requirement="dummy req", workspace_path=workspace)

    # Simulation call counter
    call_count = 0

    def faulty_producer(feedback=None):
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            # Modify file before invalid generation
            with open(test_file, "w") as f:
                f.write("corrupted_state_step1")
            # 1st attempt: Malformed UserStory (missing required fields)
            return {"malformed": True}

        elif call_count == 2:
            # 2nd attempt (retry once): still invalid
            with open(test_file, "w") as f:
                f.write("corrupted_state_step2")
            return {"id": "US-bad", "role": "admin"}  # missing action, goal

        elif call_count == 3:
            # 3rd attempt (after rollback): valid UserStory!
            return {
                "id": "US-recovered",
                "role": "admin",
                "action": "manage assets",
                "goal": "ensure recovery",
                "acceptance_criteria": ["recovered successfully"],
                "priority": "high",
                "estimate": 2,
            }

    # Execute produce_valid_artifact
    recovered_artifact = agent.produce_valid_artifact(
        "UserStory", faulty_producer, state, UserStory
    )

    assert recovered_artifact is not None
    assert recovered_artifact.id == "US-recovered"
    assert call_count == 3

    # Check that rollback restored workspace state file to checkpoint_v1
    with open(test_file, "r") as f:
        content = f.read()
    assert content == "checkpoint_v1", "Workspace must have been rolled back to checkpoint_v1 before successful rerun"

    # Verify audit events in DB
    with get_session() as session:
        events = session.query(AgentEvent).filter(AgentEvent.run_id == run_id).all()
        event_types = [e.event for e in events]
        assert "artifact_rejected" in event_types
        assert "rollback" in event_types
