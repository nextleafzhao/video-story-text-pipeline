#!/usr/bin/env python
"""Print OCR text of every frame in a raw crop file.

usage: python -m tools.probe_desc <raw-path> [zone]
"""

import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from rapidocr_onnxruntime import RapidOCR

from src.common import config


def main(argv=None):
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    path = args[0]
    zone = args[1] if len(args) > 1 else "desc"
    box = config.pipeline().get("crop", {}).get(zone)
    if not box:
        print(f"unknown zone: {zone}")
        return 1
    width, height = box["w"], box["h"]
    total = os.path.getsize(path) // (width * height * 3)
    frames = np.memmap(path, dtype=np.uint8, mode="r", shape=(total, height, width, 3))
    engine = RapidOCR(det_limit_type="max", det_limit_side_len=960, width_height_ratio=-1,
                      intra_op_num_threads=2, inter_op_num_threads=1, rec_batch_num=1)
    for index in range(total):
        image = np.ascontiguousarray(frames[index])
        result, _ = engine(image, use_cls=False)
        text = " | ".join(item for _, item, _score in (result or []))
        print(index, text[:200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())