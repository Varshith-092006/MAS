"""Manager Agent: Normalizes requirements and invokes ComplexityRouter."""

from typing import Dict, Optional
import uuid

from mas.agents.base import BaseAgent
from mas.agents.router import ComplexityRouter
from mas.core.schemas import TaskPlan
from mas.core.state import MASState
from mas.core.events import event_logger


class ManagerAgent(BaseAgent):
    """Initializes the task, coordinates complexity routing, and emits TaskPlan."""

    def __init__(self, llm, router: Optional[ComplexityRouter] = None, **kwargs):
        super().__init__(name="manager", llm=llm, **kwargs)
        self.router = router or ComplexityRouter(threshold=4)

    def run(self, state: MASState) -> MASState:
        run_id = state.get("run_id", str(uuid.uuid4()))
        raw_req = state.get("requirement", "")

        event_logger.emit(
            run_id=run_id,
            agent="manager",
            event="agent_started",
            summary=f"Normalizing requirement and determining complexity for run {run_id}",
        )

        # Zero LLM call deterministic routing
        label, score, features = self.router.route(raw_req)

        state["complexity"] = label
        state["complexity_score"] = score
        state["router_features"] = features

        def produce_plan(feedback=None):
            # Manager normalizes requirement into TaskPlan
            # For deterministic / fake LLM, produce plan directly or call llm
            messages = [
                {
                    "role": "system",
                    "content": "You are ManagerAgent. Clean and normalize the software requirement into a structured TaskPlan.",
                },
                {"role": "user", "content": f"Requirement: {raw_req}\nComplexity: {label}\nFeedback: {feedback or 'None'}"},
            ]
            result = self.llm.generate(
                messages=messages,
                response_schema=TaskPlan,
                run_id=run_id,
                agent_name="manager",
            )
            if result.parsed_json:
                data = dict(result.parsed_json)
                data["complexity"] = label
                data["description"] = raw_req.strip()
                return data
            return {
                "id": f"TP-{run_id[:8]}",
                "task_id": state.get("task_id", "task-custom"),
                "name": raw_req[:40].strip() or "Generated Application",
                "description": raw_req.strip(),
                "complexity": label,
                "files": ["main.py"],
                "sprint_goals": ["Initial implementation", "Verify core logic"],
            }

        plan: TaskPlan = self.produce_valid_artifact("TaskPlan", produce_plan, state, TaskPlan)

        state["artifacts"]["TaskPlan"] = plan.model_dump()

        event_logger.emit(
            run_id=run_id,
            agent="manager",
            event="agent_completed",
            summary=f"Manager normalized requirement. Route: {label} (Score: {score})",
        )

        return state
