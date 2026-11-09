#!/usr/bin/env python
"""Assemble the main story deliverable from config/assemble.json -> main."""

import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.build.assemble import run_main


def main(argv=None):
    return run_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())