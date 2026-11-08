from mas.core.llm import extract_json

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

res = extract_json(s)
print("extract_json result:", res)

