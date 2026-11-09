#!/usr/bin/env python3
"""Sets up external/ChatDev cleanly and applies the local patch for benchmark reproducibility."""

import os
import subprocess
import sys

CHATDEV_REPO_URL = "https://github.com/OpenBMB/ChatDev.git"
BASE_COMMIT = "5defde31792346e0cc302f672a33e766ef955dd8"  # v1.0.0 tag
PINNED_COMMIT = "c1c31e28864df6b8b0394683b8286436ce41b5ce"
PATCH_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "patches", "chatdev_local.patch"))
TARGET_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "external", "ChatDev"))


def main():
    print("=" * 60)
    print("ChatDev Setup & Patch Tool")
    print("=" * 60)

    if not os.path.exists(TARGET_DIR):
        print(f"Cloning ChatDev from {CHATDEV_REPO_URL} into {TARGET_DIR}...")
        os.makedirs(os.path.dirname(TARGET_DIR), exist_ok=True)
        subprocess.run(["git", "clone", CHATDEV_REPO_URL, TARGET_DIR], check=True)
    else:
        print(f"ChatDev directory exists at {TARGET_DIR}.")

    # Check current HEAD
    res = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=TARGET_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    current_head = res.stdout.strip()
    print(f"Current ChatDev commit: {current_head}")

    if current_head == PINNED_COMMIT:
        print(f"ChatDev is already at pinned commit {PINNED_COMMIT}.")
        return

    # Check if working tree has changes
    diff_check = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=TARGET_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    if diff_check.stdout.strip():
        print("Warning: external/ChatDev has uncommitted changes. Stashing before patch...")
        subprocess.run(["git", "stash"], cwd=TARGET_DIR, check=True)

    print(f"Checking out base commit {BASE_COMMIT}...")
    subprocess.run(["git", "checkout", BASE_COMMIT], cwd=TARGET_DIR, check=True)

    if os.path.exists(PATCH_FILE) and os.path.getsize(PATCH_FILE) > 0:
        print(f"Applying patch {PATCH_FILE}...")
        apply_res = subprocess.run(
            ["git", "apply", "--ignore-whitespace", PATCH_FILE],
            cwd=TARGET_DIR,
            capture_output=True,
            text=True,
        )
        if apply_res.returncode != 0:
            print(f"git apply output: {apply_res.stderr}")
            print("Trying git apply with 3way fallback...")
            subprocess.run(["git", "apply", "-3", PATCH_FILE], cwd=TARGET_DIR, check=True)
        print("Patch applied successfully.")
    else:
        print(f"No patch file found at {PATCH_FILE} or file is empty.")

    print(f"ChatDev setup complete.")


if __name__ == "__main__":
    main()
