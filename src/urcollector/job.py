from __future__ import annotations

import hashlib
import threading
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .adapters import GenericWebAdapter, ResourceLink
from .convert import convert_pdf
from .db import Database, utcnow
from .download import DownloadManager
from .models import JobConfig, Resource, ResourceStatus
from .naming import preferred_filename, resource_relative_path, url_relative_path
from .validate import validate_markdown


class JobController:
    """Durable single-worker job controller used by the CLI and UI."""
    def __init__(self, db: Database, config: JobConfig, adapter: GenericWebAdapter | None = None):
        self.db=db; self.config=config; self.adapter=adapter or GenericWebAdapter(config.allowed_domains)
        self.downloader=DownloadManager(config.output_root,config.delay_seconds,config.max_retries)
        self.pause_event=threading.Event(); self.cancel_event=threading.Event(); self.job_id=db.create_job(config); self._thread=None
    def start(self):
        if not self._thread or not self._thread.is_alive(): self._thread=threading.Thread(target=self.run,daemon=True); self._thread.start()
    def pause(self): self.pause_event.set(); self.db.update_job(self.job_id,status="paused")
    def resume(self): self.pause_event.clear(); self.db.update_job(self.job_id,status="running")
    def cancel(self): self.cancel_event.set(); self.pause_event.clear(); self.db.update_job(self.job_id,status="cancelled")
    def wait(self,timeout=None):
        if self._thread: self._thread.join(timeout)
    def _wait(self):
        while self.pause_event.is_set() and not self.cancel_event.is_set(): time.sleep(.1)
        if self.cancel_event.is_set(): raise RuntimeError("cancelled")
    def fetch_page(self,url):
        with urlopen(Request(url,headers={"User-Agent":"universal-resource-collector/0.1"}),timeout=90) as response: return response.geturl(),response.read(),response.status
    def _direct_pdf_resource(self):
        url=self.config.source_url; name=preferred_filename(url)
        return self.db.upsert_resource(self.job_id,Resource(url,source_page_url=None,title=name,resource_type="pdf",display_name=name,relative_path=resource_relative_path(url),metadata={"direct_input":True}))
    def run(self):
        self.db.update_job(self.job_id,status="discovering",started_at=utcnow())
        try:
            resource_ids=set()
            if self.adapter.qualifies_resource(self.config.source_url):
                resource_ids.add(self._direct_pdf_resource())
            else:
                queue=[(self.config.source_url,None,0)]; visited=set()
                while queue:
                    self._wait(); url,parent,depth=queue.pop(0)
                    if url in visited or depth>self.config.max_depth: continue
                    visited.add(url); final,body,status=self.fetch_page(url); parsed=self.adapter.parse(url,body,final); digest=hashlib.sha256(body).hexdigest(); page_path=url_relative_path(final or url); raw_dir=page_path.parent if page_path.suffix else page_path; raw=Path(self.config.output_root)/"raw"/"html"/raw_dir/"page.html"; raw.parent.mkdir(parents=True,exist_ok=True)
                    if not raw.exists(): raw.write_bytes(body)
                    page_id=self.db.upsert_page(self.job_id,url,final_url=final,parent_url=parent,raw_path=str(raw),content_hash=digest,http_status=status,status="fetched",fetched_at=utcnow())
                    if depth<self.config.max_depth:
                        for link in parsed.links:
                            if link not in visited and not self.adapter.qualifies_resource(link): queue.append((link,url,depth+1))
                    resource_links = parsed.resource_links or [ResourceLink(link, "", "") for link in parsed.links]
                    for item in resource_links:
                        if self.adapter.qualifies_resource(item.url):
                            name=preferred_filename(item.url,item.text); rel=resource_relative_path(item.url,item.text)
                            metadata={"source_page":url,"source_section":item.section,"link_text":item.text}
                            resource_ids.add(self.db.upsert_resource(self.job_id,Resource(item.url,source_page_url=url,resource_type="pdf",title=name,display_name=name,relative_path=rel,source_link_text=item.text,source_section=item.section,metadata=metadata),page_id))
                    time.sleep(self.config.delay_seconds)
            self.db.update_job(self.job_id,total_resources=len(resource_ids),status="downloading")
            for row in self.db.resource_rows(self.job_id): self._wait(); self.process_resource(row)
            self.db.update_job(self.job_id,status="completed",completed_at=utcnow())
        except Exception:
            if not self.cancel_event.is_set(): self.db.update_job(self.job_id,status="failed",completed_at=utcnow())
    def process_resource(self,row):
        rid=row["id"]; url=row["url"]; root=Path(self.config.output_root); self.db.set_resource(rid,ResourceStatus.DOWNLOADING.value)
        try:
            result=self.downloader.fetch(url,subdir="originals",stop=self.cancel_event.is_set); source=result.path
            rel=row["relative_path"] or str(url_relative_path(url)); original=root/"originals"/rel
            if original.suffix.lower() != ".pdf": original=original.with_suffix(".pdf")
            original.parent.mkdir(parents=True,exist_ok=True)
            if original.exists():
                if hashlib.sha256(original.read_bytes()).hexdigest() == result.sha256: source.unlink(missing_ok=True)
                else:
                    original=original.with_name(f"{original.stem}__{result.sha256[:10]}{original.suffix}")
                    original.parent.mkdir(parents=True,exist_ok=True); source.rename(original)
            else: source.rename(original)
            self.db.set_resource(rid,ResourceStatus.DOWNLOADED.value,final_url=result.final_url,sha256=result.sha256,bytes=result.bytes,original_path=str(original),downloaded_at=utcnow())
            out=root/"parsed"/Path(rel).with_suffix(""); self.db.set_resource(rid,ResourceStatus.CONVERTING.value); md,structured,pages=convert_pdf(original,url,out); self.db.set_resource(rid,ResourceStatus.VALIDATING.value); validation=validate_markdown(md,pages)
            final_status=ResourceStatus.PASSED.value if validation.status=="PASS" else ResourceStatus.WARNING.value; self.db.set_resource(rid,final_status,markdown_path=str(md)); self.db.update_job(self.job_id,completed_resources=self.db.conn.execute("SELECT COUNT(*) FROM resources WHERE job_id=? AND status IN (?,?)",(self.job_id,ResourceStatus.PASSED.value,ResourceStatus.WARNING.value)).fetchone()[0]); self.db.record_attempt(rid,"download_convert",1,"completed")
        except Exception as exc:
            self.db.set_resource(rid,ResourceStatus.FAILED.value); self.db.update_job(self.job_id,failed_resources=self.db.conn.execute("SELECT COUNT(*) FROM resources WHERE job_id=? AND status=\"failed\"",(self.job_id,)).fetchone()[0]); self.db.record_attempt(rid,"download_convert",1,"failed",type(exc).__name__,str(exc))
