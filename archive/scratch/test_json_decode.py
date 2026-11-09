import json

# Unescaped literal newline inside JSON string
s = '{"files": ["main.py"], "file_contents": {"main.py": "def main():\n    print(\'hi\')\n"}}'
try:
    json.loads(s)
    print("strict=True succeeded")
except Exception as e:
    print("strict=True failed:", type(e), e)

try:
    res = json.loads(s, strict=False)
    print("strict=False succeeded! Result:", res)
except Exception as e:
    print("strict=False failed:", type(e), e)

