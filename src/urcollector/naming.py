from __future__ import annotations

import re
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse


def sanitize_component(value: str, fallback: str = "resource") -> str:
    value = unquote(value or "").strip()
    value = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "-", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return value[:180] or fallback


def url_relative_path(url: str, default_name: str = "resource") -> PurePosixPath:
    parsed = urlparse(url)
    host = sanitize_component(parsed.hostname or "unknown-site", "unknown-site")
    parts = [sanitize_component(part) for part in parsed.path.split("/") if part]
    return PurePosixPath(host, *(parts or [default_name]))


def preferred_filename(url: str, anchor_text: str | None = None, extension: str = ".pdf") -> str:
    text = sanitize_component(anchor_text or "", "")
    if text and text.lower() not in {"download", "pdf", "view", "click here"}:
        return text if text.lower().endswith(extension.lower()) else text + extension
    name = sanitize_component(urlparse(url).path.rsplit("/", 1)[-1], "resource")
    return name if "." in name else name + extension


def resource_relative_path(url: str, anchor_text: str | None = None, extension: str = ".pdf") -> str:
    base = url_relative_path(url)
    return str(base.parent / preferred_filename(url, anchor_text, extension)).replace("\\", "/")
