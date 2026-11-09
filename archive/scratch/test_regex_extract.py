import re, ast

text3 = """**main.py**:
```python
import sys

def main():
    return 0
```
"""

file_pattern = re.compile(
    r"(?:#{1,4}\s*[`*]*([a-zA-Z0-9_\-\.\/]+\.py)[`*]*|(?:\*\*|`)([a-zA-Z0-9_\-\.\/]+\.py)(?:\*\*|`):?|#\s*(?:file|filename):\s*([a-zA-Z0-9_\-\.\/]+\.py))\s*\n[\s\S]*?```(?:python)?\s*([\s\S]*?)(?:```|$)",
    re.IGNORECASE,
)

for m in file_pattern.finditer(text3):
    fname = m.group(1) or m.group(2) or m.group(3)
    code = m.group(4).strip()
    print("Match on text3:", fname, "length:", len(code))
