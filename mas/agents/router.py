"""Deterministic Complexity Router making zero LLM calls."""

import re
from typing import Any, Dict, List, Tuple


class ComplexityRouter:
    """Classifies software requirements into SIMPLE or STRUCTURED execution paths

    using deterministic keyword, regex, separator, and length heuristics.
    Zero LLM calls are made.
    """

    FEATURE_RULES = {
        "persistence": re.compile(
            r"\b(database|sql|sqlite|postgres|postgresql|mongodb|persistence|storage|tables?|repository)\b",
            re.IGNORECASE,
        ),
        "authentication": re.compile(
            r"\b(auth|authentication|login|signup|sign-in|account|accounts|password|passwords|token|tokens|jwt|session|sessions)\b",
            re.IGNORECASE,
        ),
        "multiple_roles": re.compile(
            r"\b(admin|admins|role|roles|permission|permissions|rbac|superadmin|manager|managers|guest|staff|doctor|patient)\b",
            re.IGNORECASE,
        ),
        "external_integrations": re.compile(
            r"\b(api|apis|rest|http|https|webhook|webhooks|external|third-party|endpoints?|integration|integrations)\b",
            re.IGNORECASE,
        ),
        "analytics": re.compile(
            r"\b(analytics?|metrics?|reports?|reporting|dashboard|dashboards|statistics|charts?|graphs?)\b",
            re.IGNORECASE,
        ),
        "workflow_state": re.compile(
            r"\b(state\s+machine|workflow|workflows|stages?|pipeline|pipelines?|transitions?|lifecycle|approval)\b",
            re.IGNORECASE,
        ),
    }

    SEPARATOR_PATTERNS = re.compile(r"(?:,|;| and |\n\s*[-*•]|\n\s*\d+\.)", re.IGNORECASE)

    def __init__(self, threshold: int = 4):
        self.threshold = threshold

    def score(self, requirement: str) -> Tuple[int, Dict[str, Any]]:
        """Calculates complexity score and returns matched features."""
        normalized = requirement.strip().lower()
        score = 0
        matched_features: Dict[str, Any] = {}

        # 1. Feature pattern rules (1 point each)
        for feature_name, regex in self.FEATURE_RULES.items():
            matches = regex.findall(normalized)
            if matches:
                score += 1
                matched_features[feature_name] = list(set(matches))

        # 2. Separators and multi-feature indicator rule
        # count commas, ' and ', semicolons, bullets
        separators = self.SEPARATOR_PATTERNS.findall(normalized)
        sep_count = len(separators)
        matched_features["separator_count"] = sep_count

        if sep_count >= 7:
            score += 2
            matched_features["separator_bonus"] = 2
        elif sep_count >= 4:
            score += 1
            matched_features["separator_bonus"] = 1
        else:
            matched_features["separator_bonus"] = 0

        # 3. Documented length rule: word count > 80 -> +1
        words = normalized.split()
        word_count = len(words)
        matched_features["word_count"] = word_count
        if word_count > 80:
            score += 1
            matched_features["length_bonus"] = 1
        else:
            matched_features["length_bonus"] = 0

        return score, matched_features

    def route(self, requirement: str) -> Tuple[str, int, Dict[str, Any]]:
        """Returns label ('SIMPLE' or 'STRUCTURED'), total score, and matched features."""
        score, features = self.score(requirement)
        label = "STRUCTURED" if score >= self.threshold else "SIMPLE"
        return label, score, features
