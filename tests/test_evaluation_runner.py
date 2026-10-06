"""Unit tests for EvaluationRunner and ChatDevAdapter."""

import os
from eval.chatdev_adapter import ChatDevAdapter
from eval.runner import EvaluationRunner
from mas.core.llm import FakeLLMProvider


def test_dry_run_executes_zero_model_calls(capsys):
    runner = EvaluationRunner()
    runner.print_dry_run()

    captured = capsys.readouterr()
    assert "TOTAL CORE EXPERIMENTAL RUNS = 300" in captured.out
    assert "8,400,000" in captured.out
    assert "ENGINEERING PLANNING TOKEN ENVELOPE" in captured.out


def test_chatdev_adapter_fake_mode(tmp_path):
    ws = tmp_path / "ws_chatdev"
    os.makedirs(ws, exist_ok=True)

    adapter = ChatDevAdapter(llm=FakeLLMProvider())
    task = {
        "task_id": "test_cd_01",
        "name": "ChatDev Task Test",
        "description": "Create sample python app",
    }
    out = adapter.run_task(
        task=task,
        output_base_dir=str(ws),
        model="fake",
        use_fake=True,
    )
    assert out["system"] == "chatdev"
    assert out["total_tokens"] > 0
    assert os.path.exists(os.path.join(out["workspace_dir"], "main.py"))
