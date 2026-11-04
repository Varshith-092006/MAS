"""Deterministic offline regression tests for Phase 2AK:
ChatDev subprocess UTF-8 decoding, configurable timeout (900s), partial artifact preservation,
and bounded reflection review cycle logic.
"""

import os
import sys
import subprocess
from unittest.mock import MagicMock, patch
import pytest

# Ensure external/ChatDev is on sys.path for direct component testing
chatdev_dir = os.path.abspath("external/ChatDev")
if chatdev_dir not in sys.path:
    sys.path.insert(0, chatdev_dir)

from eval.chatdev_adapter import ChatDevAdapter
from mas.core.llm import LLMProvider


class RealLLMStub(LLMProvider):
    """Stub representing a non-Fake LLM to trigger live/subprocess dispatch in ChatDevAdapter."""
    def generate(self, prompt, **kwargs):
        raise NotImplementedError("Stub for offline test")


class TestPhase2AKSubprocessAndEncoding:
    """Tests Windows UTF-8 decoding and configurable timeout behavior in ChatDevAdapter."""

    def test_default_timeout_is_900_seconds(self):
        """ChatDevAdapter should default to 900 seconds."""
        adapter = ChatDevAdapter()
        assert adapter.default_timeout == 900

    def test_subprocess_decoding_handles_multibyte_utf8_chars(self, tmp_path):
        """Simulate subprocess stdout/stderr with non-breaking hyphens (\u2011), arrows (\u2192),

        and other multi-byte Unicode chars without raising UnicodeDecodeError.
        """
        adapter = ChatDevAdapter(llm=RealLLMStub())
        task = {
            "task_id": "test_encoding_01",
            "name": "Encoding Test",
            "description": "Solve science \u2011 question \u2192 \u2211 result",
        }

        unicode_stdout = "ChatDev generated code \u2011 with math \u2211 and arrow \u2192"
        mock_completed_proc = subprocess.CompletedProcess(
            args=["python", "run.py"],
            returncode=0,
            stdout=unicode_stdout,
            stderr="",
        )

        warehouse_dir = os.path.abspath("external/ChatDev/WareHouse/Encoding_Test_DefaultOrg_test")
        os.makedirs(warehouse_dir, exist_ok=True)
        with open(os.path.join(warehouse_dir, "main.py"), "w", encoding="utf-8") as f:
            f.write("# main.py \u2011 UTF-8 test\nprint('OK')\n")

        with patch("eval.chatdev_adapter.subprocess.run", return_value=mock_completed_proc) as mock_subproc:
            try:
                out = adapter.run_task(
                    task=task,
                    output_base_dir=str(tmp_path),
                    model="cohere/north-mini-code:free",
                    use_fake=False,
                )

                assert mock_subproc.called
                call_kwargs = mock_subproc.call_args[1]
                assert call_kwargs.get("encoding") == "utf-8"
                assert call_kwargs.get("errors") == "replace"
                assert call_kwargs.get("timeout") == 900

                # Verify environment variables for UTF-8
                env = call_kwargs.get("env", {})
                assert env.get("PYTHONIOENCODING") == "utf-8"
                assert env.get("PYTHONUTF8") == "1"

                assert out["status"] == "COMPLETED"
                assert os.path.exists(os.path.join(out["workspace_dir"], "main.py"))
            finally:
                if os.path.exists(warehouse_dir):
                    import shutil
                    shutil.rmtree(warehouse_dir, ignore_errors=True)

    def test_custom_timeout_override_and_preservation_on_timeout(self, tmp_path):
        """Custom timeout parameter is passed to subprocess.run and partial artifacts are preserved."""
        adapter = ChatDevAdapter(llm=RealLLMStub(), default_timeout=900)
        task = {
            "task_id": "test_timeout_01",
            "name": "Timeout Task",
            "description": "Test timeout behavior",
        }

        # Create simulated partial artifacts in WareHouse
        warehouse_dir = os.path.abspath("external/ChatDev/WareHouse/Timeout_Task_DefaultOrg_test")
        os.makedirs(warehouse_dir, exist_ok=True)
        with open(os.path.join(warehouse_dir, "main.py"), "w", encoding="utf-8") as f:
            f.write("# partial main.py\ndef run(): pass\n")
        with open(os.path.join(warehouse_dir, "solver.py"), "w", encoding="utf-8") as f:
            f.write("# partial solver.py\ndef solve(): pass\n")

        # Mock subprocess.run to raise TimeoutExpired with partial output
        timeout_exc = subprocess.TimeoutExpired(
            cmd=["python", "run.py"],
            timeout=120,
            output="Partial output before timeout \u2011",
            stderr="",
        )

        with patch("eval.chatdev_adapter.subprocess.run", side_effect=timeout_exc) as mock_subproc:
            try:
                out = adapter.run_task(
                    task=task,
                    output_base_dir=str(tmp_path),
                    model="cohere/north-mini-code:free",
                    use_fake=False,
                    timeout=120,
                )

                assert mock_subproc.called
                call_kwargs = mock_subproc.call_args[1]
                assert call_kwargs.get("timeout") == 120

                # Status should accurately report failure with timeout reason
                assert out["status"] == "FAILED"
                assert "timed out after 120 seconds" in out["failed_reason"]

                # Crucial requirement: partial artifacts are preserved in workspace_dir
                ws_main = os.path.join(out["workspace_dir"], "main.py")
                ws_solver = os.path.join(out["workspace_dir"], "solver.py")
                assert os.path.exists(ws_main)
                assert os.path.exists(ws_solver)
                assert out["files_count"] >= 2
            finally:
                if os.path.exists(warehouse_dir):
                    import shutil
                    shutil.rmtree(warehouse_dir, ignore_errors=True)


class TestPhase2AKReflectionLoopEfficiency:
    """Tests the bounded Reviewer-Programmer reflection loop logic in ChatDev."""

    def test_codereview_break_cycle_on_info_finished(self):
        """CodeReview.break_cycle should return True if <INFO> Finished appears in review_comments or modification_conclusion."""
        from chatdev.composed_phase import CodeReview

        cr = CodeReview.__new__(CodeReview)
        cr.review_count = 0
        cr.phase_env = {}

        # Case 1: reviewer signals finished
        env1 = {"review_comments": "<INFO> Finished", "modification_conclusion": ""}
        assert cr.break_cycle(env1) is True

        # Case 2: programmer signals finished
        env2 = {"review_comments": "Please fix line 5", "modification_conclusion": "Done. <INFO> Finished"}
        assert cr.break_cycle(env2) is True

    def test_codereview_break_cycle_on_codes_are_perfect(self):
        """CodeReview.break_cycle should return True if reviewer finds code is satisfactory."""
        from chatdev.composed_phase import CodeReview

        cr = CodeReview.__new__(CodeReview)
        cr.review_count = 0
        cr.phase_env = {}
        env = {
            "review_comments": "The codes are perfect and meet all requirements. No comment.",
            "modification_conclusion": "",
        }
        assert cr.break_cycle(env) is True

    def test_codereview_bounds_iterations_after_one_full_cycle(self):
        """CodeReview.break_cycle should bound cycles after 1 thorough review and modification cycle."""
        from chatdev.composed_phase import CodeReview

        cr = CodeReview.__new__(CodeReview)
        cr.review_count = 0
        cr.phase_env = {}
        env = {
            "review_comments": "Consider adding error handling in solver.py",
            "modification_conclusion": "```python\n# solver.py\ndef solve(): return 42\n```",
        }
        # In cycle 0, modification_conclusion contains code blocks, so review_count increments to 1 and terminates
        assert cr.break_cycle(env) is True

    def test_codereviewcomment_propagates_review_comments_to_phase_env(self):
        """CodeReviewComment should propagate seminar_conclusion into self.phase_env['review_comments']."""
        from chatdev.phase import CodeReviewComment

        crc = CodeReviewComment.__new__(CodeReviewComment)
        crc.phase_env = {}
        crc.seminar_conclusion = "<INFO> Finished"

        mock_chat_env = MagicMock()
        mock_chat_env.env_dict = {}

        crc.update_chat_env(mock_chat_env)
        assert mock_chat_env.env_dict.get("review_comments") == "<INFO> Finished"
        assert crc.phase_env.get("review_comments") == "<INFO> Finished"

    def test_chat_agent_handles_null_content_gracefully(self):
        """ChatAgent should gracefully handle responses where choice message content is None."""
        from camel.agents.chat_agent import ChatAgent
        from camel.messages import ChatMessage
        from camel.typing import RoleType, ModelType

        agent = ChatAgent.__new__(ChatAgent)
        agent.role_name = "programmer"
        agent.role_type = RoleType.CHATDEV_PROGRAMMER
        agent.model_type = ModelType.NORTH_MINI_CODE
        agent.model = ModelType.NORTH_MINI_CODE
        agent.model_backend = MagicMock()
        agent.model_backend.run.return_value = {
            "id": "resp-1",
            "choices": [{"message": {"role": "assistant", "content": None}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 0, "total_tokens": 10},
        }
        agent.orig_sys_message = ChatMessage("programmer", RoleType.CHATDEV_PROGRAMMER, {}, "system", "sys")
        agent.message_window_size = 10
        agent.terminated = False
        agent.info = False
        agent.get_info = MagicMock(return_value={})

        agent.model_token_limit = 4096
        agent.system_message = agent.orig_sys_message

        input_msg = ChatMessage("tester", RoleType.CHATDEV_TESTER, {}, "user", "test")
        with patch.object(ChatAgent, "update_messages", return_value=[input_msg]):
            with patch("camel.agents.chat_agent.num_tokens_from_messages", return_value=5):
                resp = agent.step(input_msg)
                assert len(resp.msgs) == 1
                assert resp.msgs[0].content == ""
