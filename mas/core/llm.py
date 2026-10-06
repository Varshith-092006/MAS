"""LLM Provider abstraction, ModelResult, and Token Logger."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import json
import time
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel
from mas.db.models import ModelCall
from mas.db.session import get_session

# Pricing per million tokens (USD)
PRICING_CATALOG = {
    "gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
    "gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
    "fake": {"input": 0.0, "output": 0.0},
}


@dataclass
class ModelResult:
    text: str
    model_name: str
    provider_model_version: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: int
    request_id: str
    estimated_cost: float
    parsed_json: Optional[Dict[str, Any]] = None


class TokenCapExceededError(Exception):
    """Raised when a run exceeds its allocated provider token limit."""
    pass


class TokenLogger:
    """Tracks provider token usage per run and enforces the 60,000 cap."""

    def __init__(self, max_tokens_per_run: int = 60000):
        self.max_tokens_per_run = max_tokens_per_run
        self._run_totals: Dict[str, Dict[str, Any]] = {}

    def get_run_totals(self, run_id: str) -> Dict[str, Any]:
        return self._run_totals.get(run_id, {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost": 0.0,
            "call_count": 0,
        })

    def record_call(self, run_id: str, agent: str, result: ModelResult, db_session=None):
        if run_id not in self._run_totals:
            self._run_totals[run_id] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "estimated_cost": 0.0,
                "call_count": 0,
            }

        totals = self._run_totals[run_id]
        totals["input_tokens"] += result.input_tokens
        totals["output_tokens"] += result.output_tokens
        totals["total_tokens"] += result.total_tokens
        totals["estimated_cost"] += result.estimated_cost
        totals["call_count"] += 1

        # Persist to database
        own_session = False
        if db_session is None:
            db_session = get_session()
            own_session = True

        try:
            call_obj = ModelCall(
                run_id=run_id,
                agent=agent,
                model=result.model_name,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
                latency_ms=result.latency_ms,
                cost=result.estimated_cost,
            )
            db_session.add(call_obj)
            db_session.commit()
        except Exception:
            db_session.rollback()
        finally:
            if own_session:
                db_session.close()

        # Check token cap
        if totals["total_tokens"] > self.max_tokens_per_run:
            raise TokenCapExceededError(
                f"Run {run_id} exceeded token cap: {totals['total_tokens']} > {self.max_tokens_per_run}"
            )


token_logger = TokenLogger()


class LLMProvider(ABC):
    """Abstract interface for model invocation."""

    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4o",
        response_schema: Optional[type[BaseModel]] = None,
        temperature: float = 0.0,
        run_id: Optional[str] = None,
        agent_name: str = "agent",
    ) -> ModelResult:
        pass


class FakeLLMProvider(LLMProvider):
    """Deterministic fake provider for development, tests, and CP1 validation."""

    def __init__(self):
        self.call_count = 0

    def generate(
        self,
        messages: List[Dict[str, str]],
        model: str = "fake",
        response_schema: Optional[type[BaseModel]] = None,
        temperature: float = 0.0,
        run_id: Optional[str] = None,
        agent_name: str = "agent",
    ) -> ModelResult:
        self.call_count += 1
        t0 = time.time()

        # Deterministic generation based on agent_name or prompt
        parsed: Dict[str, Any] = {}
        text = ""

        if agent_name == "manager":
            parsed = {
                "id": "TP-001",
                "task_id": "task-fake",
                "name": "Deterministic Task Implementation",
                "description": "Implement simple math library",
                "complexity": "SIMPLE",
                "files": ["calculator.py", "test_calculator.py"],
                "sprint_goals": ["Create add and multiply operations", "Verify smoke tests"],
            }
            text = json.dumps(parsed)

        elif response_schema and response_schema.__name__ == "UserStory":
            parsed = {
                "id": "US-001",
                "role": "User",
                "action": "execute core operations",
                "goal": "achieve requested functional outcome",
                "acceptance_criteria": ["System executes without errors", "Functions return correct values"],
                "priority": "high",
                "estimate": 3,
            }
            text = json.dumps(parsed)

        elif agent_name == "architect" or (response_schema and response_schema.__name__ == "Architecture"):
            parsed = {
                "components": [
                    {"name": "AppEngine", "responsibility": "Core application orchestration"},
                    {"name": "Storage", "responsibility": "Data persistence layer"},
                ],
                "uml_class_diagram": "classDiagram\nclass AppEngine { +run() }\nclass Storage { +save() }",
                "file_structure": ["app.py", "storage.py", "utils.py"],
                "module_dependencies": {"app": ["storage", "utils"], "storage": ["utils"]},
            }
            text = json.dumps(parsed)

        elif agent_name == "developer":
            # Return valid code patch
            parsed = {
                "files": ["calculator.py"],
                "file_contents": {
                    "calculator.py": (
                        "def add(a: int, b: int) -> int:\n"
                        "    '''Adds two numbers.'''\n"
                        "    return a + b\n\n"
                        "def multiply(a: int, b: int) -> int:\n"
                        "    '''Multiplies two numbers.'''\n"
                        "    return a * b\n"
                    )
                },
                "summary": "Implemented add and multiply arithmetic functions",
                "tests_expected": ["test_add", "test_multiply"],
            }
            text = json.dumps(parsed)

        elif agent_name == "reviewer":
            parsed = {
                "status": "PASSED",
                "critical_issues": 0,
                "major_issues": 0,
                "minor_issues": 0,
                "findings": ["Code is clean and conforms to specification."],
                "summary": "All arithmetic functions implemented without defects.",
            }
            text = json.dumps(parsed)

        elif agent_name == "reflection":
            parsed = {
                "decision": "STOP",
                "reason": "clean_result: no critical defects and internal checks pass",
                "adaptive_score": 0.95,
                "marginal_gain": 0.95,
                "iteration": 1,
            }
            text = json.dumps(parsed)

        elif agent_name == "tester":
            parsed = {
                "total_tests": 2,
                "passed_tests": 2,
                "failed_tests": 0,
                "pass_rate": 1.0,
                "coverage": 100.0,
                "details": ["test_add PASSED", "test_multiply PASSED"],
            }
            text = json.dumps(parsed)

        else:
            text = "Deterministic response"
            parsed = {"status": "ok"}

        latency = int((time.time() - t0) * 1000)
        req_id = f"fake-req-{self.call_count:04d}"

        # Deterministic token counts
        in_tokens = 120 + len(messages) * 15
        out_tokens = 80 + len(text) // 4
        tot_tokens = in_tokens + out_tokens

        res = ModelResult(
            text=text,
            model_name=model,
            provider_model_version="fake-v1.0",
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            total_tokens=tot_tokens,
            latency_ms=max(latency, 5),
            request_id=req_id,
            estimated_cost=0.0,
            parsed_json=parsed,
        )

        if run_id:
            token_logger.record_call(run_id=run_id, agent=agent_name, result=res)

        return res


class OpenAIProvider(LLMProvider):
    """OpenAI API provider routing through the local logging proxy."""

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        import os
        self.base_url = base_url or os.environ.get("PROXY_BASE_URL", "http://127.0.0.1:8089/v1")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "dummy-key")

    def generate(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4o",
        response_schema: Optional[type[BaseModel]] = None,
        temperature: float = 0.0,
        run_id: Optional[str] = None,
        agent_name: str = "agent",
    ) -> ModelResult:
        import httpx

        t0 = time.time()
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "seed": 42,
        }

        if response_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_schema.__name__,
                    "schema": response_schema.model_json_schema(),
                    "strict": True,
                },
            }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        latency = int((time.time() - t0) * 1000)
        choice = data["choices"][0]
        content = choice["message"]["content"]
        usage = data.get("usage", {})

        in_tok = usage.get("prompt_tokens", 0)
        out_tok = usage.get("completion_tokens", 0)
        tot_tok = usage.get("total_tokens", in_tok + out_tok)
        model_name = data.get("model", model)
        req_id = data.get("id", str(uuid.uuid4()))

        # Pricing calculation
        price = PRICING_CATALOG.get(model, {"input": 0.0, "output": 0.0})
        cost = (in_tok * price["input"]) + (out_tok * price["output"])

        parsed_json = None
        if response_schema:
            try:
                parsed_json = json.loads(content)
            except Exception:
                pass

        result = ModelResult(
            text=content,
            model_name=model_name,
            provider_model_version=data.get("system_fingerprint", model_name),
            input_tokens=in_tok,
            output_tokens=out_tok,
            total_tokens=tot_tok,
            latency_ms=latency,
            request_id=req_id,
            estimated_cost=round(cost, 6),
            parsed_json=parsed_json,
        )

        if run_id:
            token_logger.record_call(run_id=run_id, agent=agent_name, result=result)

        return result
