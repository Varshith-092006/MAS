import re, json
from mas.core.llm import extract_json

text = """Here is the plan:
```json
{
  "id": "plan-1",
  "task_id": "srdd_educ_01",
  "name": "Science Solver",
  "description": "Solve science questions",
  "metadata": {
    "version": "1.0",
    "sub": {
       "a": 1
    }
  },
  "acceptance_criteria": ["run --help"]
}
```
Hope this helps!"""

print("Result of extract_json on nested json inside code fence:")
result = extract_json(text)
print("Parsed:", result is not None)
if result:
    print("Keys:", list(result.keys()))

