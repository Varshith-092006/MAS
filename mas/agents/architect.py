"""Architect Agent: Produces Architecture and UserStory artifacts for STRUCTURED tasks."""

from typing import Dict, List, Optional
import uuid

from mas.agents.base import BaseAgent
from mas.core.schemas import Architecture, UserStory
from mas.core.state import MASState
from mas.core.events import event_logger


class ArchitectAgent(BaseAgent):
    """Generates UML design, module dependencies, and sprint user stories."""

    def __init__(self, llm, **kwargs):
        super().__init__(name="architect", llm=llm, **kwargs)

    def slice_uml(self, architecture: Dict, files: List[str]) -> List[str]:
        """Extracts relevant UML slices for specified files."""
        if not architecture:
            return []
        uml_text = architecture.get("uml_class_diagram", "")
        # Return lines referencing the target files/classes
        slices = []
        for line in uml_text.splitlines():
            for f in files:
                mod_name = f.replace(".py", "")
                if mod_name.lower() in line.lower():
                    slices.append(line)
        return slices if slices else uml_text.splitlines()[:10]

    def run(self, state: MASState) -> MASState:
        run_id = state.get("run_id", str(uuid.uuid4()))
        plan_data = state.get("artifacts", {}).get("TaskPlan", {})

        event_logger.emit(
            run_id=run_id,
            agent="architect",
            event="agent_started",
            summary="Designing minimal architecture and user stories for STRUCTURED task",
        )

        # 1. Produce Architecture artifact
        def produce_arch(feedback=None):
            messages = [
                {
                    "role": "system",
                    "content": "You are ArchitectAgent. Produce clean modular Architecture with UML class diagram and module dependencies.",
                },
                {
                    "role": "user",
                    "content": f"Task: {plan_data.get('description', '')}\nFeedback: {feedback or 'None'}",
                },
            ]
            res = self.llm.generate(
                messages=messages,
                response_schema=Architecture,
                run_id=run_id,
                agent_name="architect",
            )
            if res.parsed_json:
                return res.parsed_json
            return {
                "components": [
                    {"name": "CoreService", "responsibility": "Business logic and operations"},
                    {"name": "DataStore", "responsibility": "Persistence and retrieval"},
                ],
                "uml_class_diagram": "classDiagram\nclass CoreService { +execute() }\nclass DataStore { +save() }",
                "file_structure": ["service.py", "datastore.py", "models.py"],
                "module_dependencies": {"service": ["datastore", "models"], "datastore": ["models"]},
            }

        arch: Architecture = self.produce_valid_artifact("Architecture", produce_arch, state, Architecture)
        state["architecture"] = arch.model_dump()
        state["artifacts"]["Architecture"] = arch.model_dump()

        # 2. Produce UserStory artifact
        def produce_story(feedback=None):
            messages = [
                {
                    "role": "system",
                    "content": "You are ArchitectAgent. Produce a prioritized UserStory with clear acceptance criteria.",
                },
                {
                    "role": "user",
                    "content": f"Task: {plan_data.get('description', '')}\nFeedback: {feedback or 'None'}",
                },
            ]
            res = self.llm.generate(
                messages=messages,
                response_schema=UserStory,
                run_id=run_id,
                agent_name="architect",
            )
            if res.parsed_json:
                return res.parsed_json
            return {
                "id": "US-1",
                "role": "User",
                "action": "execute core operations",
                "goal": "achieve requested functional outcome",
                "acceptance_criteria": ["System executes without errors", "Functions return correct values"],
                "priority": "high",
                "estimate": 3,
            }

        story: UserStory = self.produce_valid_artifact("UserStory", produce_story, state, UserStory)
        state["artifacts"]["UserStory"] = story.model_dump()

        event_logger.emit(
            run_id=run_id,
            agent="architect",
            event="agent_completed",
            summary=f"Architecture and UserStory generated ({len(arch.file_structure)} files planned)",
        )

        return state
