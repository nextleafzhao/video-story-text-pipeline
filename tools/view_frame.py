#!/usr/bin/env python
"""Dump a cropped raw frame from work/raw/<key> to PNG for visual checks.

usage: python -m tools.view_frame <key> <sec> [band|panel|opt|desc]
"""

import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np

from src.common import config, paths


def main(argv=None):
    args = argv if argv is not None else sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        return 1
    key, sec = args[0], int(args[1])
    what = args[2] if len(args) > 2 else "band"
    crop = config.pipeline().get("crop", {})
    if what not in crop:
        print(f"unknown zone: {what}")
        return 1
    box = crop[what]
    width, height = box["w"], box["h"]
    src = paths.work("raw", key, what + ".raw")
    if not os.path.exists(src):
        print(f"missing raw frame: {paths.rel(src)}")
        return 1
    total = os.path.getsize(src) // (width * height * 3)
    if sec >= total:
        print(f"frame {sec} out of range (total {total})")
        return 1
    frames = np.memmap(src, dtype=np.uint8, mode="r", shape=(total, height, width, 3))
    image = np.ascontiguousarray(frames[sec])
    out = os.path.join(paths.ensure_work("frames"), f"{key}_{sec}_{what}.png")
    cv2.imwrite(out, image)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())