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
                    "content": (
                        "You are ManagerAgent. Clean and normalize the software requirement into a structured TaskPlan.\n"
                        "Mandatory responsibilities:\n"
                        "1. Translate task description into explicit requirements and objectively testable acceptance criteria.\n"
                        "2. Identify ambiguities or missing constraints explicitly in 'ambiguities' rather than inventing unstated requirements.\n"
                        "3. Specify all required source files (must include main.py or app.py as the primary entry point).\n"
                        "4. For command-line tools or solvers, explicitly include acceptance criteria requiring '--help' and zero-argument runs to exit cleanly with exit code 0.\n"
                        "5. Return a valid TaskPlan JSON with keys: id, task_id, name, description, complexity, files, sprint_goals, acceptance_criteria, ambiguities."
                    ),
                },
                {"role": "user", "content": f"Requirement: {raw_req}\nDetermined Complexity: {label} (Score: {score})\nFeedback: {feedback or 'None'}"},
            ]
            target_model = state.get("model") or getattr(self.llm, "default_model", None)
            result = self.llm.generate(
                messages=messages,
                model=target_model,
                response_schema=TaskPlan,
                run_id=run_id,
                agent_name="manager",
                max_tokens=1500,
            )
            data = result.parsed_json
            if not data and result.text:
                from mas.core.llm import extract_json
                data = extract_json(result.text)

            if data and isinstance(data, dict):
                data = dict(data)
                data["complexity"] = label
                if not data.get("id"):
                    data["id"] = f"plan-{uuid.uuid4().hex[:8]}"
                if not data.get("task_id"):
                    data["task_id"] = state.get("task_id", "custom")
                if not data.get("name"):
                    data["name"] = raw_req[:40].strip()
                if not data.get("description"):
                    data["description"] = raw_req.strip()
                if not data.get("acceptance_criteria"):
                    data["acceptance_criteria"] = [
                        f"Execute functionality matching: {raw_req[:60].strip()}",
                        "Main entry point runs standalone and terminates cleanly with exit code 0",
                    ]
                if "ambiguities" not in data:
                    data["ambiguities"] = []
                return data

            # Return error payload to trigger produce_valid_artifact retry mechanism
            return {
                "error": f"Manager LLM output could not be parsed as TaskPlan JSON: {result.text[:200]}"
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
