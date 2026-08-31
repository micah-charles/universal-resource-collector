from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import JobConfig, Resource, ResourceStatus


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY, source_url TEXT NOT NULL, output_root TEXT NOT NULL,
  status TEXT NOT NULL, config_json TEXT NOT NULL, created_at TEXT NOT NULL,
  started_at TEXT, completed_at TEXT, total_resources INTEGER DEFAULT 0,
  completed_resources INTEGER DEFAULT 0, failed_resources INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS source_pages (
  id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL REFERENCES jobs(id), url TEXT NOT NULL,
  final_url TEXT, parent_url TEXT, raw_path TEXT, content_hash TEXT, status TEXT NOT NULL,
  http_status INTEGER, fetched_at TEXT, UNIQUE(job_id,url)
);
CREATE TABLE IF NOT EXISTS resources (
  id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL REFERENCES jobs(id), url TEXT NOT NULL,
  final_url TEXT, source_page_id INTEGER REFERENCES source_pages(id), resource_type TEXT,
  title TEXT, metadata_json TEXT NOT NULL DEFAULT '{}', status TEXT NOT NULL,
  sha256 TEXT, bytes INTEGER, original_path TEXT, markdown_path TEXT,
  display_name TEXT, relative_path TEXT, source_link_text TEXT, source_section TEXT,
  discovered_at TEXT NOT NULL, downloaded_at TEXT, UNIQUE(job_id,url)
);
CREATE TABLE IF NOT EXISTS attempts (
  id INTEGER PRIMARY KEY, resource_id INTEGER NOT NULL REFERENCES resources(id),
  stage TEXT NOT NULL, attempt_no INTEGER NOT NULL, started_at TEXT NOT NULL,
  completed_at TEXT, status TEXT NOT NULL, error_type TEXT, error_message TEXT
);
CREATE TABLE IF NOT EXISTS conversions (
  id INTEGER PRIMARY KEY, resource_id INTEGER NOT NULL REFERENCES resources(id),
  engine TEXT NOT NULL, engine_version TEXT, config_json TEXT NOT NULL DEFAULT '{}',
  markdown_path TEXT, structured_json_path TEXT, image_dir TEXT, status TEXT NOT NULL,
  quality_score REAL, started_at TEXT NOT NULL, completed_at TEXT
);
CREATE TABLE IF NOT EXISTS page_metrics (
  id INTEGER PRIMARY KEY, conversion_id INTEGER NOT NULL REFERENCES conversions(id),
  page_number INTEGER NOT NULL, char_count INTEGER, word_count INTEGER, block_count INTEGER,
  image_count INTEGER, table_count INTEGER, formula_count INTEGER, ocr_used INTEGER,
  warnings_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS validations (
  id INTEGER PRIMARY KEY, conversion_id INTEGER NOT NULL REFERENCES conversions(id),
  validator_version TEXT NOT NULL, score REAL NOT NULL, status TEXT NOT NULL,
  findings_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audits (
  id INTEGER PRIMARY KEY, conversion_id INTEGER NOT NULL REFERENCES conversions(id),
  provider TEXT NOT NULL, model TEXT, prompt_version TEXT, status TEXT NOT NULL,
  findings_json TEXT NOT NULL, started_at TEXT NOT NULL, completed_at TEXT
);
CREATE TABLE IF NOT EXISTS repairs (
  id INTEGER PRIMARY KEY, resource_id INTEGER NOT NULL REFERENCES resources(id),
  source_conversion_id INTEGER, output_conversion_id INTEGER, method TEXT NOT NULL,
  pages_json TEXT NOT NULL, reason TEXT NOT NULL, approved INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        existing = {row[1] for row in self.conn.execute("PRAGMA table_info(resources)")}
        for column in ("display_name", "relative_path", "source_link_text", "source_section"):
            if column not in existing: self.conn.execute(f"ALTER TABLE resources ADD COLUMN {column} TEXT")
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def create_job(self, config: JobConfig) -> int:
        with self._lock, self.conn:
            cur = self.conn.execute(
                "INSERT INTO jobs(source_url,output_root,status,config_json,created_at) VALUES(?,?,?,?,?)",
                (config.source_url, config.output_root, "created", json.dumps(asdict(config)), utcnow()),
            )
            return int(cur.lastrowid)

    def update_job(self, job_id: int, **values: Any) -> None:
        if not values:
            return
        values["updated_at"] = utcnow()
        # updated_at is intentionally not a schema column; omit it from SQL while
        # retaining the timestamp in application logs where needed.
        values.pop("updated_at", None)
        columns = ", ".join(f"{key}=?" for key in values)
        with self._lock, self.conn:
            self.conn.execute(f"UPDATE jobs SET {columns} WHERE id=?", (*values.values(), job_id))

    def upsert_page(self, job_id: int, url: str, **values: Any) -> int:
        row = self.conn.execute("SELECT id FROM source_pages WHERE job_id=? AND url=?", (job_id, url)).fetchone()
        if row:
            if values:
                cols = ", ".join(f"{k}=?" for k in values)
                with self._lock, self.conn:
                    self.conn.execute(f"UPDATE source_pages SET {cols} WHERE id=?", (*values.values(), row["id"]))
            return int(row["id"])
        data = {"final_url": None, "parent_url": None, "raw_path": None, "content_hash": None, "status": "fetched", "http_status": None, "fetched_at": utcnow(), **values}
        with self._lock, self.conn:
            cur = self.conn.execute("INSERT INTO source_pages(job_id,url,final_url,parent_url,raw_path,content_hash,status,http_status,fetched_at) VALUES(?,?,?,?,?,?,?,?,?)", (job_id, url, data["final_url"], data["parent_url"], data["raw_path"], data["content_hash"], data["status"], data["http_status"], data["fetched_at"]))
            return int(cur.lastrowid)

    def upsert_resource(self, job_id: int, resource: Resource, source_page_id: int | None = None) -> int:
        row = self.conn.execute("SELECT id FROM resources WHERE job_id=? AND url=?", (job_id, resource.url)).fetchone()
        metadata = json.dumps(resource.metadata, ensure_ascii=False)
        if row:
            with self._lock, self.conn:
                self.conn.execute("UPDATE resources SET source_page_id=?,title=?,metadata_json=?,resource_type=?,display_name=?,relative_path=?,source_link_text=?,source_section=? WHERE id=?", (source_page_id, resource.title, metadata, resource.resource_type, resource.display_name, resource.relative_path, resource.source_link_text, resource.source_section, row["id"]))
            return int(row["id"])
        with self._lock, self.conn:
            cur = self.conn.execute("INSERT INTO resources(job_id,url,source_page_id,resource_type,title,metadata_json,status,display_name,relative_path,source_link_text,source_section,discovered_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (job_id, resource.url, source_page_id, resource.resource_type, resource.title, metadata, resource.status.value, resource.display_name, resource.relative_path, resource.source_link_text, resource.source_section, utcnow()))
            return int(cur.lastrowid)

    def set_resource(self, resource_id: int, status: str, **values: Any) -> None:
        values = {"status": status, **values}
        cols = ", ".join(f"{k}=?" for k in values)
        with self._lock, self.conn:
            self.conn.execute(f"UPDATE resources SET {cols} WHERE id=?", (*values.values(), resource_id))

    def resource_rows(self, job_id: int) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM resources WHERE job_id=? ORDER BY id", (job_id,)))

    def record_attempt(self, resource_id: int, stage: str, attempt_no: int, status: str, error_type: str | None = None, error_message: str | None = None) -> None:
        with self._lock, self.conn:
            self.conn.execute("INSERT INTO attempts(resource_id,stage,attempt_no,started_at,completed_at,status,error_type,error_message) VALUES(?,?,?,?,?,?,?,?)", (resource_id, stage, attempt_no, utcnow(), utcnow(), status, error_type, error_message))

    def export_manifest(self, job_id: int, target: str | Path) -> None:
        job = dict(self.conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())
        pages = [dict(row) for row in self.conn.execute("SELECT * FROM source_pages WHERE job_id=?", (job_id,))]
        resources = []
        for row in self.conn.execute("SELECT * FROM resources WHERE job_id=?", (job_id,)):
            item = dict(row); item["metadata"] = json.loads(item.pop("metadata_json")); resources.append(item)
        Path(target).write_text(json.dumps({"job": job, "pages": pages, "resources": resources}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
