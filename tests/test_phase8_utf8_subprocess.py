"""DEC-048: subprocess output is decoded as UTF-8, not the Windows cp1252 codepage.

Generated programs print emoji (UTF-8 bytes such as 0x8d / 0x8f that cp1252 cannot decode).
Before the fix the reader thread crashed, stdout/stderr came back empty, and the smoke
protocol's "usage:" fallback could not see the usage message.
"""

import os
import re

from mas.analysis.sandbox import SandboxRunner

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_smoke_run_captures_emoji_output(tmp_path):
    (tmp_path / "main.py").write_text(
        "print('Cooking time \\U0001F373 travel \\U0001F30F done')\n", encoding="utf-8"
    )
    res = SandboxRunner().smoke_run(str(tmp_path), entry_point="main.py", allow_fallback=True)
    assert res.is_success
    assert "done" in (res.stdout or "")


def test_usage_fallback_sees_stderr_with_emoji(tmp_path):
    (tmp_path / "main.py").write_text(
        "import sys\n"
        "if '--help' in sys.argv:\n"
        "    print('usage: main.py FILE \\U0001F373')\n"
        "    sys.exit(0)\n"
        "if len(sys.argv) > 1:\n"
        "    print('read ok \\U0001F373')\n"
        "    sys.exit(0)\n"
        "sys.stderr.write('usage: main.py FILE \\U0001F30F\\n')\n"
        "sys.exit(2)\n",
        encoding="utf-8",
    )
    res = SandboxRunner().smoke_run(str(tmp_path), entry_point="main.py", allow_fallback=True)
    assert res.is_success  # falls back to --help + fixture, both clean


def test_traceback_with_emoji_is_not_hidden(tmp_path):
    """A crash whose traceback contains emoji must still count as a crash (no false pass)."""
    (tmp_path / "main.py").write_text(
        "import sys\n"
        "if '--help' in sys.argv:\n"
        "    print('usage: main.py FILE')\n"
        "    sys.exit(0)\n"
        "if len(sys.argv) > 1:\n"
        "    raise ValueError('bad file \\U0001F30F')\n"
        "sys.stderr.write('usage: main.py FILE\\n')\n"
        "sys.exit(2)\n",
        encoding="utf-8",
    )
    res = SandboxRunner().smoke_run(str(tmp_path), entry_point="main.py", allow_fallback=True)
    assert not res.is_success


def test_every_text_subprocess_call_sets_utf8():
    for rel in ("mas/analysis/sandbox.py", "mas/analysis/quality_tools.py", "mas/core/checkpoints.py", "eval/runner.py"):
        src = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        for m in re.finditer(r"text=True,", src):
            window = src[m.end(): m.end() + 120]
            assert 'encoding="utf-8"' in window, f"{rel}: text=True without UTF-8 decoding"


# ---------------------------------------------------------------- per-task budget stop (DEC-048)
class _Gov:
    def __init__(self, remaining):
        self.remaining = remaining

    def get_ledger_stats(self):
        return {"remaining_internal_attempts": self.remaining}


def test_budget_allows_task_uses_pending_systems_only():
    from eval.runner import TASK_REQUEST_RESERVE, budget_allows_task

    full = sum(TASK_REQUEST_RESERVE[s] for s in ("mas", "chatdev", "single"))
    assert budget_allows_task(_Gov(full), ["mas", "chatdev", "single"])[0] is True
    assert budget_allows_task(_Gov(full - 1), ["mas", "chatdev", "single"])[0] is False
    # Only the single agent still to run: a small remainder is enough.
    assert budget_allows_task(_Gov(TASK_REQUEST_RESERVE["single"]), ["single"])[0] is True
    # Nothing pending: never blocks.
    assert budget_allows_task(_Gov(0), [])[0] is True


def test_runner_checks_budget_before_starting_a_task():
    src = open(os.path.join(ROOT, "eval", "runner.py"), encoding="utf-8").read()
    i_check = src.index("budget_allows_task(governor, pending)")
    i_mas = src.index("# 1. Run MAS", i_check)
    i_loop = src.rindex("for r_num in range(repeat_no, repeat_no + repeats):", 0, i_check)
    # Inside the repeat loop, before MAS starts (not after it has spent requests).
    assert i_loop < i_check < i_mas and "budget_stopped = True" in src[i_check:i_mas]
