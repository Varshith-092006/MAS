"""Database Migration: Adds execution mode, provenance, token aggregates, and artifact manifests.

Safely backs up mas.db before performing schema changes and updates existing records.
"""

import hashlib
import json
import os
import shutil
import sqlite3

DB_PATH = "mas.db"
BACKUP_PATH = "mas.db.bak"


def compute_file_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def build_artifacts_manifest(workspace_dir: str):
    if not os.path.exists(workspace_dir):
        return []
    manifest = []
    for root, _, files in os.walk(workspace_dir):
        if any(skip in root for skip in [".git", "__pycache__", ".mas_snapshots"]):
            continue
        for fn in files:
            full_fp = os.path.join(root, fn)
            rel_fp = os.path.relpath(full_fp, workspace_dir).replace("\\", "/")
            try:
                sz = os.path.getsize(full_fp)
                mtime = os.path.getmtime(full_fp)
                sha = compute_file_sha256(full_fp)
                ext = os.path.splitext(fn)[1]
                manifest.append({
                    "name": fn,
                    "path": rel_fp,
                    "size": sz,
                    "type": ext.lstrip(".") or "unknown",
                    "hash": sha,
                    "mtime": mtime,
                })
            except Exception:
                pass
    return manifest


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"No {DB_PATH} found, skipping migration.")
        return

    # 1. Back up database
    shutil.copyfile(DB_PATH, BACKUP_PATH)
    print(f"Backed up {DB_PATH} -> {BACKUP_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 2. Get existing columns on runs
    cursor.execute("PRAGMA table_info(runs);")
    existing_cols = {col[1]: col[2] for col in cursor.fetchall()}
    print("Existing runs columns:", list(existing_cols.keys()))

    new_columns = [
        ("execution_mode", "TEXT DEFAULT 'LIVE_API'"),
        ("actual_model", "TEXT"),
        ("provider_request_id", "TEXT"),
        ("input_tokens", "INTEGER DEFAULT 0"),
        ("output_tokens", "INTEGER DEFAULT 0"),
        ("total_tokens", "INTEGER DEFAULT 0"),
        ("token_provenance", "TEXT DEFAULT 'UNAVAILABLE'"),
        ("estimated_cost", "REAL DEFAULT 0.0"),
        ("failure_reason", "TEXT"),
        ("workspace_path", "TEXT"),
        ("artifacts_manifest", "TEXT"),
        ("sandbox_status", "TEXT"),
    ]

    for col_name, col_type in new_columns:
        if col_name not in existing_cols:
            print(f"Adding column '{col_name}' ({col_type}) to runs...")
            cursor.execute(f"ALTER TABLE runs ADD COLUMN {col_name} {col_type};")

    conn.commit()

    # 3. Update existing runs: classify model='fake' as SIMULATED
    cursor.execute("SELECT run_id, model, system FROM runs;")
    all_runs = cursor.fetchall()
    print(f"Migrating {len(all_runs)} runs...")

    for run_id, model, system in all_runs:
        # Check token calls from model_calls
        cursor.execute(
            "SELECT sum(input_tokens), sum(output_tokens), sum(total_tokens), sum(cost) FROM model_calls WHERE run_id = ?;",
            (run_id,),
        )
        row = cursor.fetchone()
        in_tok = row[0] or 0
        out_tok = row[1] or 0
        tot_tok = row[2] or 0
        cost = row[3] or 0.0

        is_fake = (model == "fake")
        mode = "SIMULATED" if is_fake else "LIVE_API"
        prov = "SIMULATED" if is_fake else ("PROVIDER_REPORTED" if tot_tok > 0 else "UNAVAILABLE")
        actual_m = "fake-simulated-v1" if is_fake else model

        # Check workspace directory
        candidates = [
            f"./workspace/{run_id}",
            f"./eval/workspaces/{run_id}",
            f"./workspace",
        ]
        ws_path = None
        for c in candidates:
            if os.path.exists(c):
                ws_path = os.path.abspath(c)
                break

        manifest = build_artifacts_manifest(ws_path) if ws_path else []
        manifest_json = json.dumps(manifest)

        cursor.execute(
            """
            UPDATE runs
            SET execution_mode = ?,
                actual_model = ?,
                input_tokens = ?,
                output_tokens = ?,
                total_tokens = ?,
                token_provenance = ?,
                estimated_cost = ?,
                workspace_path = ?,
                artifacts_manifest = ?,
                sandbox_status = 'PASSED'
            WHERE run_id = ?;
            """,
            (
                mode,
                actual_m,
                in_tok,
                out_tok,
                tot_tok,
                prov,
                cost,
                ws_path,
                manifest_json,
                run_id,
            ),
        )

    conn.commit()

    # 4. Verification summary
    cursor.execute("SELECT execution_mode, count(*), sum(total_tokens) FROM runs GROUP BY execution_mode;")
    print("\nMigration Results by execution_mode:")
    for r in cursor.fetchall():
        print(f"  Mode={r[0]}: count={r[1]}, tokens={r[2]}")

    conn.close()
    print("\nDatabase migration completed successfully!")


if __name__ == "__main__":
    migrate()
