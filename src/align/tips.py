"""Rebuild map-marker tooltip panels from whole-panel OCR boxes."""
import os, re, json, sys
from collections import Counter

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.common import paths
from src.merge.merge import rows_of_boxes, norm, tidy, fix_brackets, _sim

KEYS = ("09_qy1", "10_qy2", "11_qy3", "12_qy4", "13_qy5", "14_qy6", "15_qy7", "16_qy8")

PARA_GAP = 8


def _rows(boxes):
    out = []
    for r in rows_of_boxes([tuple(b) for b in boxes]):
        r = sorted(r, key=lambda z: z[1])
        # 地图地名标签会与浮窗文字处于同一行，按横向间距拆开，只保留主文本块
        clusters = []
        for z in r:
            if clusters and z[1] - clusters[-1][-1][3] <= 80:
                clusters[-1].append(z)
            else:
                clusters.append([z])
        best = max(clusters, key=lambda c: sum(len(norm(z[4])) for z in c))
        out.append((min(z[0] for z in best), max(z[2] for z in best), min(z[1] for z in best),
                    "".join(z[4] for z in best)))
    out.sort()
    return out


def panel(boxes):
    """-> (title, unit, body) or None"""
    info = _rows(boxes)
    if len(info) < 2:
        return None
    longs = [x0 for y0, y1, x0, t in info if len(norm(t)) >= 10]
    if not longs:
        return None
    mode = Counter(round(x0 / 10) * 10 for x0 in longs).most_common(1)[0][0]
    ti = next((i for i, (y0, y1, x0, t) in enumerate(info)
               if "·" in t and len(norm(t)) >= 5 and x0 <= mode + 40), None)
    if ti is None:
        return None
    head = info[ti]
    rows = info[ti + 1:]
    # unit line sits just below the title, slightly right of the body column
    unit = ""
    if rows and 20 <= rows[0][0] - head[1] <= 60 and rows[0][2] >= mode + 25 and len(norm(rows[0][3])) <= 12:
        unit = tidy(rows[0][3])
        rows = rows[1:]
    keep = []
    for i, (y0, y1, x0, t) in enumerate(rows):
        prev_gap = y0 - rows[i - 1][1] if i else 999
        next_gap = rows[i + 1][0] - y1 if i + 1 < len(rows) else 999
        # isolated short row = map place label bleeding into the crop
        if len(norm(t)) <= 6 and prev_gap > 30 and next_gap > 30:
            continue
        keep.append((y0, y1, t, prev_gap))
    if not keep:
        return None
    gaps = sorted(g for _, _, _, g in keep[1:])
    med = gaps[len(gaps) // 2] if gaps else 0
    parts, cur = [], keep[0][2]
    for y0, y1, t, gap in keep[1:]:
        if gap > med + PARA_GAP:
            parts.append(cur)
            cur = t
        else:
            cur += t
    parts.append(cur)
    title = tidy(head[3])
    body = "\n".join(fix_brackets(tidy(p)) for p in parts)
    return title, unit, body


def load(key):
    p = paths.work("align", "tips_" + key + ".json")
    if not os.path.exists(p):
        return []
    raw = json.load(open(p, encoding="utf-8"))
    items = []
    for t, boxes in sorted(raw.items(), key=lambda kv: int(kv[0])):
        r = panel(boxes)
        if r and len(norm(r[2])) >= 20:
            items.append({"t": int(t), "title": r[0], "unit": r[1], "body": r[2]})
    # same panel captured repeatedly -> keep the most complete copy
    merged = []
    for it in items:
        same_unit = (not it["unit"]) or (not merged[-1]["unit"]) if merged else False
        if merged and _sim(norm(it["title"]), norm(merged[-1]["title"])) >= 0.8 \
                and it["t"] - merged[-1]["t"] <= 40 \
                and (same_unit or _sim(norm(it["unit"]), norm(merged[-1]["unit"])) >= 0.8):
            if len(norm(it["body"])) > len(norm(merged[-1]["body"])):
                merged[-1]["title"] = it["title"]
                merged[-1]["unit"] = it["unit"] or merged[-1]["unit"]
                merged[-1]["body"] = it["body"]
            continue
        merged.append(dict(it))
    return merged
