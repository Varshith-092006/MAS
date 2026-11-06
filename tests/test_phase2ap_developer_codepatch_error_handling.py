"""Regression tests for Phase 2AP: Developer CodePatch extraction and JSON strictness handling."""

import ast
import json
import pytest

from mas.core.llm import extract_json, ModelResult
from mas.core.schemas import CodePatch
from mas.core.validator import SchemaValidator
from mas.agents.developer import DeveloperAgent


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append(messages)
        text = self.responses.pop(0) if self.responses else ""
        parsed = extract_json(text)
        return ModelResult(
            text=text,
            model_name="fake",
            requested_model="fake",
            provider_model_version="fake",
            input_tokens=100,
            output_tokens=len(text) // 4,
            total_tokens=100 + len(text) // 4,
            latency_ms=10,
            request_id="test_req",
            estimated_cost=0.0,
            raw_metadata={"usage": {"prompt_tokens": 100, "completion_tokens": len(text) // 4}},
            parsed_json=parsed,
            execution_mode="OFFLINE",
            token_provenance="TEST",
        )


def test_extract_json_with_literal_newlines_in_code():
    """Verify that JSON containing literal newlines in string properties parses correctly."""
    raw_payload = """```json
{
  "files": ["main.py"],
  "file_contents": {
    "main.py": "import sys

def solve(query):
    return 'solution'

def main():
    return 0
"
  },
  "summary": "Implementation with newlines",
  "tests_expected": ["test_run"]
}
```"""
    extracted = extract_json(raw_payload)
    assert extracted is not None
    assert extracted["files"] == ["main.py"]
    assert "def solve" in extracted["file_contents"]["main.py"]


def test_developer_extracts_from_conversational_wrapped_json(tmp_path):
    """Verify DeveloperAgent extracts valid CodePatch when wrapped in conversational preamble."""
    llm_output = """We need to produce a CodePatch JSON with files main.py and test_main.py.

```json
{
  "files": ["main.py", "test_main.py"],
  "file_contents": {
    "main.py": "import sys\n\ndef main():\n    return 0\n",
    "test_main.py": "def test_ok():\n    assert True\n"
  },
  "summary": "Step-by-step solver",
  "tests_expected": ["test_ok"]
}
```
Summary complete."""
    llm = FakeLLM([llm_output])
    dev = DeveloperAgent(llm=llm)

    state = {
        "run_id": "test_run",
        "requirement": "Build a science solver",
        "workspace_path": str(tmp_path),
        "iteration": 1,
        "artifacts": {},
    }
    new_state = dev.run(state)
    assert "CodePatch" in new_state["artifacts"]
    assert "main.py" in new_state["changed_files"]
    assert (tmp_path / "main.py").exists()


def test_developer_fallback_multi_file_markdown(tmp_path):
    """Verify DeveloperAgent extracts multiple files from markdown code blocks."""
    llm_output = """Here are the implementations:

### main.py
```python
import sys

def solve(q):
    return f"Explanation for {q}"

def main():
    print("Solver ready")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### test_main.py
```python
from main import solve

def test_solve():
    assert "gravity" in solve("gravity")
```
"""
    llm = FakeLLM([llm_output])
    dev = DeveloperAgent(llm=llm)

    state = {
        "run_id": "test_run_fallback",
        "requirement": "Build a science solver",
        "workspace_path": str(tmp_path),
        "iteration": 1,
        "artifacts": {},
    }
    new_state = dev.run(state)
    assert "CodePatch" in new_state["artifacts"]
    assert "main.py" in new_state["changed_files"]
    assert "test_main.py" in new_state["changed_files"]
    assert (tmp_path / "main.py").exists()
    assert (tmp_path / "test_main.py").exists()


def test_developer_fallback_unclosed_single_code_block(tmp_path):
    """Verify DeveloperAgent extracts main.py from unclosed markdown code block."""
    llm_output = """Here is the complete main.py code:
```python
import sys

def solve(q):
    return "result"

def main():
    return 0
"""
    llm = FakeLLM([llm_output])
    dev = DeveloperAgent(llm=llm)

    state = {
        "run_id": "test_run_unclosed",
        "requirement": "Build a science solver",
        "workspace_path": str(tmp_path),
        "iteration": 1,
        "artifacts": {},
    }
    new_state = dev.run(state)
    assert "CodePatch" in new_state["artifacts"]
    assert "main.py" in new_state["changed_files"]
    assert (tmp_path / "main.py").exists()


def test_developer_error_payload_does_not_echo_raw_text():
    """Verify DeveloperAgent failure returns clean error message without raw LLM dump."""
    llm = FakeLLM(["Completely non-code conversational output with no python syntax."])
    dev = DeveloperAgent(llm=llm)

    state = {
        "run_id": "test_run_fail",
        "requirement": "Build a science solver",
        "workspace_path": "./dummy",
        "iteration": 1,
        "artifacts": {},
    }
    with pytest.raises(ValueError) as excinfo:
        dev.run(state)
    err = str(excinfo.value)
    assert "Producer developer failed to produce valid CodePatch" in err
    assert "Completely non-code" not in err

