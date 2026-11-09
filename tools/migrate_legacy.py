#!/usr/bin/env python
"""Copy a legacy .work tree into the new work/ + profiles/ layout.

usage:
    python -m tools.migrate_legacy --source "C:/path/to/原项目" [--dry-run] [--force]

Mapping:
    .work/ocr          -> work/ocr
    .work/txt          -> work/txt/draft
    .work/txt2         -> work/txt/final
    .work/align        -> work/align
    .work/bub          -> work/bub
    .work/map          -> work/map
    .work/frames       -> work/frames
    .work/BWiki/json   -> work/wiki/json
    .work/BWiki/raw    -> work/wiki/raw
    .work/corrections* -> profiles/
    .work/names_extra.json / screen_drop.json / speaker_drop.json / name_unknown.json -> profiles/

Videos, deliverables and raw frame dumps are intentionally not copied.
"""

import argparse
import os
import shutil
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.common import paths, report

DIR_MAP = {
    "ocr": ("ocr",),
    "txt": ("txt", "draft"),
    "txt2": ("txt", "final"),
    "align": ("align",),
    "bub": ("bub",),
    "map": ("map",),
    "frames": ("frames",),
}
PROFILE_FILES = (
    "corrections.json",
    "names_extra.json",
    "screen_drop.json",
    "speaker_drop.json",
    "name_unknown.json",
)
PROFILE_DIRS = ("corrections.d",)


def _copy_file(src, dst, force=False):
    if os.path.exists(dst) and not force:
        return "skipped"
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    return "copied"


def _copy_tree(src, dst, force=False):
    copied = skipped = 0
    for root, _dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        target_root = os.path.join(dst, rel) if rel != "." else dst
        os.makedirs(target_root, exist_ok=True)
        for name in files:
            result = _copy_file(os.path.join(root, name), os.path.join(target_root, name), force)
            copied += result == "copied"
            skipped += result == "skipped"
    return copied, skipped


def main(argv=None):
    parser = argparse.ArgumentParser(prog="migrate_legacy")
    parser.add_argument("--source", required=True, help="legacy project root or its .work directory")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    base = args.source
    if os.path.isdir(os.path.join(base, ".work")):
        base = os.path.join(base, ".work")
    if not os.path.isdir(base):
        print(f"source not found: {args.source}")
        return 1

    plan = []
    for name, parts in DIR_MAP.items():
        src = os.path.join(base, name)
        if os.path.isdir(src):
            plan.append((src, os.path.join(paths.WORK, *parts), "tree"))
    for name in ("json", "raw"):
        src = os.path.join(base, "BWiki", name)
        if os.path.isdir(src):
            plan.append((src, paths.work("wiki", name), "tree"))
    for name in PROFILE_FILES:
        src = os.path.join(base, name)
        if os.path.isfile(src):
            plan.append((src, paths.profile_path(name), "file"))
    for name in PROFILE_DIRS:
        src = os.path.join(base, name)
        if os.path.isdir(src):
            plan.append((src, paths.profile_path(name), "tree"))

    if args.dry_run:
        for src, dst, kind in plan:
            print(f"{kind:<5} {paths.rel(src)} -> {paths.rel(dst)}")
        return 0

    copied = skipped = 0
    for src, dst, kind in plan:
        if kind == "file":
            result = _copy_file(src, dst, args.force)
            copied += result == "copied"
            skipped += result == "skipped"
        else:
            c, s = _copy_tree(src, dst, args.force)
            copied += c
            skipped += s
    report.write("migrate_legacy", {"source": base, "copied": copied, "skipped": skipped},
                 ok=True)
    print(f"copied {copied}, skipped {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())