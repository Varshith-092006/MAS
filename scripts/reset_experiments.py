"""Script to safely backup and reset all previous experimental data (Phase 1)."""

import os
import shutil
import sqlite3
import json
from datetime import datetime

def reset_all_experiments():
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.abspath(os.path.join("backups", f"experiment_backup_{timestamp}"))
    os.makedirs(backup_dir, exist_ok=True)
    
    print(f"[*] Creating recoverable backup in: {backup_dir}")
    
    db_path = "mas.db"
    backup_db_path = os.path.join(backup_dir, "mas_pre_reset.db")
    if os.path.exists(db_path):
        shutil.copy2(db_path, backup_db_path)
        print(f"    Copied {db_path} -> {backup_db_path}")
        
    for extra_file in ["results.csv", os.path.join("eval", "stats_report.md")]:
        if os.path.exists(extra_file):
            dest = os.path.join(backup_dir, os.path.basename(extra_file))
            shutil.copy2(extra_file, dest)
            print(f"    Copied {extra_file} -> {dest}")
            
    # Connect to DB and inspect counts before deletion
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    
    tables_to_inspect = [
        "runs", "evaluations", "agent_events", "artifacts", 
        "checkpoints", "model_calls", "metrics", "config_snapshots", "tasks"
    ]
    
    pre_counts = {}
    for tbl in tables_to_inspect:
        try:
            cnt = cur.execute(f"SELECT COUNT(*) FROM [{tbl}]").fetchone()[0]
            pre_counts[tbl] = cnt
        except sqlite3.OperationalError:
            pre_counts[tbl] = 0
            
    print("\n[*] Pre-reset database counts:")
    for tbl, cnt in pre_counts.items():
        print(f"    {tbl}: {cnt}")
        
    # Transactional foreign-key-safe deletion of experiment records
    print("\n[*] Executing foreign-key-safe transactional deletion...")
    cur.execute("PRAGMA foreign_keys = ON;")
    cur.execute("BEGIN TRANSACTION;")
    try:
        # Child tables first
        cur.execute("DELETE FROM metrics;")
        cur.execute("DELETE FROM model_calls;")
        cur.execute("DELETE FROM checkpoints;")
        cur.execute("DELETE FROM artifacts;")
        cur.execute("DELETE FROM agent_events;")
        cur.execute("DELETE FROM config_snapshots;")
        cur.execute("DELETE FROM runs;")
        cur.execute("DELETE FROM evaluations;")
        # Note: tasks table contains the canonical task definitions, not run records.
        con.commit()
        print("    Transaction committed successfully.")
    except Exception as e:
        con.rollback()
        print(f"    ERROR during deletion transaction: {e}. Rolled back!")
        con.close()
        raise e

    # Verify counts after deletion
    post_counts = {}
    for tbl in tables_to_inspect:
        try:
            cnt = cur.execute(f"SELECT COUNT(*) FROM [{tbl}]").fetchone()[0]
            post_counts[tbl] = cnt
        except sqlite3.OperationalError:
            post_counts[tbl] = 0
            
    cur.execute("VACUUM;")
    con.close()
    
    print("\n[*] Post-reset database counts:")
    for tbl, cnt in post_counts.items():
        print(f"    {tbl}: {cnt}")
        
    # Clean workspace directories
    print("\n[*] Cleaning generated artifact workspaces...")
    workspace_cleanup_counts = {}
    for ws_path in ["eval/workspaces", "workspace"]:
        ws_abs = os.path.abspath(ws_path)
        items_removed = 0
        if os.path.exists(ws_abs):
            for item in os.listdir(ws_abs):
                if item.startswith("."):
                    continue
                item_full = os.path.join(ws_abs, item)
                try:
                    if os.path.isdir(item_full):
                        shutil.rmtree(item_full)
                        items_removed += 1
                    elif os.path.isfile(item_full):
                        os.remove(item_full)
                        items_removed += 1
                except Exception as e:
                    print(f"    Warning: Could not remove {item_full}: {e}")
        workspace_cleanup_counts[ws_path] = items_removed
        print(f"    {ws_path}: Removed {items_removed} items. Directory now clean.")
        
    # Clean results.csv and stats report
    if os.path.exists("results.csv"):
        # Reset to header only
        header = "run_id,task_id,system,model,repeat_no,ablation,quality,quality_per_1k_tokens,completeness,executability,consistency,shared_test,ruff,bandit,radon,tokens,cost,pytest_pass_rate,coverage,status\n"
        with open("results.csv", "w", encoding="utf-8") as f:
            f.write(header)
        print("    results.csv reset to header only.")
        
    if os.path.exists(os.path.join("eval", "stats_report.md")):
        os.remove(os.path.join("eval", "stats_report.md"))
        print("    eval/stats_report.md removed.")
        
    # Write backup manifest
    manifest = {
        "timestamp": timestamp,
        "backup_directory": backup_dir,
        "pre_counts": pre_counts,
        "post_counts": post_counts,
        "workspaces_cleaned": workspace_cleanup_counts,
    }
    with open(os.path.join(backup_dir, "reset_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        
    print(f"\n[OK] Reset complete! Backup manifest written to {os.path.join(backup_dir, 'reset_manifest.json')}")
    return manifest

if __name__ == "__main__":
    reset_all_experiments()
