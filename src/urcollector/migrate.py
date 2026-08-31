from __future__ import annotations

import json
from pathlib import Path

from .db import Database
from .models import JobConfig, Resource, ResourceStatus


def migrate_legacy(legacy_root: str | Path, output_root: str | Path) -> int:
    legacy=Path(legacy_root); output=Path(output_root); output.mkdir(parents=True,exist_ok=True); manifest=json.loads((legacy/"manifest.json").read_text(encoding="utf-8")); db=Database(output/"collection.db")
    config=JobConfig(str(manifest.get("sourceIndex", "legacy://import")),str(output),manifest.get("allowedDomains",[])); job_id=db.create_job(config); db.update_job(job_id,status="migrating")
    count=0
    for item in manifest.get("documents",[]):
        resource=Resource(item["url"],resource_type="pdf",status=ResourceStatus.DOWNLOADED,metadata={"legacy":True,"category_pages":item.get("categoryPages",[])},final_url=item.get("finalUrl"),sha256=item.get("sha256"),bytes=item.get("bytes"),original_path=str(legacy/item["documentPath"]),markdown_path=str(legacy/item["markdownPath"]) if item.get("markdownPath") else None)
        rid=db.upsert_resource(job_id,resource); db.set_resource(rid,resource.status.value,final_url=resource.final_url,sha256=resource.sha256,bytes=resource.bytes,original_path=resource.original_path,markdown_path=resource.markdown_path); count+=1
    db.update_job(job_id,status="completed",total_resources=count,completed_resources=count); db.export_manifest(job_id,output/"manifest.json"); return job_id
