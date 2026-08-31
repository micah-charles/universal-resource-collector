import json
import tempfile
import unittest
from pathlib import Path

from urcollector.adapters import GenericWebAdapter
from urcollector.naming import preferred_filename, resource_relative_path
from urcollector.db import Database
from urcollector.models import JobConfig, Resource
from urcollector.providers import MockProvider, AuditRequest, validate_audit_result
from urcollector.validate import validate_markdown


class CoreTests(unittest.TestCase):
    def test_adapter_allowlist_and_pdf_detection(self):
        adapter=GenericWebAdapter(["example.com"]); page=adapter.parse("https://example.com/index",b'<title>T</title><a href="/x.pdf">PDF</a><a href="https://evil.test/x.pdf">bad</a>')
        self.assertEqual(page.title,"T"); self.assertEqual(page.links,["https://example.com/x.pdf"]); self.assertTrue(adapter.qualifies_resource(page.links[0]))
        self.assertEqual(page.resource_links[0].text, "PDF")

    def test_human_readable_paths(self):
        self.assertEqual(preferred_filename("https://site.test/download?id=42", "June 2024 Mark Scheme"), "June 2024 Mark Scheme.pdf")
        self.assertEqual(resource_relative_path("https://site.test/papers/aqa/download?id=42", "June 2024 Mark Scheme"), "site.test/papers/aqa/June 2024 Mark Scheme.pdf")

    def test_database_job_and_resource(self):
        with tempfile.TemporaryDirectory() as temp:
            db=Database(Path(temp)/"collection.db"); job=db.create_job(JobConfig("https://example.com",temp,["example.com"])); rid=db.upsert_resource(job,Resource("https://example.com/a.pdf",resource_type="pdf")); db.set_resource(rid,"downloaded",sha256="abc",bytes=10); self.assertEqual(db.resource_rows(job)[0]["sha256"],"abc")

    def test_validation_flags_empty_markdown(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"empty.md"; path.write_text(""); result=validate_markdown(path); self.assertEqual(result.status,"AI_REVIEW_REQUIRED")

    def test_provider_contract(self):
        result=MockProvider().audit(AuditRequest("1","https://example.com",None,None,None,[],[])); validate_audit_result(result); self.assertEqual(result["status"],"pass")


if __name__ == "__main__": unittest.main()
