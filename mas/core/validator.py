"""Runtime schema validation for inter-agent artifacts."""

from typing import Any, Dict, List, Optional, Tuple, Type
from pydantic import BaseModel, ValidationError

from mas.core.schemas import ARTIFACT_CLASSES


class ValidationResult:
    def __init__(self, is_valid: bool, errors: Optional[List[str]] = None, parsed_artifact: Optional[BaseModel] = None):
        self.is_valid = is_valid
        self.errors = errors or []
        self.parsed_artifact = parsed_artifact

    def __bool__(self) -> bool:
        return self.is_valid

    def error_summary(self) -> str:
        return "; ".join(self.errors)


class SchemaValidator:
    """Validates data against canonical Pydantic models."""

    @staticmethod
    def validate_artifact(artifact_type: str, data: Any) -> ValidationResult:
        if artifact_type not in ARTIFACT_CLASSES:
            return ValidationResult(
                is_valid=False,
                errors=[f"Unknown artifact type: {artifact_type}"],
            )

        model_cls: Type[BaseModel] = ARTIFACT_CLASSES[artifact_type]

        if isinstance(data, model_cls):
            return ValidationResult(is_valid=True, parsed_artifact=data)

        if not isinstance(data, dict):
            return ValidationResult(
                is_valid=False,
                errors=[f"Expected dictionary payload for {artifact_type}, got {type(data).__name__}"],
            )

        # Handle explicit producer error and exception payloads to prevent masking parsing failures
        if "error" in data and len(data) == 1:
            return ValidationResult(is_valid=False, errors=[str(data["error"])])
        if "__producer_exception__" in data:
            return ValidationResult(is_valid=False, errors=[str(data["__producer_exception__"])])

        try:
            parsed = model_cls.model_validate(data)
            return ValidationResult(is_valid=True, parsed_artifact=parsed)
        except ValidationError as e:
            errors = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
            return ValidationResult(is_valid=False, errors=errors)
        except Exception as e:
            return ValidationResult(is_valid=False, errors=[str(e)])
