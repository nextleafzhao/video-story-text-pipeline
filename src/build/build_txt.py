"""Build per-video transcript txt from merged OCR timeline.

Segment list and game-specific correction tables are externalised to
config/segments.json and (optionally) config/game_profile.json so the core
pipeline stays game-agnostic.
"""
import glob, json, os, re, sys
from collections import Counter

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.common import config, paths
from src.merge.merge import merge, tidy, norm, collect_candidates, collect_frames, nkey, parse_band

VIDEOS = [(key, title, filename, dur) for key, title, filename, dur, _wiki in config.videos()]
PROFILE = config.game_profile()

# UI words / noise words / series titles — override via game_profile.json
UI_WORDS = tuple(PROFILE.get("ui_words", ()))
NOISE_WORDS = tuple(PROFILE.get("noise_words", ()))
SERIES_TITLES = tuple(PROFILE.get("series_titles", ()))
EXTRA_NAME_WHITELIST = PROFILE.get("extra_name_whitelist", [])
NAME_FIX = PROFILE.get("name_fix", {})
TYPO_FIX = PROFILE.get("typo_fix", {})

DIST_RE = re.compile(r"^(高处|低处)?\s*\d+(\.\d+)?\s*m$", re.I)
DOTS_RE = re.compile(r"^[·…\.]+$")


def hms(sec):
    sec = int(sec)
    return f"{sec//60:02d}:{sec%60:02d}"


def clean_body(s):
    """Generic OCR text normalisation. Game-specific typo fixes live in
    game_profile.json -> typo_fix."""
    s = tidy(s)
    if DOTS_RE.match(s):
        return "……"
    # game-specific typo fixes
    for wrong, right in TYPO_FIX.items():
        s = s.replace(wrong, right)
    # normalise brackets / quotes to 「」
    s = s.replace("】", "」").replace("【", "「")
    s = s.replace("［", "「").replace("］", "」")
    s = s.replace("\u201d", "」").replace("\u201c", "「")
    s = s.replace("\u300e", "「").replace("\u300f", "」")
    s = re.sub(r"「([^」］\]]{1,12})\]", r"「\1」", s)
    s = re.sub(r"「([^」］\]]{1,12})］", r"「\1」", s)
    # balance quotes
    if s.startswith("（") and "）" not in s:
        s += "）"
    if s.startswith("「") and "」" not in s:
        s += "」"
    # trailing dots -> ellipsis
    s = re.sub(r"([哇啊呀哦呃])[一—]$", r"\1——", s)
    s = re.sub(r"——+", "——", s)
    if re.search(r"[\u4e00-\u9fff]", s):
        s = re.sub(r"\.$", "。", s)
    s = s.replace("『", "「").replace("』", "」")
    s = drop_stray_close(s)
    while s.endswith("」") and s.count("」") > s.count("「"):
        s = s[:-1]
    return s.strip()


def drop_stray_close(s):
    out, depth = [], 0
    for i, ch in enumerate(s):
        if ch == "「":
            depth += 1
        elif ch == "」":
            if depth:
                depth -= 1
            elif i and i + 1 < len(s):
                prev, nxt = s[i - 1], s[i + 1]
                if "\u4e00" <= prev <= "\u9fff" and (
                        nxt in "，。、；：！？" or "\u4e00" <= nxt <= "\u9fff"):
                    continue
        out.append(ch)
    return "".join(out)


def panel_objective(panel):
    texts = []
    for z in sorted(panel or [], key=lambda z: (z[0], z[1])):
        t = tidy(z[4])
        if len(t) < 2 or DIST_RE.match(t) or "追踪" in t:
            continue
        texts.append(t)
    return texts


def build_whitelist():
    cnt = Counter()
    frames = Counter()
    for path in glob.glob(os.path.join(paths.work("ocr"), "*.jsonl")):
        recs = [json.loads(l) for l in open(path, encoding="utf-8")]
        for k, v in collect_candidates(recs).items():
            cnt[k] += v
        for k, v in collect_frames(recs).items():
            frames[k] += v
        for r in recs:
            nm = parse_band(r.get("band") or [], frozenset())[0]
            if nm and len(nkey(nm)) >= 2:
                cnt[nkey(nm)] += 1
    wl = {k for k, v in cnt.items() if v >= 2}
    wl |= {k for k, v in frames.items() if v >= 3 and len(k) >= 2}
    for n in EXTRA_NAME_WHITELIST:
        wl.add(nkey(n))
    return wl


def canonical_names(lines):
    forms = {}
    for l in lines:
        n = l.get("name")
        if not n:
            continue
        forms.setdefault(nkey(n), Counter())[n] += 1
    best = {}
    for k, c in forms.items():
        bracketed = [f for f in c if f.startswith("「")]
        best[k] = max(bracketed, key=c.get) if bracketed else c.most_common(1)[0][0]
    for l in lines:
        if l.get("name"):
            l["name"] = best.get(nkey(l["name"]), l["name"])
            n = nkey(l["name"])
            if n in NAME_FIX:
                l["name"] = NAME_FIX[n]


def build(key, title, filename, dur, wl):
    recs = [json.loads(l) for l in open(paths.work("ocr", key + ".jsonl"), encoding="utf-8")]
    lines, opts, descs = merge(recs, wl)
    canonical_names(lines)

    events = []
    for l in lines:
        events.append((l["t"], 0, "line", l))
    for o in opts:
        events.append((o["t"], 1, "opt", o))
    for d in descs:
        events.append((d["t"], 3, "desc", d))

    runs, prev, start = [], None, 0
    for r in recs:
        obj = "｜".join(panel_objective(r.get("panel")))
        if obj != prev:
            if prev and r["t"] - start >= 5:
                runs.append((start, prev))
            prev, start = obj, r["t"]
    if prev and recs and recs[-1]["t"] - start >= 5:
        runs.append((start, prev))
    for t, obj in runs:
        events.append((t, 2, "obj", obj))

    events.sort(key=lambda e: (e[0], e[1]))

    out = [f"【{title}】",
           f"对应视频：{filename}",
           f"时长：{hms(dur)}",
           "台词来源：画面内嵌中文字幕（OCR 识别）",
           "说话人来源：画面中显示的角色名，逐帧识别后与台词按画面时间对齐",
           "标记说明：??? = 游戏画面本身未显示姓名；画面文字 = 界面/教程/字卡/选项/任务目标等非台词文本",
           "=" * 56, ""]

    last_opt, last_opt_t = None, -999
    last_obj, last_obj_t = None, -999
    screen_at = []

    def emit_screen(t, text):
        text = clean_body(text)
        if not text or any(w in text for w in NOISE_WORDS):
            return
        k = norm(text)
        for i in range(len(screen_at) - 1, -1, -1):
            et, idx, ek = screen_at[i]
            if t - et > 12:
                break
            if k and ek and (k in ek or ek in k):
                if len(k) > len(ek):
                    out[idx] = f"[{hms(t)}] 画面文字：{text}"
                    screen_at[i] = (t, idx, k)
                else:
                    screen_at[i] = (t, idx, ek)
                return
        screen_at.append((t, len(out), k))
        out.append(f"[{hms(t)}] 画面文字：{text}")

    for t, order, kind, data in events:
        if kind == "opt":
            key_txt = " / ".join(data["texts"])
            if key_txt == last_opt and t - last_opt_t <= 90:
                last_opt_t = t
                continue
            out.append(f"[{hms(t)}] 画面文字：{key_txt}")
            last_opt, last_opt_t = key_txt, t
            continue
        if kind == "obj":
            if any(s in data for s in SERIES_TITLES):
                continue
            if data == last_obj and t - last_obj_t <= 120:
                last_obj_t = t
                continue
            out.append(f"[{hms(t)}] 画面文字：任务目标·{data}")
            last_obj, last_obj_t = data, t
            continue
        if kind == "desc":
            body = clean_body(data["body"])
            title = clean_body(data["title"])
            if not body and not title:
                continue
            if title and body:
                emit_screen(t, f"{title}｜{body}")
            elif body:
                emit_screen(t, body)
            else:
                emit_screen(t, title)
            continue
        body = clean_body(data["body"])
        if not body:
            continue
        name = data.get("name", "")
        if any(w in name for w in UI_WORDS):
            name = ""
        if body.startswith("成就达成"):
            body = body[4:].lstrip("：: ")
            name = ""
        if data.get("kind") == "screen" or not name:
            emit_screen(t, body)
        else:
            out.append(f"[{hms(t)}] {name}：{body}")
    return "\n".join(out) + "\n", len(lines), len(opts)


def main(keys=None):
    out_dir = paths.ensure_work("txt", "draft")
    wl = build_whitelist()
    written = []
    for key, title, filename, dur in VIDEOS:
        if keys and key not in keys:
            continue
        src = paths.work("ocr", key + ".jsonl")
        if not os.path.exists(src):
            print("MISSING", key)
            continue
        text, nl, no = build(key, title, filename, dur, wl)
        dst = os.path.join(out_dir, f"{key}_{title}.txt")
        with open(dst, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        written.append(dst)
        print(f"{key}: {nl} lines, {no} opt groups -> {dst}")
    return written


if __name__ == "__main__":
    main(sys.argv[1:] or None)
