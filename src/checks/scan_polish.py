#!/usr/bin/env python
"""Per-segment polish scan: brackets, ASCII, symbols, short screen text, near duplicates."""

import glob
import os
import re
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.common import paths, report

LINE = re.compile(r"^\[(\d+):(\d+)\] (.+)$")


def _tsec(match):
    return int(match.group(1)) * 60 + int(match.group(2))


def norm(text):
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", text)


def _txt_dir(directory=None):
    if directory:
        return directory
    final = paths.work("txt", "final")
    if os.path.isdir(final) and glob.glob(os.path.join(final, "*.txt")):
        return final
    return paths.work("txt", "draft")


def run(keys=None, directory=None):
    directory = _txt_dir(directory)
    issues, reports = [], []
    for path in sorted(glob.glob(os.path.join(directory, "*.txt"))):
        key = os.path.basename(path)[:6]
        if keys and key not in keys:
            continue
        lines = open(path, encoding="utf-8").read().splitlines()
        found = []
        items = []
        for index, line in enumerate(lines):
            match = LINE.match(line)
            if not match:
                continue
            t, rest = _tsec(match), match.group(3)
            items.append((index, t, rest))
            for left, right in (("「", "」"), ("（", "）"), ("【", "】")):
                if rest.count(left) != rest.count(right):
                    found.append((index + 1, "QUOTE", rest))
            body = rest.split("：", 1)[1] if not rest.startswith("画面文字：") and "：" in rest else rest
            if re.search(r"[A-Za-z]{2,}|[0-9]{2,}", body) and not re.search(r"(S|A|B)级|第\d|Lv", body):
                found.append((index + 1, "ASCII", rest))
            if re.search(r"\]」|］」|\]\]|【|『|』", rest):
                found.append((index + 1, "SYMBOL", rest))
        for index, t, rest in items:
            if rest.startswith("画面文字："):
                body = rest[5:]
                if len(norm(body)) <= 2 and not body.endswith("…"):
                    found.append((index + 1, "SHORT", rest))
        seen = {}
        for index, t, rest in items:
            key_text = norm(rest.split("：", 1)[-1])
            if len(key_text) < 4:
                continue
            for t0, i0, _rest in seen.get(key_text, []):
                if t - t0 <= 10:
                    found.append((index + 1, f"DUP@{i0 + 1}", rest))
            seen.setdefault(key_text, []).append((t, index, rest))
        if found:
            reports.append({"key": key, "count": len(found)})
            for line_no, tag, text in found:
                issues.append({"key": key, "line": line_no, "tag": tag, "text": text})
    return issues, reports


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    keys = args or None
    issues, reports = run(keys)
    for report_row in reports:
        print("=" * 20, report_row["key"], report_row["count"])
        for issue in issues:
            if issue["key"] == report_row["key"]:
                print(f"  {issue['line']}\t{issue['tag']}\t{issue['text']}")
    result = report.write("scan_polish", {"segments": reports, "issues": issues}, ok=not issues)
    report.echo(result)
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())