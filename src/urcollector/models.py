from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ResourceStatus(StrEnum):
    DISCOVERED = "discovered"
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    CONVERTING = "converting"
    CONVERTED = "converted"
    VALIDATING = "validating"
    PASSED = "passed"
    WARNING = "warning"
    FALLBACK_REQUIRED = "fallback_required"
    AUDITING = "auditing"
    HUMAN_REVIEW = "human_review"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class Resource:
    url: str
    source_page_url: str | None = None
    title: str | None = None
    resource_type: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)
    id: int | None = None
    status: ResourceStatus = ResourceStatus.DISCOVERED
    final_url: str | None = None
    sha256: str | None = None
    bytes: int | None = None
    original_path: str | None = None
    markdown_path: str | None = None
    display_name: str | None = None
    relative_path: str | None = None
    source_link_text: str | None = None
    source_section: str | None = None


@dataclass(slots=True)
class ValidationResult:
    status: str
    score: float
    findings: list[dict[str, Any]] = field(default_factory=list)
    page_metrics: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class JobConfig:
    source_url: str
    output_root: str
    allowed_domains: list[str] = field(default_factory=list)
    max_depth: int = 1
    delay_seconds: float = 0.35
    max_retries: int = 3
    download_pdfs: bool = True
    convert_documents: bool = True
    audit_policy: str = "suspicious_only"
