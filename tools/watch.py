#!/usr/bin/env python
"""Watch work/driver.log and align each segment as soon as its OCR finishes.

usage: python -m tools.watch
"""

import json
import os
import re
import sys
import time

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.align import align
from src.common import paths

LOG = paths.work("driver.log")
STATE = paths.work("align", "watch_state.json")
LOGFILE = paths.work("watch.log")


def log(message):
    line = f"[{time.strftime('%H:%M:%S')}] {message}"
    print(line, flush=True)
    with open(LOGFILE, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")


def done_keys():
    if not os.path.exists(LOG):
        return set()
    current, finished = None, set()
    for line in open(LOG, encoding="utf-8"):
        match = re.match(r"\[\d\d:\d\d:\d\d\] OCR (\S+)", line)
        if match:
            current = match.group(1)
            continue
        if current and "ocr done in" in line:
            finished.add(current)
            current = None
    return finished


def main(argv=None):
    paths.ensure_work("align")
    state = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {}
    while True:
        for key in done_keys():
            if state.get(key) == "ok":
                continue
            if not os.path.exists(paths.work("ocr", key + ".jsonl")):
                continue
            log(f"ALIGN {key}")
            try:
                align.main([key])
                state[key] = "ok"
                log(f"  aligned {key}")
            except Exception as exc:
                state[key] = "err"
                log(f"  FAIL {key}: {exc}")
            with open(STATE, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(state, handle, ensure_ascii=False)
        if os.path.exists(LOG):
            tail = [line for line in open(LOG, encoding="utf-8").read().splitlines() if line.strip()]
            if tail and tail[-1].endswith("ALL DONE"):
                log("DRIVER DONE, watcher exit")
                return 0
        time.sleep(30)


if __name__ == "__main__":
    raise SystemExit(main())