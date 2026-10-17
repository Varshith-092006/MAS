import os
import sqlite3

def main():
    if not os.path.exists("mas.db"):
        print("mas.db does not exist!")
        return
        
    con = sqlite3.connect("mas.db")
    cur = con.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
    print("=== Database Tables and Counts ===")
    for t in tables:
        count = cur.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
        print(f"  {t}: {count}")
    
    # Check runs sample
    if "runs" in tables:
        print("\n=== Runs Summary ===")
        rows = cur.execute("SELECT run_id, system, model, execution_mode, token_provenance, total_tokens, estimated_cost FROM runs LIMIT 10").fetchall()
        for r in rows:
            print(f"  {r}")
            
    con.close()
    
    print("\n=== Workspace Directories ===")
    for p in ["eval/workspaces", "workspace"]:
        if os.path.exists(p):
            entries = os.listdir(p)
            print(f"  {p}: {len(entries)} items -> {entries[:5]}")
        else:
            print(f"  {p}: does not exist")

if __name__ == "__main__":
    main()
