#!/usr/bin/env python
"""Assemble the non-story supplement from config/assemble.json -> supplement."""

import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.build.assemble import assemble
from src.common import config, paths, report


def run_supplement(argv=None):
    cfg = config.assemble().get("supplement", {})
    if not cfg.get("enabled"):
        print("supplement disabled")
        return 0
    keys = list(cfg.get("keys") or [])
    out, stats = assemble(keys, [], cfg["title"], cfg["file"], section_prefix="补录：")
    print("wrote", paths.rel(out), stats["count"], "segments")
    if stats["missing"]:
        print("MISSING", ", ".join(stats["missing"]))
    report.write("assemble_supplement", {"output": paths.rel(out), **stats}, ok=not stats["missing"])
    return 0 if not stats["missing"] else 1


def main(argv=None):
    return run_supplement(argv)


if __name__ == "__main__":
    raise SystemExit(main())