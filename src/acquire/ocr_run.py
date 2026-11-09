"""OCR the extracted band/panel raw frames of one video, with worker processes."""
import json, os, sys, time, hashlib

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np, cv2
from multiprocessing import Pool
from rapidocr_onnxruntime import RapidOCR
from src.acquire.extract import DIM, _cfg

BW, BH = DIM["band"]
PW, PH = DIM["panel"]
OW, OH = DIM["opt"]
DW, DH = DIM["desc"]
SCALE = _cfg.get("ocr", {}).get("scale", 0.75)

_eng = None
_band = None
_panel = None
_opt = None
_desc = None
_last_panel = {}
_last_opt = {}
_last_desc = {}
THREADS = int(os.environ.get("OCR_THREADS", "1"))
BSCALE = float(os.environ.get("OCR_SCALE", str(SCALE)))

def init(bandpath, panelpath, optpath, descpath):
    global _eng, _band, _panel, _opt, _desc
    # rapidocr-onnxruntime 1.2.3 起，只要传了 det_*/rec_* 参数就必须显式给出
    # det_model_path/rec_model_path，否则 UpdateParameters 取 model_path 直接 KeyError
    _eng = RapidOCR(det_limit_type='max', det_limit_side_len=960, width_height_ratio=-1,
                    det_model_path=None, rec_model_path=None,
                    intra_op_num_threads=THREADS, inter_op_num_threads=1, rec_batch_num=1)
    nb = os.path.getsize(bandpath) // (BW*BH*3)
    npn = os.path.getsize(panelpath) // (PW*PH*3)
    _band = np.memmap(bandpath, dtype=np.uint8, mode='r', shape=(nb, BH, BW, 3))
    _panel = np.memmap(panelpath, dtype=np.uint8, mode='r', shape=(npn, PH, PW, 3))
    no = os.path.getsize(optpath) // (OW*OH*3)
    _opt = np.memmap(optpath, dtype=np.uint8, mode='r', shape=(no, OH, OW, 3))
    nd = os.path.getsize(descpath) // (DW*DH*3)
    _desc = np.memmap(descpath, dtype=np.uint8, mode='r', shape=(nd, DH, DW, 3))
    _last_panel.clear(); _last_opt.clear(); _last_desc.clear()

def ocr_img(img):
    r, _ = _eng(img, use_cls=False)
    out = []
    if not r:
        return out
    for box, txt, score in r:
        ys = [p[1] for p in box]; xs = [p[0] for p in box]
        out.append([int(min(ys)), int(min(xs)), int(max(ys)), int(max(xs)), txt, round(float(score), 3)])
    return out

def work(idxs):
    res = []
    for i in idxs:
        band = _band[i]
        small = cv2.resize(band, None, fx=BSCALE, fy=BSCALE, interpolation=cv2.INTER_AREA)
        bl = ocr_img(small)
        panel = np.ascontiguousarray(_panel[i])
        h = hashlib.md5(panel.tobytes()).hexdigest()
        pl = _last_panel.get(h)
        if pl is None:
            pl = ocr_img(panel)
            _last_panel[h] = pl
        opt = np.ascontiguousarray(_opt[i])
        oh = hashlib.md5(opt.tobytes()).hexdigest()
        ol = _last_opt.get(oh)
        if ol is None:
            ol = ocr_img(opt)
            _last_opt[oh] = ol
        desc = np.ascontiguousarray(_desc[i])
        dh = hashlib.md5(desc.tobytes()).hexdigest()
        dl = _last_desc.get(dh)
        if dl is None:
            dl = ocr_img(desc)
            _last_desc[dh] = dl
        res.append({"t": i, "band": bl, "panel": pl, "opt": ol, "desc": dl})
    return res

def run(viddir, outpath, workers=None, step=None):
    _oc = _cfg.get("ocr", {})
    workers = workers or _oc.get("workers", 2)
    step = step or _oc.get("step", 100)
    band = os.path.join(viddir, "band.raw"); panel = os.path.join(viddir, "panel.raw")
    opt = os.path.join(viddir, "opt.raw"); desc = os.path.join(viddir, "desc.raw")
    nb = os.path.getsize(band) // (BW*BH*3)
    idx = list(range(nb))
    chunks = [idx[i:i+step] for i in range(0, nb, step)]
    t0 = time.time(); done = 0
    with Pool(workers, initializer=init, initargs=(band, panel, opt, desc)) as pool:
        with open(outpath, "w", encoding="utf-8") as f:
            for res in pool.imap(work, chunks):
                for r in res:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
                done += len(res)
                if done % 500 < step:
                    el = time.time() - t0
                    print(f"  {done}/{nb} {el:.0f}s eta {el/done*(nb-done):.0f}s", flush=True)
    print(f"DONE {nb} frames in {time.time()-t0:.0f}s", flush=True)

if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 2)
