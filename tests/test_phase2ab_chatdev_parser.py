"""Phase 2AB Targeted Offline Regression Suite:
Robust ChatDev code parsing, multi-format extraction, placeholder rejection,
file writing, and error propagation to the adapter/runner.
All tests run strictly offline with zero live model transmissions.
"""

import os
import shutil
import sys
import tempfile
from unittest.mock import MagicMock, patch
import pytest

# Ensure external/ChatDev is on sys.path for direct parser testing
chatdev_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "external", "ChatDev"))
if chatdev_dir not in sys.path:
    sys.path.insert(0, chatdev_dir)

from chatdev.codes import Codes, _is_trivial_placeholder_or_empty
from eval.chatdev_adapter import ChatDevAdapter


# ============================================================================
# SECTION 1: REPRODUCTION & RESOLUTION OF PREVIOUS PARSER FAILURES
# ============================================================================

def test_code_block_at_start_of_response():
    """Reproduces old parser failure where response starts immediately with ```python.
    Old regex `(.+?)\n```...` failed because no characters preceded the fence.
    """
    content = (
        "```python\n"
        "def solve(question: str) -> str:\n"
        "    return f'Solved: {question}'\n\n"
        "if __name__ == '__main__':\n"
        "    print(solve('What is kinetic energy?'))\n"
        "```\n"
    )
    codes = Codes(content)
    assert "main.py" in codes.codebooks
    assert "def solve(" in codes.codebooks["main.py"]


def test_windows_crlf_normalization():
    """Reproduces old parser failure with Windows CRLF newlines."""
    content = (
        "main.py\r\n"
        "```python\r\n"
        "def main():\r\n"
        "    print('Running on CRLF')\r\n"
        "if __name__ == '__main__':\r\n"
        "    main()\r\n"
        "```\r\n"
    )
    codes = Codes(content)
    assert "main.py" in codes.codebooks
    assert "\r" not in codes.codebooks["main.py"]
    assert "Running on CRLF" in codes.codebooks["main.py"]


def test_code_containing_uppercase_substring_code():
    """Reproduces critical bug where 'CODE' in code discarded valid files (e.g. STATUS_CODE)."""
    content = (
        "### main.py\n"
        "```python\n"
        "STATUS_CODE_SUCCESS = 200\n"
        "ERROR_CODE_INVALID = 400\n"
        "ZIP_CODE = '90210'\n\n"
        "def evaluate_response(status_code: int) -> bool:\n"
        "    return status_code == STATUS_CODE_SUCCESS\n\n"
        "if __name__ == '__main__':\n"
        "    print(evaluate_response(200))\n"
        "```\n"
    )
    codes = Codes(content)
    assert "main.py" in codes.codebooks
    assert "STATUS_CODE_SUCCESS = 200" in codes.codebooks["main.py"]


def test_preceding_text_with_version_numbers():
    """Reproduces old regex matching candidate '3.11' instead of filename."""
    content = (
        "We develop this using Python 3.11 with numpy 1.24.\n"
        "### solver.py\n"
        "```python\n"
        "def solve():\n"
        "    return 42\n"
        "```\n"
    )
    codes = Codes(content)
    assert "3.11" not in codes.codebooks
    assert "1.24" not in codes.codebooks
    assert "solver.py" in codes.codebooks


# ============================================================================
# SECTION 2: MULTI-FORMAT FILENAME & CODE EXTRACTION
# ============================================================================

def test_markdown_heading_filename():
    """Detects filename in markdown heading (### main.py)."""
    content = (
        "Here is the code:\n\n"
        "### main.py\n"
        "```python\n"
        "class ScienceApp:\n"
        "    def run(self):\n"
        "        pass\n\n"
        "if __name__ == '__main__':\n"
        "    ScienceApp().run()\n"
        "```\n"
    )
    codes = Codes(content)
    assert "main.py" in codes.codebooks


def test_bold_filename_line():
    """Detects filename in bold markdown line (**main.py** or **File: main.py**)."""
    content = (
        "**File: main.py**\n"
        "```python\n"
        "def main():\n"
        "    return 'success'\n"
        "```\n"
    )
    codes = Codes(content)
    assert "main.py" in codes.codebooks


def test_fence_info_filename():
    """Detects filename in code fence tag (```python:main.py or ```python filename=main.py)."""
    content = (
        "```python:main.py\n"
        "def solve():\n"
        "    return 'step by step'\n"
        "if __name__ == '__main__':\n"
        "    print(solve())\n"
        "```\n"
    )
    codes = Codes(content)
    assert "main.py" in codes.codebooks


def test_comment_header_filename():
    """Detects filename from top line comments (# filename: main.py)."""
    content = (
        "```python\n"
        "# filename: main.py\n"
        "def main():\n"
        "    print('hello')\n"
        "main()\n"
        "```\n"
    )
    codes = Codes(content)
    assert "main.py" in codes.codebooks


def test_multi_file_project_extraction():
    """Extracts multiple distinct source files from a single response."""
    content = (
        "### solver.py\n"
        "```python\n"
        "class ScienceSolver:\n"
        "    def solve(self, q):\n"
        "        return f'Answer to {q}'\n"
        "```\n\n"
        "### main.py\n"
        "```python\n"
        "from solver import ScienceSolver\n"
        "if __name__ == '__main__':\n"
        "    s = ScienceSolver()\n"
        "    print(s.solve('speed of light'))\n"
        "```\n"
    )
    codes = Codes(content)
    assert len(codes.codebooks) == 2
    assert "solver.py" in codes.codebooks
    assert "main.py" in codes.codebooks
    assert "ScienceSolver" in codes.codebooks["solver.py"]
    assert "from solver import ScienceSolver" in codes.codebooks["main.py"]


# ============================================================================
# SECTION 3: PLACEHOLDER REJECTION & MALFORMED / TRUNCATED INPUTS
# ============================================================================

def test_reject_literal_prompt_template_placeholder():
    """Rejects literal prompt placeholder without implementation."""
    content = (
        "main.py\n"
        "```python\n"
        "'''\n"
        "DOCSTRING\n"
        "'''\n"
        "CODE\n"
        "```\n"
    )
    codes = Codes(content)
    assert len(codes.codebooks) == 0


def test_reject_trivial_pass_only_stub():
    """Rejects source file containing only docstrings and pass."""
    content = (
        "main.py\n"
        "```python\n"
        "'''Step-by-step solver main file.'''\n"
        "pass\n"
        "```\n"
    )
    codes = Codes(content)
    assert len(codes.codebooks) == 0


def test_reject_empty_and_whitespace_responses():
    """Empty and whitespace responses produce empty codebooks."""
    assert len(Codes("").codebooks) == 0
    assert len(Codes("   \n\n\t  ").codebooks) == 0


def test_reject_prose_only_response():
    """Prose-only responses without code blocks produce empty codebooks."""
    content = (
        "I have analyzed the customer's request. We should create a modular solver "
        "using python's sympy and pint libraries. The main application will have a CLI."
    )
    codes = Codes(content)
    assert len(codes.codebooks) == 0


def test_reject_json_config_only_response():
    """JSON configuration without executable implementation is rejected."""
    content = (
        "```json\n"
        "{\n"
        "  \"task\": \"srdd_educ_01\",\n"
        "  \"status\": \"configured\",\n"
        "  \"files\": [\"main.py\"]\n"
        "}\n"
        "```\n"
    )
    codes = Codes(content)
    # No .py files or executable python code
    assert "main.py" not in codes.codebooks


def test_handle_truncated_response_gracefully():
    """Handles response truncated before closing fence without throwing unhandled exceptions."""
    content = (
        "### main.py\n"
        "```python\n"
        "def solve(question: str) -> str:\n"
        "    steps = ['Step 1', 'Step 2']\n"
        "    return '\\n'.join(steps)\n\n"
        "if __name__ == '__main__':\n"
        "    print(solve('physics'))\n"
        "# Truncated here before closing backticks"
    )
    codes = Codes(content)
    assert "main.py" in codes.codebooks
    assert "def solve(" in codes.codebooks["main.py"]


# ============================================================================
# SECTION 4: SOURCE FILE WRITING & ADAPTER / RUNNER INTEGRATION
# ============================================================================

def test_rewrite_codes_writes_valid_files_to_disk():
    """Codes._rewrite_codes correctly writes parsed files to disk."""
    content = (
        "### main.py\n"
        "```python\n"
        "def main():\n"
        "    print('hello world')\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
        "```\n"
    )
    codes = Codes(content)
    tmpdir = tempfile.mkdtemp(prefix="chatdev_rewrite_test_")
    try:
        codes.directory = tmpdir
        codes._rewrite_codes(git_management=False)
        target_file = os.path.join(tmpdir, "main.py")
        assert os.path.exists(target_file)
        with open(target_file, "r", encoding="utf-8") as f:
            written = f.read()
        assert "def main():" in written
        assert "hello world" in written
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_adapter_marks_failed_on_parser_error():
    """When ChatDev exits with code 1 due to ValueError: No Valid Codes, adapter reports FAILED."""
    adapter = ChatDevAdapter(llm=MagicMock())
    task = {"task_id": "srdd_educ_01", "name": "Science Solver", "description": "Solve science questions"}
    workspace = tempfile.mkdtemp(prefix="adapter_test_ws_")

    try:
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = (
            "Traceback (most recent call last):\n"
            "  File 'run.py', line 125, in <module>\n"
            "    chat_chain.execute_chain()\n"
            "ValueError: No Valid Codes: model response did not contain parsable code blocks."
        )

        with patch("subprocess.run", return_value=mock_proc):
            res = adapter.run_task(
                task=task,
                output_base_dir=workspace,
                model="cohere/north-mini-code:free",
                run_id="test_cd_parser_error_propagation",
                use_fake=False,
            )

        assert res["status"] == "FAILED"
        assert "ChatDev exited with code 1" in res["failed_reason"]
        assert "No Valid Codes" in res["failed_reason"]
        # main.py must NOT be fabricated
        assert not os.path.exists(os.path.join(workspace, "main.py"))
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_zero_network_transmissions_in_parser_tests():
    """Guarantees parser logic performs purely local computation with zero HTTP calls."""
    with patch("mas.core.governor.GovernedHTTPClient") as mock_gov:
        with patch("httpx.Client.post") as mock_post:
            # Parse a rich response
            Codes("main.py\n```python\nimport os\nprint('offline')\n```\n")
            # Neither governor nor httpx should ever be called
            mock_gov.assert_not_called()
            mock_post.assert_not_called()
