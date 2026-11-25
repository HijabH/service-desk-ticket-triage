"""Removes personal and secret data before ticket text is sent to an external LLM."""

import re

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("[EMAIL]", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("[IBAN]", re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,3})?\b")),
    ("[PASSWORD]", re.compile(r"(?i)\b(pass(?:word|wort)?|pwd|kennwort)\b\s*[:=]\s*\S+")),
    ("[PHONE]", re.compile(r"(?<!\w)\+?\d[\d /()-]{7,}\d")),
    ("[IP]", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
]


def redact(text: str) -> tuple[str, list[str]]:
    """Returns the redacted text and the kinds of data that were removed."""
    removed: list[str] = []
    for label, pattern in _PATTERNS:
        text, count = pattern.subn(label, text)
        if count:
            removed.append(label.strip("[]").lower())
    return text, removed
