"""Sequential driver: extract raw band/panel, OCR, clean up. One video at a time.

Segment list is read from config/segments.json (copy .example to start).
"""
import os, sys, time, shutil

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.common import config, paths
from src.acquire import extract, ocr_run

VIDEOS = [(v[0], v[2]) for v in config.videos()]
VIDDIRS = config.pipeline().get("video_dirs", [])
RAW = paths.work("raw")
OCRD = paths.work("ocr")
LOG = paths.work("driver.log")


def video_path(name):
    for d in VIDDIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def main(keys=None):
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(OCRD, exist_ok=True)
    wanted = list(keys) if keys else [k for k, _ in VIDEOS]
    done = []
    for key, name in VIDEOS:
        if key not in wanted:
            continue
        out_json = os.path.join(OCRD, key + ".jsonl")
        if os.path.exists(out_json) and os.path.getsize(out_json) > 1000:
            log(f"SKIP {key} (exists)")
            continue
        src = video_path(name)
        if not src:
            log(f"MISSING {key} {name}")
            continue
        rd = os.path.join(RAW, key)
        log(f"EXTRACT {key} {name}")
        t0 = time.time()
        info = extract.extract(src, rd)
        if not info:
            log(f"FAIL extract {key}")
            continue
        log(f"  decoded {info[4]} frames in {time.time()-t0:.0f}s")
        log(f"OCR {key}")
        t1 = time.time()
        ocr_run.run(rd, out_json)
        log(f"  ocr done in {time.time()-t1:.0f}s")
        shutil.rmtree(rd, ignore_errors=True)
        done.append(key)
    log("ALL DONE")
    return done


if __name__ == "__main__":
    main(sys.argv[1:] or None)
