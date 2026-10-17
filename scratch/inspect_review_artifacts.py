import sqlite3
import json

conn = sqlite3.connect('mas.db')
c = conn.cursor()

pilot_id = "mas_dev_csv_sales_1792211689"

rows = c.execute('SELECT artifact_id, type, version, json_data FROM artifacts WHERE run_id = ? ORDER BY artifact_id', (pilot_id,)).fetchall()

for aid, atype, aver, raw in rows:
    data = json.loads(raw)
    tl = atype.lower()
    print(f"\n==========================================")
    print(f"ARTIFACT {aid} | TYPE: {atype} | VERSION: {aver}")
    print(f"==========================================")
    if "review" in tl:
        print("STATUS:", data.get("status"))
        print("SUMMARY:", data.get("summary"))
        print("FINDINGS:")
        for idx, f in enumerate(data.get("findings", []), 1):
            print(f"  Finding #{idx}: {repr(f)}")
    elif "test" in tl:
        print("STATUS:", data.get("status"))
        print("PASSED:", data.get("passed"))
        print("TOTAL:", data.get("total_tests"), "PASSED:", data.get("passed_tests"), "FAILED:", data.get("failed_tests"))
        print("SUMMARY:", data.get("summary"))
        for t in data.get("test_results", []):
            print(f"  Test: {t}")
    elif "reflection" in tl:
        print("ACTION:", data.get("action"))
        print("SCORE:", data.get("score"))
        print("SCORE_DELTA:", data.get("score_delta"))
        print("RATIONALE:", data.get("rationale"))
    elif "codepatch" in tl:
        print("FILES:", list(data.get("files", {}).keys()) if isinstance(data.get("files"), dict) else data.get("files"))
        print("DESCRIPTION:", data.get("description"))
