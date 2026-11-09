#!/usr/bin/env python
"""Deliverable-level scan: watch tokens, short screen text, brackets, ASCII, duplicates."""

import collections
import os
import re
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.common import config, paths, report


def deliverable_path(path=None):
    if path:
        return path
    cfg = config.assemble()
    main = cfg.get("main", {})
    return os.path.join(paths.ROOT, main.get("file", cfg.get("output_file", "transcript.md")))


def run(path=None):
    path = deliverable_path(path)
    issues = []
    if not os.path.exists(path):
        return [{"line": 0, "tag": "MISSING", "text": paths.rel(path)}], {"path": paths.rel(path)}

    lines = [line for line in open(path, encoding="utf-8").read().splitlines()
             if re.match(r"^\[\d+:\d+\]", line)]
    tokens = config.game_profile().get("watch_tokens", [])

    token_hits = {}
    for token in tokens:
        count = sum(line.count(token) for line in lines)
        if count:
            token_hits[token] = count

    for line in lines:
        match = re.match(r"^\[\d+:\d+\] \*\*【画面文字】\*\*(.+)$", line)
        if match:
            body = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", match.group(1))
            if len(body) <= 2:
                issues.append({"line": 0, "tag": "SHORT", "text": line[:80]})

    balanced_failures = 0
    for line in lines:
        body = re.sub(r"^\[\d+:\d+\] ", "", line)
        if body.count("「") != body.count("」") or "]" in body or "］" in body:
            balanced_failures += 1
            issues.append({"line": 0, "tag": "QUOTE", "text": line[:100]})

    for line in lines:
        if "画面文字" in line:
            continue
        body = re.sub(r"^\[\d+:\d+\] \*\*(.+?)\*\*：", "", line)
        if re.search(r"[\u4e00-\u9fff][A-Za-z0-9]|[A-Za-z0-9][\u4e00-\u9fff]", body):
            issues.append({"line": 0, "tag": "ASCII", "text": line[:90]})

    seen = collections.defaultdict(list)
    for line in lines:
        match = re.match(r"^\[(\d+):(\d+)\] (.+)$", line)
        if not match:
            continue
        t = int(match.group(1)) * 60 + int(match.group(2))
        key = re.sub(r"[^\u4e00-\u9fff]", "", match.group(3))
        if len(key) >= 4:
            seen[key].append((t, line))
    for items in seen.values():
        if len(items) > 1 and items[-1][0] - items[0][0] <= 10:
            issues.append({"line": 0, "tag": "DUP10", "text": items[0][1][:80]})

    stats = {"path": paths.rel(path), "lines": len(lines), "issues": len(issues),
             "quote_failures": balanced_failures, "token_hits": token_hits}
    return issues, stats


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    path = args[:1]
    issues, stats = run(path[0] if path else None)
    for issue in issues:
        print(f"{issue['tag']:<12} {issue['text']}")
    result = report.write("status", {"stats": stats, "issues": issues}, ok=not issues)
    report.echo(result)
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())