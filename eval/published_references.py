"""Verified published baseline reference metrics from the iCoder paper.

Source Citation:
You, Y., et al. "iCoder: A Multi-Agent Software Development Platform."
Information and Software Technology 198 (2026) 108224.
Pages 11-13, Tables 1, 2, 3, 4.

ALL VALUES ARE PUBLISHED LITERATURE REFERENCES AND WERE NOT EXECUTED LOCALLY.
"""

from typing import Any, Dict, Optional

PUBLISHED_REFERENCES: Dict[str, Dict[str, Any]] = {
    "gpt-3.5-turbo": {
        "model_condition": "gpt-3.5-turbo",
        "tasks_evaluated": 100,
        "source_paper": "You et al., Information and Software Technology 198 (2026) 108224",
        "quality_table": "Table 1, Page 12",
        "overhead_table": "Table 3, Page 13",
        "icoder_quality": 0.690192,
        "chatdev_quality": 0.590626,
        "icoder_completeness": 0.95206186,
        "chatdev_completeness": 0.90219378,
        "icoder_executability": 0.88,
        "chatdev_executability": 0.81,
        "icoder_consistency": 0.823800,
        "chatdev_consistency": 0.808389,
        "icoder_tokens_per_task": 411144.62,
        "chatdev_tokens_per_task": 22327.02,
        "icoder_duration_seconds": 2700.43,
        "chatdev_duration_seconds": 439.59,
        "icoder_loc": 168.92,
        "chatdev_loc": 113.93,
        "metric_definition": "Quality = Completeness × Executability × Consistency",
        "status_label": "PUBLISHED REFERENCE — NOT EXECUTED LOCALLY",
    },
    "gpt-4o": {
        "model_condition": "gpt-4o",
        "tasks_evaluated": 20,
        "source_paper": "You et al., Information and Software Technology 198 (2026) 108224",
        "quality_table": "Table 2, Page 12",
        "overhead_table": "Table 4, Page 13",
        "icoder_quality": 0.792398,
        "chatdev_quality": 0.654990,
        "icoder_completeness": 0.99599198,
        "chatdev_completeness": 1.0,
        "icoder_executability": 0.95,
        "chatdev_executability": 0.80,
        "icoder_consistency": 0.837460,
        "chatdev_consistency": 0.818738,
        "icoder_tokens_per_task": 104883.2,
        "chatdev_tokens_per_task": 30416.6,
        "icoder_duration_seconds": 1620.05,
        "chatdev_duration_seconds": 1058.7,
        "icoder_loc": 216.15,
        "chatdev_loc": 125.95,
        "metric_definition": "Quality = Completeness × Executability × Consistency",
        "status_label": "PUBLISHED REFERENCE — NOT EXECUTED LOCALLY",
    },
}


def get_published_reference(model: str = "gpt-4o") -> Dict[str, Any]:
    """Retrieves verified published baseline metrics for a specific model condition."""
    m_clean = model.lower()
    if "3.5" in m_clean or "35" in m_clean:
        return dict(PUBLISHED_REFERENCES["gpt-3.5-turbo"])
    return dict(PUBLISHED_REFERENCES["gpt-4o"])
