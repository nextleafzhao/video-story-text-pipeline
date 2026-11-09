#!/usr/bin/env python
"""Run vframe jobs from a JSON list.

usage: python -m tools.batch_frames jobs.json

jobs.json format:
    [["video-name.mp4", 348, "band"], ["video-name.mp4", 985, "full"]]
"""

import json
import os
import subprocess
import sys


def main(argv=None):
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    with open(args[0], encoding="utf-8") as handle:
        jobs = json.load(handle)
    failures = 0
    for name, sec, what in jobs:
        result = subprocess.run(
            [sys.executable, "-m", "tools.vframe", name, str(sec), what],
            capture_output=True, text=True,
        )
        text = (result.stdout or result.stderr).strip()
        print(text)
        if result.returncode:
            failures += 1
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())