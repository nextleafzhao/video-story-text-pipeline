"""Extract subtitle band + UI panel raw frames from one video.

Crop regions are read from config/pipeline.json so they can be adapted to
any game / video layout.
"""
import os, sys, subprocess

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.common import config

_cfg = config.pipeline()
FFMPEG = _cfg.get("ffmpeg", "ffmpeg")
_fps = _cfg.get("fps", 1)
_c = _cfg["crop"]


def _crop_str(region):
    return f"crop={region['w']}:{region['h']}:{region['x']}:{region['y']}"


BAND = _crop_str(_c["band"])
PANEL = _crop_str(_c["panel"])
OPT = _crop_str(_c["opt"])
DESC = _crop_str(_c["desc"])

DIM = {k: (v["w"], v["h"]) for k, v in _c.items()}


def extract(src, outdir, ss=None, t=None, fps=None):
    os.makedirs(outdir, exist_ok=True)
    fps = fps or _fps
    band = os.path.join(outdir, "band.raw")
    panel = os.path.join(outdir, "panel.raw")
    opt = os.path.join(outdir, "opt.raw")
    desc = os.path.join(outdir, "desc.raw")
    cmd = [FFMPEG, "-y", "-v", "error"]
    if ss is not None:
        cmd += ["-ss", str(ss)]
    if t is not None:
        cmd += ["-t", str(t)]
    cmd += ["-i", src,
            "-filter_complex",
            f"[0:v]fps={fps},split=4[b][p][o][d];"
            f"[b]{BAND}[band];[p]{PANEL}[panel];[o]{OPT}[opt];[d]{DESC}[desc]",
            "-map", "[band]", "-f", "rawvideo", "-pix_fmt", "bgr24", band,
            "-map", "[panel]", "-f", "rawvideo", "-pix_fmt", "bgr24", panel,
            "-map", "[opt]", "-f", "rawvideo", "-pix_fmt", "bgr24", opt,
            "-map", "[desc]", "-f", "rawvideo", "-pix_fmt", "bgr24", desc]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("FFMPEG FAIL", r.stderr[-2000:])
        return None
    bw, bh = DIM["band"]
    pw, ph = DIM["panel"]
    ow, oh = DIM["opt"]
    dw, dh = DIM["desc"]
    n_band = os.path.getsize(band) / (bw * bh * 3)
    n_panel = os.path.getsize(panel) / (pw * ph * 3)
    n_opt = os.path.getsize(opt) / (ow * oh * 3)
    n_desc = os.path.getsize(desc) / (dw * dh * 3)
    return band, panel, opt, desc, n_band, n_panel, n_opt, n_desc


if __name__ == "__main__":
    src = sys.argv[1]
    out = sys.argv[2]
    ss = float(sys.argv[3]) if len(sys.argv) > 3 else None
    t = float(sys.argv[4]) if len(sys.argv) > 4 else None
    print(extract(src, out, ss, t))
