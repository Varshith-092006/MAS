import subprocess, sys

workspace = r"eval\workspaces\mas_srdd_educ_01_r1_attempt8"

tests = [
    (["python", "main.py", "--help"], 0, "usage instructions / help"),
    (["python", "main.py"], 0, "zero arguments clean exit"),
    (["python", "main.py", "What is the speed if distance is 100 km and time is 2 h?"], 0, "physics speed query"),
    (["python", "main.py", "What is the atomic number of carbon?"], 0, "chemistry carbon atomic number"),
    (["python", "main.py", "Explain the steps of photosynthesis."], 0, "biology photosynthesis"),
    (["python", "main.py", "What is the formula for water?"], 0, "chemistry formula for water"),
    (["python", "main.py", ""], 1, "invalid/empty input"),
]

for cmd, expected_code, desc in tests:
    res = subprocess.run(cmd, cwd=workspace, capture_output=True, text=True)
    status = "PASS" if res.returncode == expected_code else "FAIL"
    print(f"[{status}] {desc} -> exit code {res.returncode} (expected {expected_code})")
    if status == "FAIL":
        print(f"   Stdout: {res.stdout.strip()[:100]}")
        print(f"   Stderr: {res.stderr.strip()[:100]}")

