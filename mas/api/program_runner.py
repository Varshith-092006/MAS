"""Run a generated project from the web UI (DEC-053).

Two ways:
  * quick_test(): the same headless smoke protocol the evaluator uses (SandboxRunner.smoke_run),
    output captured and returned to the browser. Read-only for scoring: nothing is re-scored.
  * open_program(): starts the program in a new console window on this computer so the user can
    interact with it (type input, see a tkinter window).

Both run a temporary COPY of the run folder, so programs that write files (databases, saves)
never change the official benchmark folders. Neither passes API keys or secrets to the program.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional

# Files ChatDev / MAS keep next to the code that are not part of the program.
_SKIP_DIRS = {".mas_snapshots", "__pycache__", ".git"}
_MAX_OUTPUT = 20_000


def find_entry_point(workspace: str) -> Optional[str]:
    """Same choice as the evaluator (eval/scorers/icoder_metrics.py, v1.3)."""
    for cand in ("main.py", "app.py"):
        if os.path.isfile(os.path.join(workspace, cand)):
            return cand
    for f in sorted(os.listdir(workspace)):
        if f.endswith(".py") and not f.startswith("test_"):
            return f
    return None


def copy_workspace(workspace: str) -> str:
    """Copies the run folder to a fresh temp folder and returns its path."""
    dest = tempfile.mkdtemp(prefix="mas_preview_")
    shutil.copytree(
        workspace,
        dest,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(*_SKIP_DIRS),
    )
    return dest


def clean_env(workdir: str) -> Dict[str, str]:
    """Environment for a generated program: system basics only, never keys, tokens or secrets."""
    keep = ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "HOME", "USERPROFILE", "LANG")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env.update(
        {
            "PYTHONPATH": workdir,
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        }
    )
    return {k: v for k, v in env.items() if not any(s in k.upper() for s in ("KEY", "TOKEN", "SECRET", "PASSWORD"))}


def _trim(text: str) -> str:
    text = text or ""
    return text if len(text) <= _MAX_OUTPUT else text[:_MAX_OUTPUT] + "\n… (output cut off)"


def quick_test(workspace: str, sandbox_runner=None) -> dict:
    """Runs the evaluator's headless smoke protocol on a copy of the project."""
    from mas.analysis.sandbox import SandboxRunner

    entry = find_entry_point(workspace)
    if not entry:
        return {"entry_point": None, "success": False, "exit_code": None, "stdout": "", "stderr": "No Python entry file found.", "duration_ms": 0, "timed_out": False}

    copy = copy_workspace(workspace)
    try:
        runner = sandbox_runner or SandboxRunner()
        res = runner.smoke_run(copy, entry_point=entry, allow_fallback=True)
        return {
            "entry_point": entry,
            "success": bool(res.is_success),
            "exit_code": res.exit_code,
            "stdout": _trim(res.stdout),
            "stderr": _trim(res.stderr),
            "duration_ms": res.duration_ms,
            "timed_out": bool(res.timed_out),
        }
    finally:
        shutil.rmtree(copy, ignore_errors=True)


def build_open_command(entry: str, args: List[str]) -> List[str]:
    """Command that runs the program and keeps the window open afterwards so output stays readable."""
    py = sys.executable
    if os.name == "nt":
        # cmd /k keeps the console open after the program ends.
        return ["cmd", "/k", py, entry, *args]
    return [py, entry, *args]


def open_program(workspace: str, args_text: str = "", popen=None) -> dict:
    """Starts the program in a new console window on this computer (copy of the folder)."""
    entry = find_entry_point(workspace)
    if not entry:
        raise FileNotFoundError("No Python entry file found.")
    try:
        args = shlex.split(args_text or "", posix=(os.name != "nt"))
    except ValueError as exc:
        raise ValueError(f"Could not read the arguments: {exc}") from exc

    copy = copy_workspace(workspace)
    cmd = build_open_command(entry, args)
    kwargs = {"cwd": copy, "env": clean_env(copy)}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
    else:
        kwargs["start_new_session"] = True
    (popen or subprocess.Popen)(cmd, **kwargs)
    return {"entry_point": entry, "args": args, "copy_folder": copy}
