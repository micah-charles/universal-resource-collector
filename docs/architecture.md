# Architecture

The application is deliberately split into deterministic and optional layers.

```text
PySide6 UI (optional)
       |
JobController + SQLite
       |
SiteAdapter -> discovery -> durable download
       |
HTML/PDF conversion -> structured JSON + Markdown
       |
deterministic validation -> fallback/OCR -> optional AuditProvider
```

The current implementation provides the standard-library core, `pdfplumber`
conversion, site adapter, SQLite schema, legacy import, and a minimal
PySide6 UI. Docling, OCR, browser rendering, and named external agents remain
optional adapters until their platform/licence benchmarks are completed.

## Provider safety

Providers receive JSON over stdin or an adapter API and must return validated JSON.
They never receive permission to overwrite originals. Cloud providers must be
explicitly approved by the caller before a future UI integration sends content.
