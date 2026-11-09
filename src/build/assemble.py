"""Shared deliverable assembly logic.

Per-segment txt files are read from ``work/txt/final`` (aligned output) and
fall back to ``work/txt/draft`` (build_txt output).  Three thin wrappers call
this module: ``assemble_main``, ``assemble_side`` and ``assemble_supplement``.
"""

import glob
import json
import os
import re

if __package__ in (None, ""):
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.common import config, paths, report


def txt_dir():
    """Prefer aligned output; fall back to the draft directory."""
    final = paths.work("txt", "final")
    if os.path.isdir(final) and glob.glob(os.path.join(final, "*.txt")):
        return final
    return paths.work("txt", "draft")


def load(key, directory=None):
    directory = directory or txt_dir()
    if not os.path.isdir(directory):
        return None
    matches = [name for name in os.listdir(directory)
               if name.startswith(key + "_") and name.endswith(".txt")]
    if not matches:
        return None
    matches.sort(key=lambda name: os.path.getmtime(os.path.join(directory, name)), reverse=True)
    return os.path.join(directory, matches[0])


def parse(path):
    lines = open(path, encoding="utf-8").read().splitlines()
    head = {"title": "", "video": "", "dur": "", "desc": ""}
    body = []
    started = False
    for line in lines:
        if line.startswith("===="):
            started = True
            continue
        if not started:
            if line.startswith("【"):
                head["title"] = line.strip("【】")
            elif line.startswith("对应视频："):
                head["video"] = line.split("：", 1)[1]
            elif line.startswith("时长："):
                head["dur"] = line.split("：", 1)[1]
            elif line.startswith("任务描述："):
                head["desc"] = line.split("：", 1)[1]
        elif line.strip():
            body.append(line)
    return head, body


def _duration(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def assemble(keys, arcs, title, out_file, intro="", section_prefix=""):
    """Render one deliverable. Returns ``(path, stats)``."""
    by_key = {row[0]: row for row in config.videos()}
    arc_of = {key: name for name, group in arcs for key in group}
    sections, toc = [], []
    total, count, last_arc, missing = 0, 0, None, []

    for index, key in enumerate(keys, 1):
        row = by_key.get(key)
        if not row:
            missing.append(key)
            continue
        path = load(key)
        if not path:
            missing.append(key)
            continue
        head, body = parse(path)
        seg_title = head["title"] or row[1]
        num = f"{index:02d}"
        arc = arc_of.get(key, "")
        if arc and arc != last_arc:
            sections.append(f"## {arc}\n")
            toc.append(f"- **{arc}**")
            last_arc = arc
        toc.append(f"  - {num}　{seg_title}　（{head['dur']}）")
        total += _duration(row[3])
        count += 1

        sec = [f"### {num} {section_prefix}{seg_title}", ""]
        if head["desc"]:
            sec += [f"**任务描述**：{head['desc']}", ""]
        sec += [f"> 对应视频：{head['video']}　时长 {head['dur']}", ""]
        for line in body:
            match = re.match(r"^\[(\d+:\d+)\] (.*)$", line)
            if not match:
                continue
            stamp, rest = match.group(1), match.group(2)
            if rest.startswith("画面文字："):
                sec.append(f"[{stamp}] **【画面文字】**{rest[5:]}")
            else:
                speaker, _, text = rest.partition("：")
                sec.append(f"[{stamp}] **{speaker}**：{text}" if text else f"[{stamp}] {speaker}")
        sec += ["", "---", ""]
        sections.append("\n".join(sec))

    hours, rest = divmod(int(total), 3600)
    minutes, seconds = divmod(rest, 60)
    head = [f"# {title}", ""]
    if intro:
        head += [intro, ""]
    head += [
        f"> 依据 {count} 段剧情视频的画面字幕与界面文字整理，未使用语音识别",
        "",
        "## 编辑说明",
        "",
        "- **来源**：画面内嵌中文字幕与界面文字（OCR 识别）",
        "- **说话人**：画面中显示的角色名，逐帧识别后与台词按画面时间对齐",
        "- **标记**：`【画面文字】` 表示界面、教程、字卡、选项、任务目标等非台词文本",
        "- **时间**：每段方括号内为该句字幕首次出现的时间点（分:秒）",
        "",
        "## 目录",
        "",
    ] + toc + ["", f"> 全 {count} 段，合计时长约 {hours} 小时 {minutes} 分 {seconds} 秒。", "", "---", ""]

    out = os.path.join(paths.ROOT, out_file)
    os.makedirs(os.path.dirname(out) or paths.ROOT, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(head) + "\n".join(sections))
    return out, {"count": count, "missing": missing, "keys": list(keys)}


def run_main(argv=None):
    cfg = config.assemble()
    main = cfg.get("main") or {
        "title": cfg.get("title", "剧情全剧情文本"),
        "file": cfg.get("output_file", "transcript.md"),
        "arcs": cfg.get("arcs", []),
    }
    arcs = main.get("arcs", [])
    keys = [key for _name, group in arcs for key in group]
    if not keys:
        excluded = set(cfg.get("supplement_keys", []))
        keys = [row[0] for row in config.videos() if row[0] not in excluded]
    out, stats = assemble(keys, arcs, main["title"], main["file"], intro=main.get("intro", ""))
    print("wrote", paths.rel(out), stats["count"], "segments")
    if stats["missing"]:
        print("MISSING", ", ".join(stats["missing"]))
    report.write("assemble_main", {"output": paths.rel(out), **stats}, ok=not stats["missing"])
    return 0 if not stats["missing"] else 1


def main(argv=None):
    return run_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())