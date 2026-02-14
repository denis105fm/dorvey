"""Affiliate rules validation."""

import re
from typing import Optional


def validate_content(
    text: str,
    forbidden_words: Optional[list] = None,
    required_words: Optional[list] = None,
) -> tuple:
    """Check content compliance. Returns (is_valid, violations)."""
    violations = []
    text_lower = text.lower()
    if forbidden_words:
        for word in forbidden_words:
            pat = r"\b" + re.escape(word.lower()) + r"\b"
            if re.search(pat, text_lower, re.IGNORECASE):
                violations.append("Forbidden: " + word)
    if required_words:
        for word in required_words:
            if word.lower() not in text_lower:
                violations.append("Required: " + word)
    return len(violations) == 0, violations


def get_forbidden_words(rules: Optional[dict]) -> list:
    if not rules or not isinstance(rules, dict):
        return []
    fw = rules.get("forbidden_words")
    return [str(w) for w in fw] if isinstance(fw, list) else []


def get_required_words(rules: Optional[dict]) -> list:
    if not rules or not isinstance(rules, dict):
        return []
    rw = rules.get("required_words")
    return [str(w) for w in rw] if isinstance(rw, list) else []
