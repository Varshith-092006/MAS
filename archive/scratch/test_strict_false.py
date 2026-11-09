import re, json

s = '''```json
{
  "files": ["main.py"],
  "file_contents": {
    "main.py": "import sys

def solve(q):
    return 'solution'

if __name__ == '__main__':
    print('running')
"
  },
  "summary": "Implementation",
  "tests_expected": ["test1"]
}
```'''

match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", s.strip())
if match:
    try:
        data = json.loads(match.group(1), strict=False)
        print("Success with strict=False:", data.keys())
    except Exception as e:
        print("Failed:", e)

