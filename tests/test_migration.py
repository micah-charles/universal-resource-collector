import json
import tempfile
import unittest
from pathlib import Path

from urcollector.migrate import migrate_legacy


class MigrationTests(unittest.TestCase):
    def test_imports_legacy_manifest_without_network(self):
        with tempfile.TemporaryDirectory() as temp:
            legacy=Path(temp)/"legacy"; out=Path(temp)/"new"; legacy.mkdir(); (legacy/"documents").mkdir(); (legacy/"markdown").mkdir()
            pdf=legacy/"documents"/"abc.pdf"; pdf.write_bytes(b"%PDF-1.4 test"); md=legacy/"markdown"/"abc.md"; md.write_text("text")
            (legacy/"manifest.json").write_text(json.dumps({"sourceIndex":"https://example.com","allowedDomains":["example.com"],"documents":[{"url":"https://example.com/a.pdf","sha256":"abc","bytes":12,"documentPath":"documents/abc.pdf","markdownPath":"markdown/abc.md"}]}))
            job=migrate_legacy(legacy,out); self.assertGreater(job,0); manifest=json.loads((out/"manifest.json").read_text()); self.assertEqual(len(manifest["resources"]),1)


if __name__ == "__main__": unittest.main()
