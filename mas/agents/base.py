"""Base agent abstraction and valid artifact production loop."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel

from mas.core.llm import LLMProvider
from mas.core.state import MASState
from mas.core.validator import SchemaValidator, ValidationResult
from mas.core.events import event_logger
from mas.core.checkpoints import CheckpointManager


class BaseAgent(ABC):
    """Abstract base class for all MAS agents."""

    def __init__(
        self,
        name: str,
        llm: LLMProvider,
        validator: Optional[SchemaValidator] = None,
        checkpoint_manager: Optional[CheckpointManager] = None,
    ):
        self.name = name
        self.llm = llm
        self.validator = validator or SchemaValidator()
        self.checkpoint_manager = checkpoint_manager

    @abstractmethod
    def run(self, state: MASState) -> MASState:
        """Executes the agent logic and returns updated MASState."""
        pass

    def produce_valid_artifact(
        self,
        artifact_type: str,
        producer_func,
        state: MASState,
        schema_model: Type[BaseModel],
    ) -> BaseModel:
        """Executes producer with invalid artifact policy:

        1. checkpoint workspace
        2. generate
        3. if invalid, retry producer once with error feedback
        4. if still invalid, rollback to checkpoint and rerun producer
        5. if still invalid, fail run
        """
        run_id = state.get("run_id", "unknown")
        cp_ref = None
        if self.checkpoint_manager:
            cp_ref = self.checkpoint_manager.save_checkpoint()

        # Step 1: Initial generation
        candidate = producer_func(feedback=None)
        res = self.validator.validate_artifact(artifact_type, candidate)
        if res.is_valid and res.parsed_artifact:
            return res.parsed_artifact

        # Record validation failure
        err_msg = res.error_summary()
        event_logger.emit(
            run_id=run_id,
            agent=self.name,
            event="artifact_rejected",
            status="failure",
            summary=f"Validation failed for {artifact_type}: {err_msg}",
        )

        # Step 2: Retry producer once with feedback
        retry_candidate = producer_func(feedback=f"Validation error: {err_msg}. Please return valid JSON.")
        res_retry = self.validator.validate_artifact(artifact_type, retry_candidate)
        if res_retry.is_valid and res_retry.parsed_artifact:
            event_logger.emit(
                run_id=run_id,
                agent=self.name,
                event="agent_retry",
                status="success",
                summary=f"Producer retry succeeded for {artifact_type}",
            )
            return res_retry.parsed_artifact

        # Step 3: Rollback to last valid checkpoint and rerun
        if self.checkpoint_manager and cp_ref:
            self.checkpoint_manager.restore_checkpoint(cp_ref)
            event_logger.emit(
                run_id=run_id,
                agent=self.name,
                event="rollback",
                status="success",
                summary=f"Rolled back to checkpoint {cp_ref} after retry failure",
            )

        rerun_candidate = producer_func(feedback=f"Strict compliance required for schema: {schema_model.model_json_schema()}")
        res_rerun = self.validator.validate_artifact(artifact_type, rerun_candidate)
        if res_rerun.is_valid and res_rerun.parsed_artifact:
            return res_rerun.parsed_artifact

        event_logger.emit(
            run_id=run_id,
            agent=self.name,
            event="artifact_rejected",
            status="failure",
            summary=f"Permanent validation failure for {artifact_type} after retry and rollback",
        )
        raise ValueError(f"Producer {self.name} failed to produce valid {artifact_type}: {res_rerun.error_summary()}")
