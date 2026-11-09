#!/usr/bin/env python
"""Deliverable re-check: broken characters, brackets, bare ellipsis, watch phrases."""

import os
import re
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.common import config, paths, report
from src.checks.status import deliverable_path


def _body(line):
    text = re.sub(r"^\[\d+:\d+\] ", "", line)
    if text.startswith("**【画面文字】**"):
        return text[len("**【画面文字】**"):]
    match = re.match(r"^\*\*(.+?)\*\*：(.+)$", text)
    return match.group(2) if match else text


def run(path=None):
    path = deliverable_path(path)
    issues = []
    if not os.path.exists(path):
        return [{"tag": "MISSING", "text": paths.rel(path)}], {"path": paths.rel(path)}
    text = open(path, encoding="utf-8").read()
    lines = [line for line in text.splitlines() if re.match(r"^\[\d+:\d+\]", line)]

    for line in lines:
        if "画面文字" in line:
            continue
        body = _body(line)
        if re.search(r"[\u4e00-\u9fff][A-Za-z0-9]|[A-Za-z0-9][\u4e00-\u9fff]", body):
            issues.append({"tag": "ASCII", "text": line[:90]})

    for line in lines:
        body = _body(line)
        if body.count("「") != body.count("」") or "]" in body or "］" in body:
            issues.append({"tag": "QUOTE", "text": line[:90]})

    for line in lines:
        if re.search(r"：……$", line):
            issues.append({"tag": "ELLIPSIS", "text": line})

    watch_hits = []
    for phrase in config.game_profile().get("watch_phrases", []):
        for line in lines:
            if phrase in line:
                watch_hits.append(line[:90])

    return issues, {"path": paths.rel(path), "lines": len(lines), "issues": len(issues),
                    "watch_hits": watch_hits}


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    path = args[:1]
    issues, stats = run(path[0] if path else None)
    for issue in issues:
        print(f"{issue['tag']:<10} {issue['text']}")
    result = report.write("recheck", {"stats": stats, "issues": issues}, ok=not issues)
    report.echo(result)
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())