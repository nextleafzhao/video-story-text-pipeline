"""行动模式段专用：右侧常驻任务面板的整块采集与 OCR。

某些段是行动模式：右侧常驻一块任务面板，desc 裁切只截到面板一角，这里按整块重采。
面板坐标需按目标游戏调整。

用法:
  python map_ocr.py <key> <视频文件名>    # 抽帧 + OCR -> work/map/<key>.jsonl
  python map_ocr.py <key> --parse        # 解析成面板条目
"""
import os, sys, json, re, subprocess

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np
from src.common import config, paths

_cfg = config.pipeline()
FFMPEG = _cfg.get("ffmpeg", "ffmpeg")
_VIDEO_DIRS = _cfg.get("video_dirs", [])
# 右侧行动面板坐标：优先读 pipeline.json 的 map_panel，缺省沿用原游戏布局
_map_panel = _cfg.get("map_panel", {})
MX, MY = _map_panel.get("x", 1400), _map_panel.get("y", 0)
MW, MH = _map_panel.get("w", 520), _map_panel.get("h", 560)
MAPD = paths.ensure_work("map")


def find_video(name):
    for d in _VIDEO_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None


def extract(src, outdir):
    os.makedirs(outdir, exist_ok=True)
    raw = os.path.join(outdir, "map.raw")
    cmd = [FFMPEG, "-y", "-v", "error", "-i", src,
           "-vf", "fps=1,crop=%d:%d:%d:%d" % (MW, MH, MX, MY),
           "-f", "rawvideo", "-pix_fmt", "bgr24", raw]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("FFMPEG FAIL", r.stderr[-1500:])
        return None
    return os.path.getsize(raw) // (MW * MH * 3)


_eng = None
_n = 0


def _init(rawpath, n):
    global _eng, _n
    from rapidocr_onnxruntime import RapidOCR
    _n = n
    _eng = RapidOCR(det_limit_type='max', det_limit_side_len=1280, width_height_ratio=-1,
                    det_model_path=None, rec_model_path=None,
                    intra_op_num_threads=1, inter_op_num_threads=1, rec_batch_num=1)


def _work(args):
    import cv2
    rawpath, lo, hi = args
    arr = np.memmap(rawpath, dtype=np.uint8, mode='r', shape=(_n, MH, MW, 3))
    out = []
    for i in range(lo, hi):
        img = np.ascontiguousarray(arr[i])
        r, _ = _eng(img, use_cls=False)
        boxes = []
        for box, txt, score in (r or []):
            ys = [p[1] for p in box]
            xs = [p[0] for p in box]
            boxes.append([int(min(ys)), int(min(xs)), int(max(ys)), int(max(xs)),
                          txt, round(float(score), 3)])
        out.append({"t": i, "map": boxes})
    return out


def ocr(rawpath, outjsonl):
    from multiprocessing import Pool
    n = os.path.getsize(rawpath) // (MW * MH * 3)
    chunks = [(rawpath, i, min(i + 50, n)) for i in range(0, n, 50)]
    with Pool(2, initializer=_init, initargs=(rawpath, n)) as pool, \
            open(outjsonl, "w", encoding="utf-8") as f:
        for res in pool.imap(_work, chunks):
            for r in res:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("DONE", n, "frames ->", outjsonl)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    key = sys.argv[1]
    if sys.argv[2] == "--parse":
        recs = [json.loads(l) for l in open(os.path.join(MAPD, key + ".jsonl"), encoding="utf-8")]
        for r in recs:
            if r["map"]:
                print(r["t"], " | ".join(b[4] for b in sorted(r["map"], key=lambda b: (b[0], b[1]))))
        return
    name = sys.argv[2]
    src = find_video(name)
    if not src:
        print("MISSING", name)
        return
    raw = os.path.join(MAPD, key)
    n = extract(src, raw)
    print("frames", n, flush=True)
    ocr(os.path.join(raw, "map.raw"), os.path.join(MAPD, key + ".jsonl"))
    import shutil
    shutil.rmtree(raw, ignore_errors=True)


if __name__ == "__main__":
    main()
