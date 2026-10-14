"""
security.py
===========
Security controls for MortgageGuard AI:
- File validation & path traversal defense
- Prompt injection detection and input sanitization
- Role-Based Access Control (RBAC) helpers
- Secret masking for logs
"""

import os
import re
from pathlib import Path
from typing import List, Tuple
from fastapi import HTTPException, status

# Prompt injection heuristic triggers
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(?:all\s+)?rules", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.IGNORECASE),
    re.compile(r"system\s*prompt\s*:", re.IGNORECASE),
    re.compile(r"override\s+compliance\s+status", re.IGNORECASE),
    re.compile(r"pretend\s+to\s+be", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
]


def validate_safe_filename(filename: str) -> str:
    """Protects against path traversal and malicious filenames."""
    clean_name = os.path.basename(filename).strip()
    clean_name = re.sub(r"[^\w\.\-\s]", "_", clean_name)
    if not clean_name or clean_name.startswith("..") or clean_name.startswith("/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename: path traversal characters detected",
        )
    return clean_name


def sanitize_untrusted_text(text: str) -> Tuple[str, bool]:
    """
    Scans untrusted extracted document text for prompt injection attempts.
    Returns (sanitized_text, has_injection_warning).
    """
    has_warning = False
    warning_tags = []

    for pat in INJECTION_PATTERNS:
        if pat.search(text):
            has_warning = True
            warning_tags.append(pat.pattern)
            # Neutralize the trigger
            text = pat.sub("[FLAGGED_INJECTION_ATTEMPT_REDACTED]", text)

    return text, has_warning


def mask_sensitive_data(text: str) -> str:
    """Masks SSNs, PANs, and sensitive account identifiers from logs."""
    # US SSN: XXX-XX-XXXX
    text = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "XXX-XX-XXXX", text)
    # Indian PAN: [A-Z]{5}[0-9]{4}[A-Z]{1}
    text = re.sub(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", "XXXXX0000X", text)
    # Credit Card numbers: 16 digits
    text = re.sub(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "XXXX-XXXX-XXXX-XXXX", text)
    return text
