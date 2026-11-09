#!/usr/bin/env python
"""Dump one video frame (cropped region) to PNG for visual verification.

usage: python -m tools.vframe <video-file-name> <sec> [band|panel|opt|desc|full]
"""

import os
import subprocess
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np

from src.common import config, paths


def find_video(name):
    for directory in config.pipeline().get("video_dirs", []):
        path = os.path.join(directory, name)
        if os.path.exists(path):
            return path
    return None


def main(argv=None):
    args = argv if argv is not None else sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        return 1
    name, sec = args[0], args[1]
    what = args[2] if len(args) > 2 else "band"
    cfg = config.pipeline()
    crops = cfg.get("crop", {})
    if what == "full":
        width, height = cfg.get("full_size", [1920, 1080])
        vf = "null"
    elif what in crops:
        box = crops[what]
        width, height = box["w"], box["h"]
        vf = f"crop={width}:{height}:{box['x']}:{box['y']}"
    else:
        print(f"unknown zone: {what}")
        return 1
    src = find_video(name)
    if not src:
        print(f"video not found: {name}")
        return 1
    cmd = [cfg.get("ffmpeg", "ffmpeg"), "-v", "error", "-ss", sec, "-i", src,
           "-frames:v", "1", "-vf", vf, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    result = subprocess.run(cmd, capture_output=True)
    buf = np.frombuffer(result.stdout, dtype=np.uint8)
    if buf.size != width * height * 3:
        print(f"decode failed: got {buf.size} bytes (expected {width * height * 3})")
        return 1
    image = buf.reshape(height, width, 3)
    out = os.path.join(paths.ensure_work("frames"),
                       f"{os.path.splitext(name)[0]}_{sec}_{what}.png")
    cv2.imwrite(out, image)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())