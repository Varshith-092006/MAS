"""Fault injection tests for F1 (malformed UML) and F2 (incomplete UserStory)."""

import os
import time
from typing import Any, Dict
import pytest

from mas.agents.base import BaseAgent
from mas.core.checkpoints import CheckpointManager
from mas.core.events import event_logger
from mas.core.llm import FakeLLMProvider
from mas.core.schemas import Architecture, UserStory
from mas.core.state import create_initial_state
from mas.db.models import AgentEvent
from mas.db.session import get_session


class FaultInjectorAgent(BaseAgent):
    def run(self, state):
        return state


def test_f1_malformed_uml_fault_injection(tmp_path):
    """F1: Injects malformed UML/Architecture artifact and verifies detection and recovery."""
    workspace = str(tmp_path / "ws_f1")
    os.makedirs(workspace, exist_ok=True)
    cp_mgr = CheckpointManager(workspace)
    agent = FaultInjectorAgent(name="architect_f1", llm=FakeLLMProvider(), checkpoint_manager=cp_mgr)

    run_id = "test-f1-malformed-uml"
    state = create_initial_state(run_id=run_id, requirement="inventory system", workspace_path=workspace)

    t0 = time.time()
    call_attempts = 0

    def faulty_architect_producer(feedback=None):
        nonlocal call_attempts
        call_attempts += 1
        if call_attempts == 1:
            # F1 Fault: Malformed Architecture (invalid fields)
            return {"components": "not_a_list", "uml_class_diagram": 12345}
        # Recovery on retry
        return {
            "components": [{"name": "Auth", "responsibility": "Security"}],
            "uml_class_diagram": "classDiagram\nclass Auth { +login() }",
            "file_structure": ["auth.py"],
            "module_dependencies": {},
        }

    recovered_arch = agent.produce_valid_artifact("Architecture", faulty_architect_producer, state, Architecture)
    recovery_time_ms = int((time.time() - t0) * 1000)

    assert recovered_arch is not None
    assert recovered_arch.components[0]["name"] == "Auth"
    assert call_attempts == 2

    # Check event logging
    with get_session() as session:
        events = session.query(AgentEvent).filter(AgentEvent.run_id == run_id).all()
        event_types = [e.event for e in events]
        assert "artifact_rejected" in event_types
        assert "agent_retry" in event_types


def test_f2_incomplete_user_story_fault_injection(tmp_path):
    """F2: Injects incomplete UserStory (missing role, goal, estimate) and verifies detection and recovery."""
    workspace = str(tmp_path / "ws_f2")
    os.makedirs(workspace, exist_ok=True)
    cp_mgr = CheckpointManager(workspace)
    agent = FaultInjectorAgent(name="architect_f2", llm=FakeLLMProvider(), checkpoint_manager=cp_mgr)

    run_id = "test-f2-incomplete-story"
    state = create_initial_state(run_id=run_id, requirement="inventory system", workspace_path=workspace)

    t0 = time.time()
    call_attempts = 0

    def faulty_story_producer(feedback=None):
        nonlocal call_attempts
        call_attempts += 1
        if call_attempts == 1:
            # F2 Fault: Incomplete UserStory (missing required fields)
            return {"id": "US-INCOMPLETE", "action": "click button"}
        # Recovery on retry
        return {
            "id": "US-RECOVERED",
            "role": "InventoryManager",
            "action": "approve stock replenishment",
            "goal": "maintain optimal inventory levels",
            "acceptance_criteria": ["Stock updated in DB", "Confirmation message displayed"],
            "priority": "high",
            "estimate": 2,
        }

    recovered_story = agent.produce_valid_artifact("UserStory", faulty_story_producer, state, UserStory)
    recovery_time_ms = int((time.time() - t0) * 1000)

    assert recovered_story is not None
    assert recovered_story.id == "US-RECOVERED"
    assert call_attempts == 2
    assert recovery_time_ms >= 0
