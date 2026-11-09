#!/usr/bin/env python
"""Unified command line entry for the pipeline.

Run from the repository root:

    python -m src.cli doctor
    python -m src.cli run [keys ...]
    python -m src.cli build [keys ...]
    python -m src.cli align [keys ...]
    python -m src.cli assemble [main|side|supplement|all]
    python -m src.cli check [config|polish|status|recheck|all]
    python -m src.cli migrate --source <legacy-project> [--dry-run]

Every subcommand writes ``work/reports/<command>.json`` and returns 0 on
success, so both humans and agents can tell whether a step finished.
"""

import argparse
import os
import shutil
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.common import config, paths, report


def _exe_exists(value):
    if not value:
        return False
    if os.path.isabs(value):
        return os.path.exists(value)
    return shutil.which(value) is not None


def _check(name, passed, detail=""):
    return {"name": name, "ok": bool(passed), "detail": str(detail)}


def cmd_doctor(args):
    checks = [
        _check("python", sys.version_info >= (3, 9), ".".join(str(v) for v in sys.version_info[:3]))
    ]
    pipeline_cfg = {}
    for name, required in (("pipeline", True), ("segments", True),
                           ("game_profile", False), ("assemble", True)):
        try:
            data, path = config.load(name, required=required)
            checks.append(_check(f"config:{name}", True, paths.rel(path)))
            if name == "pipeline":
                pipeline_cfg = data
        except Exception as exc:
            checks.append(_check(f"config:{name}", False, exc))
    checks.append(_check("ffmpeg", _exe_exists(pipeline_cfg.get("ffmpeg", "ffmpeg")),
                         pipeline_cfg.get("ffmpeg", "ffmpeg")))
    checks.append(_check("work", os.access(paths.ROOT, os.W_OK), paths.rel(paths.WORK)))
    for module in ("cv2", "numpy", "rapidocr_onnxruntime"):
        try:
            __import__(module)
            checks.append(_check(f"dep:{module}", True, "importable"))
        except Exception as exc:
            checks.append(_check(f"dep:{module}", False, exc))

    blocking = {"python", "ffmpeg", "work"}
    hard_ok = all(item["ok"] for item in checks
                  if item["name"] in blocking or item["name"].startswith("config:"))
    result = report.write("doctor", {"checks": checks}, ok=hard_ok)
    for item in checks:
        print(f"{'OK  ' if item['ok'] else 'FAIL'} {item['name']:<24} {item['detail']}")
    report.echo(result)
    return 0 if hard_ok else 1


def cmd_run(args):
    from src import driver
    done = driver.main(args.keys or None)
    result = report.write("run", {"done": done}, ok=bool(done))
    report.echo(result)
    return 0 if done else 1


def cmd_build(args):
    from src.build import build_txt
    written = build_txt.main(args.keys or None)
    result = report.write("build", {"files": [paths.rel(path) for path in written]}, ok=bool(written))
    report.echo(result)
    return 0 if written else 1


def cmd_align(args):
    from src.align import align
    written = align.main(args.keys or None)
    result = report.write("align", {"files": [paths.rel(path) for path in written]}, ok=bool(written))
    report.echo(result)
    return 0 if written else 1


def cmd_assemble(args):
    from src.build import assemble_main, assemble_side, assemble_supplement
    funcs = {"main": assemble_main.main, "side": assemble_side.main,
             "supplement": assemble_supplement.main}
    if args.target == "all":
        return max(func() for func in funcs.values())
    return funcs[args.target]()


def cmd_check(args):
    from src.checks import recheck, scan_polish, status, validate_config
    funcs = {"config": validate_config.main, "polish": scan_polish.main,
             "status": status.main, "recheck": recheck.main}
    if args.target == "all":
        return max(func([]) for func in funcs.values())
    return funcs[args.target]([])


def cmd_migrate(args):
    from tools import migrate_legacy
    argv = ["--source", args.source]
    if args.dry_run:
        argv.append("--dry-run")
    if args.force:
        argv.append("--force")
    return migrate_legacy.main(argv)


def build_parser():
    parser = argparse.ArgumentParser(prog="pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="check config, ffmpeg, dependencies")
    doctor.set_defaults(func=cmd_doctor)

    run = sub.add_parser("run", help="extract + OCR one or all segments")
    run.add_argument("keys", nargs="*")
    run.set_defaults(func=cmd_run)

    build = sub.add_parser("build", help="OCR jsonl -> work/txt/draft")
    build.add_argument("keys", nargs="*")
    build.set_defaults(func=cmd_build)

    align = sub.add_parser("align", help="align with wiki -> work/txt/final")
    align.add_argument("keys", nargs="*")
    align.set_defaults(func=cmd_align)

    assemble = sub.add_parser("assemble", help="render deliverables")
    assemble.add_argument("target", nargs="?", default="main",
                          choices=["main", "side", "supplement", "all"])
    assemble.set_defaults(func=cmd_assemble)

    check = sub.add_parser("check", help="run quality checks")
    check.add_argument("target", nargs="?", default="all",
                       choices=["config", "polish", "status", "recheck", "all"])
    check.set_defaults(func=cmd_check)

    migrate = sub.add_parser("migrate", help="copy legacy .work data into this layout")
    migrate.add_argument("--source", required=True)
    migrate.add_argument("--dry-run", action="store_true")
    migrate.add_argument("--force", action="store_true")
    migrate.set_defaults(func=cmd_migrate)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())