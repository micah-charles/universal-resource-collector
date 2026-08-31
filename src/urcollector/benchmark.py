from __future__ import annotations

import json
import time
from pathlib import Path

from .convert import convert_pdf
from .validate import validate_markdown


def benchmark_pdf(pdf_path: str | Path, output_root: str | Path) -> dict:
    pdf_path=Path(pdf_path); started=time.perf_counter(); out=Path(output_root)/pdf_path.stem
    try:
        md, structured, pages=convert_pdf(pdf_path,pdf_path.as_uri(),out); validation=validate_markdown(md,pages); status="ok"
    except Exception as exc:
        md=structured=None; pages=0; validation=None; status=f"error: {type(exc).__name__}: {exc}"
    result={"pdf":str(pdf_path),"status":status,"pages":pages,"seconds":round(time.perf_counter()-started,3),"markdown":str(md) if md else None,"structured_json":str(structured) if structured else None,"validation":validation.__dict__ if validation and hasattr(validation,"__dict__") else ({"status":validation.status,"score":validation.score,"findings":validation.findings} if validation else None)}
    Path(output_root).mkdir(parents=True,exist_ok=True); (Path(output_root)/"benchmark.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8"); return result
