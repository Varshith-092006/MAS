import json
from mas.core.llm import extract_json

truncated_sample = """Here is the plan:
{
  "id": "plan-srdd_educ_01",
  "task_id": "srdd_educ_01",
  "name": "Science Question Solver",
  "description": "Step-by-step science question solver providing explanations and solutions.",
  "complexity": "SIMPLE",
  "files": ["main.py"],
  "sprint_goals": [
    "Goal 1"
  ],
  "acceptance_criteria": [
    "Criteria 1",
    "Criteria 2: photosynthesis step
"""

result = extract_json(truncated_sample)
print("Truncated parsed:", result)

