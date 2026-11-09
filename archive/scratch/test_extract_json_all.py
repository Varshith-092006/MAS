import json, re
from typing import Optional, Dict, Any

def test_extract(content: str) -> Optional[Dict[str, Any]]:
    if not content:
        return None
    text = content.strip()
    try:
        data = json.loads(text, strict=False)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if match:
        try:
            data = json.loads(match.group(1), strict=False)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            data = json.loads(candidate, strict=False)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        cleaned = re.sub(r",\s*([}\]])", r"\1", candidate)
        try:
            data = json.loads(cleaned, strict=False)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return None

sample_output = """We need to produce a CodePatch JSON with files main.py and test_main.py.

```json
{
  "files": ["main.py", "test_main.py"],
  "file_contents": {
    "main.py": "import sys

def solve(query):
    return f'Explanation: {query}'

def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--help':
        print('Help message')
        return 0
    return 0

if __name__ == '__main__':
    main()
",
    "test_main.py": "from main import solve

def test_solve():
    assert solve('gravity') is not None
"
  },
  "summary": "Implemented CLI solver",
  "tests_expected": ["test_solve"]
}
```
Here is the summary of changes."""

result = test_extract(sample_output)
print("Extracted successfully?", result is not None)
if result:
    print("Files:", result.get("files"))
    print("main.py length:", len(result.get("file_contents", {}).get("main.py", "")))

