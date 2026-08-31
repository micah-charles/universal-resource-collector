from __future__ import annotations

import argparse
from pathlib import Path

from .adapters import GenericWebAdapter
from .db import Database
from .job import JobController
from .migrate import migrate_legacy
from .models import JobConfig


def main():
    parser=argparse.ArgumentParser(prog="resource-collector"); sub=parser.add_subparsers(dest="command",required=True)
    discover=sub.add_parser("discover"); discover.add_argument("--url",required=True); discover.add_argument("--output",required=True); discover.add_argument("--domain",action="append"); discover.add_argument("--depth",type=int,default=1); discover.add_argument("--delay",type=float,default=.35)
    migrate=sub.add_parser("migrate"); migrate.add_argument("--legacy",required=True); migrate.add_argument("--output",required=True)
    args=parser.parse_args()
    if args.command=="migrate": print(f"Imported job {migrate_legacy(args.legacy,args.output)}"); return
    domains=args.domain or [__import__("urllib.parse",fromlist=["urlparse"]).urlparse(args.url).hostname]
    config=JobConfig(args.url,args.output,domains,args.depth,args.delay); db=Database(Path(args.output)/"collection.db"); controller=JobController(db,config,GenericWebAdapter(domains)); controller.start(); controller.wait(); db.export_manifest(controller.job_id,Path(args.output)/"manifest.json"); print(f"Job {controller.job_id} finished")
