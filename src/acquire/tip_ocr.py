#!/usr/bin/env python
"""OCR the map-marker tooltip panel (whole-panel capture) for configured keys.

Products ``work/align/tips_<key>.json`` consumed by ``src.align.tips``.
"""

import glob
import json
import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import cv2
import numpy as np
from multiprocessing import Pool
from rapidocr_onnxruntime import RapidOCR

from src.common import config, paths
from src.merge.merge import merge, norm
from src.build.build_txt import build_whitelist

_cfg = config.pipeline()
VID_DIRS = _cfg.get("video_dirs", [])
_tip = _cfg.get("tip_panel", {})
X0, Y0 = _tip.get("x", 590), _tip.get("y", 12)
X1, Y1 = _tip.get("x2", 1360), _tip.get("y2", 520)
KEYS = tuple(config.game_profile().get("tips_keys", ()))


def video_path(key):
    row = config.video(key)
    if not row:
        return None
    name = row[2]
    for directory in VID_DIRS:
        path = os.path.join(directory, name)
        if os.path.exists(path):
            return path
        hits = glob.glob(os.path.join(directory, "*" + name[4:]))
        if hits:
            return hits[0]
    return None


def grab(path, sec):
    cap = cv2.VideoCapture(path)
    cap.set(cv2.CAP_PROP_POS_MSEC, sec * 1000)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return None
    return np.ascontiguousarray(frame[Y0:Y1, X0:X1])


def ocr(img):
    engine = RapidOCR(det_limit_type="max", det_limit_side_len=1100, width_height_ratio=-1,
                      intra_op_num_threads=1, inter_op_num_threads=1, rec_batch_num=1)
    result, _ = engine(img, use_cls=False)
    boxes = []
    for box, txt, score in result or []:
        ys = [point[1] for point in box]
        xs = [point[0] for point in box]
        boxes.append([int(min(ys)), int(min(xs)), int(max(ys)), int(max(xs)), txt, round(float(score), 3)])
    return boxes


def work(job):
    key, t, path = job
    img = grab(path, t)
    if img is None:
        return key, t, []
    return key, t, ocr(img)


def panels_for(key):
    path = paths.work("ocr", key + ".jsonl")
    if not os.path.exists(path):
        return []
    recs = [json.loads(line) for line in open(path, encoding="utf-8")]
    _lines, _opts, descs = merge(recs, build_whitelist())
    return [d for d in descs if len(norm(d["title"] + d["body"])) >= 20]


def main(argv=None):
    keys = (argv or sys.argv[1:]) or KEYS
    if not keys:
        print("no tips_keys configured; set game_profile.json -> tips_keys")
        return 0
    jobs = []
    for key in keys:
        path = video_path(key)
        if not path:
            print("MISSING", key)
            continue
        for desc in panels_for(key):
            jobs.append((key, (desc["t"] + desc["end"]) // 2, path))
    print("jobs", len(jobs), flush=True)
    result = {}
    with Pool(2) as pool:
        for key, t, boxes in pool.imap(work, jobs):
            result.setdefault(key, {})[t] = boxes
    directory = paths.ensure_work("align")
    for key in keys:
        with open(os.path.join(directory, "tips_" + key + ".json"), "w", encoding="utf-8", newline="\n") as handle:
            json.dump(result.get(key, {}), handle, ensure_ascii=False, indent=1)
        print(key, len(result.get(key, {})))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())