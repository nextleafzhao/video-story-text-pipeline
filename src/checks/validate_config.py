#!/usr/bin/env python
"""Validate the four configuration files without third-party dependencies.

Exit code 0 means every config is present, parseable and internally
consistent.  The same checks run from ``python -m src.cli check config``.
"""

import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.common import config, report


def _expect(issues, condition, message):
    if not condition:
        issues.append(message)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def check_pipeline(issues):
    data = config.pipeline()
    _expect(issues, isinstance(data.get("ffmpeg"), str), "pipeline.ffmpeg 必须是字符串")
    _expect(issues, isinstance(data.get("video_dirs"), list), "pipeline.video_dirs 必须是数组")
    crop = data.get("crop", {})
    for zone in ("band", "panel", "opt", "desc"):
        box = crop.get(zone)
        _expect(issues, isinstance(box, dict), f"pipeline.crop.{zone} 缺失")
        if isinstance(box, dict):
            for field in ("w", "h", "x", "y"):
                _expect(issues, isinstance(box.get(field), int), f"pipeline.crop.{zone}.{field} 必须是整数")
    ocr = data.get("ocr", {})
    _expect(issues, isinstance(ocr.get("workers"), int) and ocr.get("workers", 0) >= 1, "pipeline.ocr.workers 必须是 >=1 的整数")
    _expect(issues, _is_number(ocr.get("scale")) and ocr.get("scale", 0) > 0, "pipeline.ocr.scale 必须是正数")
    _expect(issues, isinstance(ocr.get("step"), int) and ocr.get("step", 0) >= 1, "pipeline.ocr.step 必须是 >=1 的整数")
    _expect(issues, _is_number(data.get("fps")) and data.get("fps", 0) > 0, "pipeline.fps 必须是正数")


def check_segments(issues):
    data = config.segments()
    videos = data.get("videos")
    _expect(issues, isinstance(videos, list) and videos, "segments.videos 必须是非空数组")
    if not isinstance(videos, list):
        return {}
    seen = set()
    for index, item in enumerate(videos):
        label = f"segments.videos[{index}]"
        _expect(issues, isinstance(item, dict), f"{label} 必须是对象")
        if not isinstance(item, dict):
            continue
        for field in ("key", "title", "file"):
            _expect(issues, isinstance(item.get(field), str) and item.get(field), f"{label}.{field} 必须是非空字符串")
        _expect(issues, _is_number(item.get("duration")), f"{label}.duration 必须是数字")
        key = item.get("key")
        if key:
            _expect(issues, key not in seen, f"{label}.key 重复: {key}")
            seen.add(key)
    return {item.get("key"): item for item in videos if isinstance(item, dict) and item.get("key")}


def check_assemble(issues, by_key):
    data = config.assemble()
    main = data.get("main")
    _expect(issues, isinstance(main, dict), "assemble.main 缺失")
    if isinstance(main, dict):
        for field in ("title", "file"):
            _expect(issues, isinstance(main.get(field), str) and main.get(field), f"assemble.main.{field} 必须是非空字符串")
        arcs = main.get("arcs")
        _expect(issues, isinstance(arcs, list), "assemble.main.arcs 必须是数组")
        if isinstance(arcs, list):
            for index, arc in enumerate(arcs):
                label = f"assemble.main.arcs[{index}]"
                _expect(issues, isinstance(arc, list) and len(arc) == 2, f"{label} 必须是 [幕名, [段key...]]")
                if isinstance(arc, list) and len(arc) == 2:
                    _expect(issues, isinstance(arc[0], str), f"{label}[0] 必须是字符串")
                    _expect(issues, isinstance(arc[1], list), f"{label}[1] 必须是数组")
                    for key in arc[1] if isinstance(arc[1], list) else []:
                        _expect(issues, key in by_key, f"{label} 引用了不存在的段: {key}")

    side = data.get("side", {})
    if side.get("enabled"):
        for field in ("title", "file"):
            _expect(issues, isinstance(side.get(field), str) and side.get(field), f"assemble.side.{field} 必须是非空字符串")
        for key in side.get("keys", []):
            _expect(issues, key in by_key, f"assemble.side.keys 引用了不存在的段: {key}")

    supplement = data.get("supplement", {})
    if supplement.get("enabled"):
        for field in ("title", "file"):
            _expect(issues, isinstance(supplement.get(field), str) and supplement.get(field), f"assemble.supplement.{field} 必须是非空字符串")
        for key in supplement.get("keys", []):
            _expect(issues, key in by_key, f"assemble.supplement.keys 引用了不存在的段: {key}")


def check_game_profile(issues):
    data = config.game_profile()
    if not data:
        return
    for field in ("ui_words", "noise_words", "series_titles", "extra_name_whitelist", "player_names", "map_panel_keys", "tips_keys"):
        if field in data:
            _expect(issues, isinstance(data[field], list), f"game_profile.{field} 必须是数组")
    for field in ("name_fix", "typo_fix"):
        if field in data:
            _expect(issues, isinstance(data[field], dict), f"game_profile.{field} 必须是对象")


def main(argv=None):
    issues = []
    for check in (
        lambda: check_pipeline(issues),
        lambda: check_segments(issues),
        lambda: check_game_profile(issues),
    ):
        try:
            check()
        except Exception as exc:
            issues.append(str(exc))
    by_key = {}
    try:
        by_key = check_segments([])
    except Exception:
        pass
    try:
        check_assemble(issues, by_key)
    except Exception as exc:
        issues.append(str(exc))

    result = report.write("validate_config", {"issues": issues}, ok=not issues)
    if issues:
        for issue in issues:
            print("FAIL", issue)
    else:
        print("OK   所有配置通过校验")
    report.echo(result)
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())