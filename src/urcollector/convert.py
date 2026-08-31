from __future__ import annotations

import json
from pathlib import Path
from typing import Callable


class ConversionError(RuntimeError): pass


def convert_html(body: bytes, source_url: str, output_dir: str | Path) -> tuple[Path, Path]:
    from html.parser import HTMLParser
    class Text(HTMLParser):
        def __init__(self): super().__init__(); self.parts=[]
        def handle_data(self, data):
            if data.strip(): self.parts.append(" ".join(data.split()))
    parser=Text(); parser.feed(body.decode("utf-8",errors="replace")); text="\n\n".join(parser.parts)
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True); md=out/"primary.md"; structured=out/"primary.json"
    md.write_text(f"<!-- Source: {source_url} -->\n\n{text}\n",encoding="utf-8")
    structured.write_text(json.dumps({"source_url":source_url,"type":"html","text":text},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return md, structured


def convert_pdf(pdf_path: str | Path, source_url: str, output_dir: str | Path, progress: Callable[[int,int],None] | None = None) -> tuple[Path, Path, int]:
    try: import pdfplumber
    except ImportError as exc: raise ConversionError("Install pdfplumber to convert PDFs") from exc
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True); md=out/"primary.md"; structured=out/"primary.json"; pages=[]
    try:
        with pdfplumber.open(pdf_path) as doc:
            total=len(doc.pages)
            for index,page in enumerate(doc.pages,1):
                text=page.extract_text() or ""
                pages.append({"page":index,"text":text,"char_count":len(text),"word_count":len(text.split()),"block_count":len(page.extract_words()),"image_count":len(page.images),"table_count":0,"formula_count":0,"ocr_used":False})
                if progress: progress(index,total)
    except Exception as exc: raise ConversionError(str(exc)) from exc
    text="\n\n".join(page["text"] for page in pages)
    md.write_text(f"<!-- Source: {source_url} -->\n\n{text}\n",encoding="utf-8")
    structured.write_text(json.dumps({"source_url":source_url,"type":"pdf","page_count":len(pages),"pages":pages},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return md,structured,len(pages)
