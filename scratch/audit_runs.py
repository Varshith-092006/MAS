import sqlite3

conn = sqlite3.connect("mas.db")
cursor = conn.cursor()

updates = [
    (
        "MODEL_MISMATCH_DIAGNOSTIC: Requested openai/gpt-4o-mini but reviewer was served by free models (liquid/lfm-2.5-2.6b:free, cohere, nemotron); retained for audit, excluded from research aggregates.",
        "live_pilot_mas_1791691672"
    ),
    (
        "MODEL_MISMATCH_DIAGNOSTIC: Requested openai/gpt-4o but reviewer was served by free models (cohere/north-mini-code:free); unaligned QuickStudy prompt; retained for audit, excluded from GPT-4o research aggregates.",
        "mas_srdd_educ_01_live"
    ),
    (
        "DIAGNOSTIC_RUN: Dataset integrity limitation (used unaligned QuickStudy prompt instead of canonical Science Question Solver); model was verified openai/gpt-4o; retained for audit, excluded from canonical aggregates.",
        "cd_srdd_educ_01_live"
    )
]

for reason, run_id in updates:
    cursor.execute("UPDATE runs SET failure_reason = ? WHERE run_id = ?", (reason, run_id))

conn.commit()
print("Audited runs updated successfully:")
for row in cursor.execute("SELECT run_id, model, actual_model, failure_reason FROM runs").fetchall():
    print(f"  {row[0]}: model={row[1]}, actual={row[2]}")
    print(f"    failure_reason: {row[3][:80]}...")
