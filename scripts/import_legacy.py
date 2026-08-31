#!/usr/bin/env python3
import argparse
from urcollector.migrate import migrate_legacy

parser=argparse.ArgumentParser(); parser.add_argument("--legacy",required=True); parser.add_argument("--output",required=True); args=parser.parse_args(); print(f"Imported job {migrate_legacy(args.legacy,args.output)}")
