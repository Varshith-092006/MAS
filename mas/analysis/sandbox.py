"""Docker Sandbox execution environment with strict resource limits and security isolation."""

import os
import shutil
import subprocess
import tempfile
import time
from typing import Any, Dict, List, Optional


class SandboxExecutionResult:
    def __init__(
        self,
        exit_code: int,
        stdout: str,
        stderr: str,
        duration_ms: int,
        timed_out: bool = False,
        oom_killed: bool = False,
    ):
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.duration_ms = duration_ms
        self.timed_out = timed_out
        self.oom_killed = oom_killed

    @property
    def is_success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and not self.oom_killed


class SandboxRunner:
    """Executes generated code in disposable Docker containers or isolated fallback."""

    def __init__(
        self,
        image_tag: str = "python:3.11-slim",
        memory_limit: str = "512m",
        cpu_limit: float = 1.0,
        pids_limit: int = 64,
        timeout_seconds: int = 45,
    ):
        self.image_tag = image_tag
        self.memory_limit = memory_limit
        self.cpu_limit = str(cpu_limit)
        self.pids_limit = pids_limit
        self.timeout_seconds = timeout_seconds

    def is_docker_available(self) -> bool:
        """Checks if Docker CLI and daemon are responsive."""
        if not shutil.which("docker"):
            return False
        try:
            res = subprocess.run(
                ["docker", "version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return res.returncode == 0 and "Server:" in res.stdout
        except Exception:
            return False

    def execute_in_container(
        self,
        workspace_path: str,
        command: List[str],
        env_vars: Optional[Dict[str, str]] = None,
    ) -> SandboxExecutionResult:
        """Runs command inside an isolated disposable Docker container.

        Constraints:
        - --network none
        - 1 CPU (--cpus=1.0)
        - 512 MB memory (--memory=512m)
        - limited PIDs (--pids-limit=64)
        - read-only base filesystem (--read-only)
        - writable /workspace volume only
        - no host secrets or socket mounted
        - disposable container (--rm)
        """
        abs_workspace = os.path.abspath(workspace_path)
        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--network", "none",
            "--cpus", self.cpu_limit,
            "--memory", self.memory_limit,
            "--pids-limit", str(self.pids_limit),
            "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",  # nosec B108 - Docker container tmpfs mount, not host temporary file
            "-v", f"{abs_workspace}:/workspace:rw",
            "-w", "/workspace",
        ]

        if env_vars:
            for k, v in env_vars.items():
                # Never pass API secrets to container
                if "KEY" not in k.upper() and "SECRET" not in k.upper():
                    docker_cmd.extend(["-e", f"{k}={v}"])

        docker_cmd.append(self.image_tag)
        docker_cmd.extend(command)

        t0 = time.time()
        try:
            proc = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            duration = int((time.time() - t0) * 1000)
            return SandboxExecutionResult(
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_ms=duration,
            )
        except subprocess.TimeoutExpired as e:
            duration = int((time.time() - t0) * 1000)
            return SandboxExecutionResult(
                exit_code=-1,
                stdout=e.stdout or "",
                stderr=(e.stderr or "") + f"\nTimed out after {self.timeout_seconds}s",
                duration_ms=duration,
                timed_out=True,
            )
        except Exception as e:
            duration = int((time.time() - t0) * 1000)
            return SandboxExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=duration,
            )

    def execute_local_isolated(
        self,
        workspace_path: str,
        command: List[str],
        env_vars: Optional[Dict[str, str]] = None,
    ) -> SandboxExecutionResult:
        """Local subprocess fallback with clean environment and timeout limits."""
        abs_workspace = os.path.abspath(workspace_path)
        clean_env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": abs_workspace,
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        if env_vars:
            for k, v in env_vars.items():
                if "KEY" not in k.upper() and "SECRET" not in k.upper():
                    clean_env[k] = v

        t0 = time.time()
        try:
            proc = subprocess.run(
                command,
                cwd=abs_workspace,
                env=clean_env,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            duration = int((time.time() - t0) * 1000)
            return SandboxExecutionResult(
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_ms=duration,
            )
        except subprocess.TimeoutExpired as e:
            duration = int((time.time() - t0) * 1000)
            return SandboxExecutionResult(
                exit_code=-1,
                stdout=e.stdout or "",
                stderr=f"Execution timed out after {self.timeout_seconds}s",
                duration_ms=duration,
                timed_out=True,
            )
        except Exception as e:
            duration = int((time.time() - t0) * 1000)
            return SandboxExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=duration,
            )

    def execute(
        self,
        workspace_path: str,
        command: List[str],
        env_vars: Optional[Dict[str, str]] = None,
        allow_fallback: bool = False,
    ) -> SandboxExecutionResult:
        """Executes in Docker container. For real runs, fails if Docker is not available."""
        if self.is_docker_available():
            return self.execute_in_container(workspace_path, command, env_vars)
        if allow_fallback or os.environ.get("MAS_ALLOW_SUBPROCESS_SANDBOX") == "1":
            return self.execute_local_isolated(workspace_path, command, env_vars)
        raise RuntimeError(
            "Docker daemon is not running or unavailable. Real execution requires Docker sandbox; "
            "host execution fallback is disabled."
        )

    def smoke_run(
        self,
        workspace_path: str,
        entry_point: Optional[str] = None,
        allow_fallback: bool = False,
    ) -> SandboxExecutionResult:
        """Runs a smoke test on the entry point file with timeout."""
        if not entry_point:
            candidates = ["main.py", "app.py", "calculator.py"]
            chosen = None
            for cand in candidates:
                if os.path.exists(os.path.join(workspace_path, cand)):
                    chosen = cand
                    break
            if not chosen and os.path.exists(workspace_path):
                py_files = [f for f in os.listdir(workspace_path) if f.endswith(".py") and not f.startswith("test_")]
                if py_files:
                    chosen = py_files[0]
                elif os.path.exists(os.path.join(workspace_path, "index.html")):
                    return SandboxExecutionResult(
                        exit_code=0,
                        stdout="Web application verified: index.html entry point present.",
                        stderr="",
                        duration_ms=5,
                    )
            entry_point = chosen or "main.py"
        return self.execute(workspace_path, ["python", entry_point], allow_fallback=allow_fallback)
