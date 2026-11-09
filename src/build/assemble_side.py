#!/usr/bin/env python
"""Assemble the side-quest deliverable from config/assemble.json -> side."""

import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.build.assemble import assemble
from src.common import config, paths, report


def run_side(argv=None):
    cfg = config.assemble().get("side", {})
    if not cfg.get("enabled"):
        print("side disabled")
        return 0
    keys = list(cfg.get("keys") or [])
    if not keys and cfg.get("keys_from"):
        keys = [row[0] for row in config.videos() if row[0] >= cfg["keys_from"]]
    arcs = cfg.get("arcs") or ([[cfg.get("title", "支线"), keys]] if keys else [])
    out, stats = assemble(keys, arcs, cfg["title"], cfg["file"])
    print("wrote", paths.rel(out), stats["count"], "segments")
    if stats["missing"]:
        print("MISSING", ", ".join(stats["missing"]))
    report.write("assemble_side", {"output": paths.rel(out), **stats}, ok=not stats["missing"])
    return 0 if not stats["missing"] else 1


def main(argv=None):
    return run_side(argv)


if __name__ == "__main__":
    raise SystemExit(main())