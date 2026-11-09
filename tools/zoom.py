#!/usr/bin/env python
"""Zoom a region of an existing PNG for character-by-character checks.

usage: python -m tools.zoom <png> <x> <y> <w> <h> [scale]
"""

import os
import sys

import cv2


def main(argv=None):
    args = argv if argv is not None else sys.argv[1:]
    if len(args) < 5:
        print(__doc__)
        return 1
    path, x, y, w, h = args[0], int(args[1]), int(args[2]), int(args[3]), int(args[4])
    scale = float(args[5]) if len(args) > 5 else 3.0
    image = cv2.imread(path)
    if image is None:
        print(f"cannot read {path}")
        return 1
    crop = image[y:y + h, x:x + w]
    crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    out = os.path.splitext(path)[0] + f"_z{x}_{y}.png"
    cv2.imwrite(out, crop)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())