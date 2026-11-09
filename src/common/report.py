"""Machine-readable run reports.

Every command writes ``work/reports/<step>.json`` and returns a process exit
code.  Agents use the JSON to decide whether a step succeeded; humans get a
short summary on stdout.
"""

import json
import time

from .paths import ensure_work, rel


def write(step, payload=None, ok=True):
    """Write a report and return its path."""
    directory = ensure_work("reports")
    path = f"{directory}/{step}.json"
    data = {
        "step": step,
        "ok": bool(ok),
        "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    data.update(payload or {})
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return path


def ok(step, **extra):
    return write(step, extra, ok=True)


def fail(step, message, **extra):
    return write(step, {"error": message, **extra}, ok=False)


def echo(result_path):
    print(f"report: {rel(result_path)}")