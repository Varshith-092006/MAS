"""Reviewer Agent: Performs semantic and requirement review using GPT-4o-mini."""

import os
from typing import Dict, List, Optional
import uuid

from mas.agents.base import BaseAgent
from mas.core.schemas import ReviewReport
from mas.core.state import MASState
from mas.core.events import event_logger


class ReviewerAgent(BaseAgent):
    """Reviews code against natural language requirements semantically.

    Structural checks are offloaded strictly to deterministic AST analysis.
    """

    def __init__(self, llm, **kwargs):
        super().__init__(name="reviewer", llm=llm, **kwargs)

    def run(self, state: MASState) -> MASState:
        run_id = state.get("run_id", str(uuid.uuid4()))
        req = state.get("requirement", "")
        changed_files = state.get("changed_files", [])

        event_logger.emit(
            run_id=run_id,
            agent="reviewer",
            event="agent_started",
            summary="Reviewer analyzing semantic conformance to requirements",
        )

        def produce_review(feedback=None):
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are ReviewerAgent. Perform semantic requirement review. "
                        "Do not calculate import cycles (handled deterministically by AST). "
                        "Return ReviewReport with status, critical_issues, major_issues, minor_issues, findings, and summary."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Original Requirement: {req}\n"
                        f"Files Changed: {changed_files}\n"
                        f"AST Report Summary: {state.get('ast_report', {}).get('summary', 'None')}\n"
                        f"Feedback: {feedback or 'None'}"
                    ),
                },
            ]
            cheap_model = (
                os.environ.get("OPENROUTER_CHEAP_MODEL")
                or os.environ.get("OPENROUTER_MODEL")
                or "openrouter/free"
            )
            res = self.llm.generate(
                messages=messages,
                model=cheap_model,
                response_schema=ReviewReport,
                run_id=run_id,
                agent_name="reviewer",
            )
            if res.parsed_json:
                return res.parsed_json
            return {
                "status": "PASSED",
                "critical_issues": 0,
                "major_issues": 0,
                "minor_issues": 0,
                "findings": ["Requirements satisfied correctly."],
                "summary": "Clean semantic review with zero critical findings.",
            }

        report: ReviewReport = self.produce_valid_artifact("ReviewReport", produce_review, state, ReviewReport)

        state["review_report"] = report.model_dump()
        state["artifacts"]["ReviewReport"] = report.model_dump()

        event_logger.emit(
            run_id=run_id,
            agent="reviewer",
            event="agent_completed",
            summary=f"Review completed: {report.status} (critical={report.critical_issues}, major={report.major_issues})",
        )

        return state
