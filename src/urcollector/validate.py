from __future__ import annotations

import re
from pathlib import Path

from .models import ValidationResult


def validate_pdf(path: str | Path, text: str | None = None, page_count: int | None = None) -> ValidationResult:
    path = Path(path); findings = []; score = 1.0
    raw = path.read_bytes() if path.exists() else b""
    if not raw.startswith(b"%PDF-"):
        findings.append({"type": "invalid_signature", "severity": "high"}); score -= .6
    if not raw or len(raw) < 256:
        findings.append({"type": "suspicious_size", "severity": "high"}); score -= .3
    if text is not None:
        if not text.strip(): findings.append({"type": "empty_text", "severity": "high"}); score -= .5
        if text.count("�") > max(10, len(text) // 500): findings.append({"type": "replacement_characters", "severity": "medium"}); score -= .15
        if re.search(r"(.)\1{80,}", text): findings.append({"type": "repeated_garbage", "severity": "medium"}); score -= .15
    if page_count == 0: findings.append({"type": "zero_pages", "severity": "high"}); score -= .5
    score = max(0.0, min(1.0, score))
    status = "PASS" if not findings else "PASS_WITH_WARNINGS" if score >= .75 else "REPARSE" if score >= .4 else "UNRECOVERABLE"
    return ValidationResult(status, score, findings)


def validate_markdown(path: str | Path, expected_pages: int | None = None) -> ValidationResult:
    path = Path(path); text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""; findings = []; score = 1.0
    if not text.strip(): findings.append({"type": "empty_markdown", "severity": "high"}); score -= .7
    if len(text) < max(100, (expected_pages or 1) * 20): findings.append({"type": "low_text_density", "severity": "medium"}); score -= .25
    if text.count("�") > max(10, len(text) // 500): findings.append({"type": "replacement_characters", "severity": "medium"}); score -= .15
    score = max(0.0, score); status = "PASS" if not findings else "PASS_WITH_WARNINGS" if score >= .75 else "AI_REVIEW_REQUIRED"
    return ValidationResult(status, score, findings)
