# Universal Resource Collector

Universal Resource Collector is a cross-platform desktop and command-line tool for collecting public HTML and PDF resources, preserving the originals, converting PDFs to Markdown/JSON, and recording durable job progress.

It is designed for people who want a local, inspectable copy of a website’s resources without losing the relationship between the source page, the downloaded file, and the converted output.

> Current release: **0.1.0 (early release)**

## What it supports

- **Operating systems:** Apple Silicon macOS and Windows x64 (Python source; packaging work is planned with PyInstaller).
- **Interfaces:** PySide6 desktop GUI and a command-line interface.
- **Web resources:** public HTML pages and PDF files.
- **Collection features:** domain allowlists, bounded crawl depth, PDF discovery, retries, `.part` files, SHA-256 hashes, and SQLite job state.
- **Conversion:** PDF to Markdown and structured JSON using `pdfplumber`.
- **Job control:** start, pause, resume, cancel, retry/resume after restart, and per-job progress monitoring.
- **Provenance:** source URL, final URL, source page, link text, section heading, local path, file hash, and validation status.
- **AI auditing:** provider-neutral interfaces are available; AI is optional and is not required to download or convert files.

## Desktop GUI

The GUI accepts a source URL and output folder, then shows each job independently with its stage, progress, completed/failed counts, current resource, and status. Jobs can be selected and controlled without losing the state of other jobs. Screenshots and machine-specific paths are intentionally not included in this public repository.

The current GUI includes:

- Source URL field
- Output-folder field and Browse button
- Start new job
- Pause, resume, and cancel selected job
- Per-job progress bar
- Discovery/download/conversion status
- Current resource URL
- Completion and failure counts
- Live job log

## Install on macOS or Windows

Use a virtual environment. This avoids the PEP 668 error produced by Homebrew and other externally managed Python installations.

```sh
git clone https://github.com/micah-charles/universal-resource-collector.git
cd universal-resource-collector
python3 -m venv .venv
source .venv/bin/activate                 # macOS/Linux
# .venv\Scripts\Activate.ps1             # Windows PowerShell
python -m pip install --upgrade pip
python -m pip install -e ".[desktop]"
```

Launch the GUI:

```sh
resource-collector-gui
```

On Windows, use `python -m venv .venv`, activate `.venv\Scripts\Activate.ps1`, and run the same `python -m pip install -e ".[desktop]"` command.

## Quick CLI example

```sh
resource-collector discover \
  --url https://example.org/resources/ \
  --output ./collections/example-resources \
  --depth 2
```

The collector is site-neutral. An adapter can record useful metadata such as collection, category, document type, source page, and component information where it is available in the source URL or page.

## Output layout

New downloads use readable website paths instead of exposing UUIDs as filenames:

```text
collections/example-resources/
├── collection.db
├── manifest.json
├── raw/
│   └── html/<website-path>/page.html
├── originals/
│   └── example.org/resources/exam-board/
│       └── Sample Paper 1 Question Paper.pdf
└── parsed/
    └── example.org/resources/exam-board/
        └── Sample Paper 1 Question Paper/
            ├── primary.md
            └── primary.json
```

For dynamic links such as `/download?id=123`, the collector uses the visible hyperlink text (for example, `June 2024 Mark Scheme`) when available, while retaining the exact URL and ID in the manifest. SHA-256 remains in SQLite and `manifest.json` for duplicate detection and integrity checks.

## Example collection

### Public document website

```sh
resource-collector discover \
  --url https://example.org/resources/ \
  --output ./collections/exam-resources \
  --depth 2
```

Example resource types include:

- Public PDF documents
- Category and section folders
- Human-readable link names for dynamic downloads
- Multiple years, sessions, papers, and components

### Direct PDF

```sh
resource-collector discover \
  --url https://example.org/documents/sample.pdf \
  --output ./collections/sample-document
```

This produces a readable path similar to:

```text
originals/example.org/documents/sample.pdf
parsed/example.org/documents/sample/primary.md
parsed/example.org/documents/sample/primary.json
```

## Important safety properties

- Originals are preserved and are never overwritten by Markdown conversion.
- Raw HTML is retained for provenance and later reprocessing.
- Downloads use temporary `.part` files and atomic completion.
- Redirects are checked against the allowed domain.
- URLs are passed through Python’s HTTP client; they are not interpolated into shell commands.
- Clean documents can complete without AI credentials.
- Existing hash-based identity is retained even though user-facing paths are readable.

## Development

```sh
python -m unittest discover -s tests -v
python -m compileall -q src
```

The project is currently at version 0.1.0. PyInstaller packaging for native Apple Silicon macOS and Windows x64, broader parser benchmarking, OCR, and production AI-provider adapters are planned follow-up work.

## License and website policies

Only collect public resources that you are permitted to access and preserve. Review the target website’s terms, robots policy, copyright, rate limits, and applicable law before running a large collection. This project does not bypass login, CAPTCHA, paywalls, or access controls.
