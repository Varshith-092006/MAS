"""Checkpoint management and rollback support."""

import os
import shutil
import subprocess
from typing import Dict, Optional


class CheckpointManager:
    """Manages workspace snapshots and rollback."""

    def __init__(self, workspace_path: str):
        self.workspace_path = os.path.abspath(workspace_path)
        self.snapshot_dir = os.path.join(self.workspace_path, ".mas_snapshots")
        os.makedirs(self.workspace_path, exist_ok=True)
        self._checkpoints: Dict[str, str] = {}
        self._counter = 0

    def _is_git_repo(self) -> bool:
        return os.path.isdir(os.path.join(self.workspace_path, ".git"))

    def save_checkpoint(self, checkpoint_id: Optional[str] = None) -> str:
        """Saves current workspace state and returns a reference string."""
        self._counter += 1
        cid = checkpoint_id or f"cp_{self._counter}"

        # Git commit checkpoint if git repo
        if self._is_git_repo():
            try:
                subprocess.run(["git", "add", "."], cwd=self.workspace_path, capture_output=True, check=True)
                proc = subprocess.run(
                    ["git", "commit", "-m", f"checkpoint: {cid}", "--allow-empty"],
                    cwd=self.workspace_path,
                    capture_output=True,
                    text=True,
                )
                rev = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=self.workspace_path,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                commit_hash = rev.stdout.strip()
                self._checkpoints[cid] = commit_hash
                return cid
            except Exception:
                pass

        # Filesystem snapshot fallback
        os.makedirs(self.snapshot_dir, exist_ok=True)
        dest = os.path.join(self.snapshot_dir, cid)
        if os.path.exists(dest):
            shutil.rmtree(dest)
        
        # Copy files excluding .mas_snapshots and .git
        shutil.copytree(
            self.workspace_path,
            dest,
            ignore=shutil.ignore_patterns(".mas_snapshots", ".git", "__pycache__", "*.pyc"),
        )
        self._checkpoints[cid] = dest
        return cid

    def restore_checkpoint(self, checkpoint_id: str) -> bool:
        """Restores workspace to the referenced checkpoint."""
        if checkpoint_id not in self._checkpoints:
            return False

        ref = self._checkpoints[checkpoint_id]

        if self._is_git_repo() and os.path.exists(os.path.join(self.workspace_path, ".git")):
            try:
                subprocess.run(
                    ["git", "reset", "--hard", ref],
                    cwd=self.workspace_path,
                    capture_output=True,
                    check=True,
                )
                subprocess.run(
                    ["git", "clean", "-fd"],
                    cwd=self.workspace_path,
                    capture_output=True,
                    check=True,
                )
                return True
            except Exception:
                pass

        # Snapshot folder fallback
        if os.path.isdir(ref):
            # Clean current workspace files (except .mas_snapshots and .git)
            for item in os.listdir(self.workspace_path):
                if item in [".mas_snapshots", ".git"]:
                    continue
                full_path = os.path.join(self.workspace_path, item)
                if os.path.isdir(full_path):
                    shutil.rmtree(full_path)
                else:
                    os.remove(full_path)

            # Copy back from snapshot
            for item in os.listdir(ref):
                src = os.path.join(ref, item)
                dst = os.path.join(self.workspace_path, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
            return True

        return False
