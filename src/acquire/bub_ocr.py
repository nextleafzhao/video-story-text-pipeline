"""行动模式段专用：角色头像气泡式对话的采集与解析。

某些段全程是左上角「头像 + 姓名 + 台词」气泡，不在底部字幕带里，
原来的 band 裁切抓不到正文；这类段改采一块左侧气泡区域。
气泡坐标与 UI 词表需按目标游戏调整。

用法:
  python bub_ocr.py <key> <视频文件名>      # 抽帧 + OCR，产物 work/bub/<key>.jsonl
  python bub_ocr.py <key> --parse           # 只解析已有 jsonl，打印时间线
"""
import os, sys, json, re, subprocess

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np
from src.common import config, paths

_cfg = config.pipeline()
FFMPEG = _cfg.get("ffmpeg", "ffmpeg")
_VIDEO_DIRS = _cfg.get("video_dirs", [])
# 气泡区域坐标：优先读 pipeline.json 的 bubble，缺省沿用原游戏布局
_bubble = _cfg.get("bubble", {})
CX, CY = _bubble.get("x", 190), _bubble.get("y", 130)
CW, CH = _bubble.get("w", 1240), _bubble.get("h", 400)
BUBD = paths.ensure_work("bub")

PUNCT = re.compile(r"[，。！？、…：；,!?·]")
# 气泡区里混进来的 HUD / 任务提示，不是对话 —— 按游戏调整
UI = ()

# 战斗飘字（元素反应名/伤害数字）会被误当成「姓名 + 正文」的一对，全部排除
REACTION = set()


def find_video(name):
    for d in _VIDEO_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None


def extract(src, outdir):
    os.makedirs(outdir, exist_ok=True)
    bub = os.path.join(outdir, "bub.raw")
    cmd = [FFMPEG, "-y", "-v", "error", "-i", src,
           "-vf", "fps=1,crop=%d:%d:%d:%d" % (CW, CH, CX, CY),
           "-f", "rawvideo", "-pix_fmt", "bgr24", bub]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("FFMPEG FAIL", r.stderr[-1500:])
        return None
    return os.path.getsize(bub) // (CW * CH * 3)


_eng = None
_n = 0


def _init(rawpath, n):
    global _eng, _n
    from rapidocr_onnxruntime import RapidOCR
    _n = n
    _eng = RapidOCR(det_limit_type='max', det_limit_side_len=1100, width_height_ratio=-1,
                    det_model_path=None, rec_model_path=None,
                    intra_op_num_threads=1, inter_op_num_threads=1, rec_batch_num=1)


def _work(args):
    import cv2
    rawpath, lo, hi = args
    arr = np.memmap(rawpath, dtype=np.uint8, mode='r', shape=(_n, CH, CW, 3))
    out = []
    for i in range(lo, hi):
        img = np.ascontiguousarray(arr[i])
        img = cv2.resize(img, None, fx=0.8, fy=0.8, interpolation=cv2.INTER_AREA)
        r, _ = _eng(img, use_cls=False)
        boxes = []
        for box, txt, score in (r or []):
            ys = [p[1] / 0.8 for p in box]
            xs = [p[0] / 0.8 for p in box]
            boxes.append([int(min(ys)), int(min(xs)), int(max(ys)), int(max(xs)),
                          txt, round(float(score), 3)])
        out.append({"t": i, "bub": boxes})
    return out


def ocr(rawpath, outjsonl):
    from multiprocessing import Pool
    n = os.path.getsize(rawpath) // (CW * CH * 3)
    chunks = [(rawpath, i, min(i + 50, n)) for i in range(0, n, 50)]
    with Pool(2, initializer=_init, initargs=(rawpath, n)) as pool, \
            open(outjsonl, "w", encoding="utf-8") as f:
        for res in pool.imap(_work, chunks):
            for r in res:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("DONE", n, "frames ->", outjsonl)


def _clusters(boxes):
    """按 y 重叠聚成若干行块，一行一块。"""
    ls = [b for b in boxes if b[5] >= 0.5 and b[4].strip()]
    ls.sort(key=lambda b: (b[0], b[1]))
    out = []
    for b in ls:
        if out and b[0] - out[-1][-1][2] <= 60 and abs(b[1] - out[-1][0][1]) <= 60:
            out[-1].append(b)
        else:
            out.append([b])
    return out


CJK = re.compile(r"[\u4e00-\u9fff]")
NUMJUNK = re.compile(r"^[0-9A-Za-z.%×/\\ \-]+$")


def _cjk_len(s):
    return len(CJK.findall(s or ""))


def parse_frame(boxes):
    """气泡结构：第一行是姓名（短、无标点、含汉字），下面一到多行是正文。"""
    best = None
    for c in _clusters(boxes):
        if len(c) < 2:
            continue
        nm = c[0][4].strip()
        # 姓名：含汉字、无句读、长度受限
        if not (1 <= _cjk_len(nm) <= 8) or len(nm) > 10 or PUNCT.search(nm):
            continue
        if NUMJUNK.match(nm) or any(u in nm for u in UI) or nm in REACTION:
            continue
        body_rows = sorted(c[1:], key=lambda b: (b[0], b[1]))
        body = "".join(b[4] for b in body_rows)
        conf = min(b[5] for b in body_rows)
        if _cjk_len(body) < 2 or NUMJUNK.match(body.strip()):
            continue
        if any(u in body for u in UI) and _cjk_len(body) < 6:
            continue
        # 战斗飘字：正文也是反应名，或正文里除反应名外没有别的汉字
        if body.strip() in REACTION:
            continue
        if re.fullmatch(r"(?:%s)+" % "|".join(REACTION), body.strip()):
            continue
        # 排序依据：先比 OCR 置信度（高者更可能是完整清晰的帧），再比字数
        score = (round(conf, 2), _cjk_len(body))
        if best is None or score > best[2]:
            best = (nm, body, score, conf)
    return (best[0], best[1], best[3]) if best else ("", "", 0.0)


ELLIPSIS_MARKS = re.compile(r"[·．…]")


def fix_bubble(s):
    """气泡台词的专用清洗：只作用于 17 段，避免影响 01–16 已交付内容。

    游戏气泡里的省略号「…」会被 OCR 认成「·」「.」「···」或干脆漏掉，
    这里统一还原成「…」；夹在汉字中间的单个拉丁字母是放大镜等 HUD 图标的误识，剔除。
    """
    s = s.strip()
    s = re.sub(r"(?<=[\u4e00-\u9fff])[A-Za-z](?=[\u4e00-\u9fff])", "", s)
    s = re.sub(r"[·．]{2,}", "…", s)
    s = re.sub(r"(?<=[\u4e00-\u9fff])[·．]+(?=[\u4e00-\u9fff])", "…", s)
    s = re.sub(r"(?<=[\u4e00-\u9fff])[·．]+(?=[！？。，、]|$)", "…", s)
    s = re.sub(r"[·．]+", "…", s)
    s = re.sub(r"…{2,}", "…", s)
    s = re.sub(r"[．.]$", "。", s)
    return s.strip()


def _skeleton(s):
    """去掉省略号标记后的纯正文，用于判断两条 OCR 是不是同一句。"""
    return re.sub(r"[·．…]", "", s or "")


def _cjk(s):
    return len(re.findall(r"[\u4e00-\u9fff]", s or ""))


def parse(key):
    """把逐帧气泡结果合成台词时间线。

    气泡在屏幕上停留若干秒，同一句会被反复识别成多个变体：
    有完整带省略号的、有漏掉省略号的、也有被 HUD 图标遮出残字的。
    OCR 置信度对「有没有省略号」并不敏感（省略号反而常拉低置信度），
    所以判据用「去掉省略号标记后的骨架正文」：
      - 骨架相同 = 同一句，优先保留带省略号、字数更全的变体；
      - 骨架不同但高度相似 = 同一句的残帧，同样并入。
    """
    from src.merge.merge import norm, _sim
    p = os.path.join(BUBD, key + ".jsonl")
    recs = [json.loads(l) for l in open(p, encoding="utf-8")]

    frames = []
    for r in recs:
        n, b, conf = parse_frame(r.get("bub") or [])
        if b:
            frames.append({"t": r["t"], "name": n, "body": b, "conf": conf})

    def same_sentence(a, b):
        ka, kb = _skeleton(a), _skeleton(b)
        if not ka or not kb:
            return False
        if ka == kb:
            return True
        short, long_ = (ka, kb) if len(ka) <= len(kb) else (kb, ka)
        if long_.startswith(short) and len(long_) - len(short) <= 20:
            return True
        return _sim(ka, kb) >= 0.6

    def better(a, b):
        """a 是否比 b 更适合当这一句的正文。"""
        ka, kb = _skeleton(a["body"]), _skeleton(b["body"])
        # 骨架更完整（字数更多）优先；骨架一样长时，带省略号的优先
        if len(ka) != len(kb):
            return len(ka) > len(kb)
        ea = len(re.findall(r"[·．…]", a["body"]))
        eb = len(re.findall(r"[·．…]", b["body"]))
        if bool(ea) != bool(eb):
            return bool(ea)
        return a["conf"] > b["conf"]

    def same_name(a, b):
        if a == b:
            return True
        if not a or not b:
            return False
        return len(a) == len(b) and sum(1 for x, y in zip(a, b) if x != y) <= 1

    runs, cur = [], None
    for f in frames:
        if cur and same_name(f["name"], cur["name"]) and f["t"] - cur["end"] <= 2 \
                and same_sentence(f["body"], cur["best"]["body"]):
            cur["end"] = f["t"]
            if better(f, cur["best"]):
                cur["best"] = f
            cur["names"][f["name"]] = cur["names"].get(f["name"], 0) + 1
            continue
        cur = {"t": f["t"], "end": f["end"] if "end" in f else f["t"], "name": f["name"],
               "best": f, "names": {f["name"]: 1}}
        runs.append(cur)

    lines = []
    for r in runs:
        b = r["best"]
        name = max(r["names"].items(), key=lambda kv: kv[1])[0]
        lines.append({"t": r["t"], "end": r["end"], "name": name,
                      "body": fix_bubble(b["body"]), "q": b["conf"],
                      "conf": b["conf"], "kind": "line"})
    return lines


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    key = sys.argv[1]
    if sys.argv[2] == "--parse":
        for l in parse(key):
            print("[%d-%d] %r | %r" % (l["t"], l["end"], l["name"], l["body"]))
        return
    name = sys.argv[2]
    src = find_video(name)
    if not src:
        print("MISSING", name)
        return
    raw = os.path.join(BUBD, key)
    n = extract(src, raw)
    print("frames", n, flush=True)
    ocr(os.path.join(raw, "bub.raw"), os.path.join(BUBD, key + ".jsonl"))
    import shutil
    shutil.rmtree(raw, ignore_errors=True)


if __name__ == "__main__":
    main()
