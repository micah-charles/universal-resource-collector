from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class AuditRequest:
    resource_id: str
    source_url: str
    original_path: str | None
    markdown_path: str | None
    structured_json_path: str | None
    suspect_pages: list[int]
    deterministic_findings: list[dict[str, Any]]
    requested_task: str = "audit"


class AuditProvider:
    name = "base"
    def audit(self, request: AuditRequest) -> dict[str, Any]: raise NotImplementedError


class NoneProvider(AuditProvider):
    name = "none"
    def audit(self, request): return {"status": "pass", "confidence": 1.0, "issues": [], "recommended_action": {"action": "none", "pages": [], "preferred_parser": None}}


class MockProvider(AuditProvider):
    name = "mock"
    def audit(self, request): return {"status": "warning" if request.deterministic_findings else "pass", "confidence": .5, "issues": request.deterministic_findings, "recommended_action": {"action": "inspect_original" if request.deterministic_findings else "none", "pages": request.suspect_pages, "preferred_parser": None}}


class CustomCommandProvider(AuditProvider):
    name = "custom_command"
    def __init__(self, argv: list[str], timeout: int = 300): self.argv = argv; self.timeout = timeout
    def audit(self, request):
        payload = json.dumps(asdict(request), ensure_ascii=False)
        result = subprocess.run(self.argv, input=payload, text=True, capture_output=True, timeout=self.timeout, check=False)
        if result.returncode: raise RuntimeError(result.stderr.strip() or f"provider exited {result.returncode}")
        output = json.loads(result.stdout); validate_audit_result(output); return output


def validate_audit_result(value: dict[str, Any]) -> None:
    if value.get("status") not in {"pass", "warning", "repair_required", "human_review"}: raise ValueError("invalid audit status")
    if not isinstance(value.get("confidence"), (int, float)) or not 0 <= value["confidence"] <= 1: raise ValueError("invalid confidence")
    if not isinstance(value.get("issues"), list): raise ValueError("issues must be a list")
    action = value.get("recommended_action", {}).get("action")
    if action not in {"none", "reparse", "ocr", "inspect_original", "human_review"}: raise ValueError("invalid recommended action")
