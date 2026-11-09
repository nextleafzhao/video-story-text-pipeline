"""Align OCR timeline with wiki script pages and emit a corrected transcript.

WIKI mapping (key -> wiki page title) is loaded from config/segments.json
(videos[].wiki field). If no wiki mapping exists for a segment, it falls
through to the clean-only branch.
"""
import difflib, json, os, re, sys, glob
from collections import Counter

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.common import config, paths
from src.merge.merge import merge, tidy, norm, nkey, _sim, _subseq, is_title, fix_brackets
from src.build.build_txt import build_whitelist, canonical_names, hms, clean_body, VIDEOS
from src.align import tips, map_panel

ROOT = paths.ROOT
WORK = paths.WORK

# Build WIKI map from segments.json: entries with a "wiki" field
WIKI = {}
for _item in config.segments().get("videos", []):
    if _item.get("wiki"):
        WIKI[_item["key"]] = _item["wiki"]

PROFILE = config.game_profile()
PLAYER_NAMES = tuple(PROFILE.get("player_names", ()))
# Sequential keys that share one continuous wiki script (cursor carries over).
CURSOR_KEYS = tuple(PROFILE.get("align_cursor_keys", ()))
CURSOR = paths.work("align", "cursor.json")
MAP_PANEL_KEYS = tuple(PROFILE.get("map_panel_keys", map_panel.KEYS))
TIPS_KEYS = tuple(PROFILE.get("tips_keys", tips.KEYS))

def _lcp(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n

def _frag(short, long_):
    """短行是否为长行的同段碎片（允许少量识别误差）。"""
    if not short or len(long_) < len(short) + 6:
        return False
    m = difflib.SequenceMatcher(None, short, long_, autojunk=False).find_longest_match(
        0, len(short), 0, len(long_))
    return m.size >= max(8, int(len(short) * 0.8))

SCREEN_RE = re.compile(r"^\[(\d+):(\d+)\] 画面文字：(.*)$")

def dedupe_screen(lines, win=15):
    """字卡/界面文字逐帧累积时会出现渐进截断的同句，只保留最长的一条。"""
    items = {}
    for i, ln in enumerate(lines):
        m = SCREEN_RE.match(ln)
        if m:
            items[i] = (int(m.group(1)) * 60 + int(m.group(2)), m.group(3))
    drop = set()
    keys = sorted(items)
    for pos, i in enumerate(keys):
        if i in drop:
            continue
        t, tx = items[i]
        a = norm(tx)
        if len(a) < 3:
            continue
        for j in keys[pos + 1:]:
            t2, tx2 = items[j]
            if t2 - t > win:
                break
            if j in drop:
                continue
            b = norm(tx2)
            if len(b) < 3:
                continue
            short, long_ = (i, j) if len(a) <= len(b) else (j, i)
            la, lb = (a, b) if len(a) <= len(b) else (b, a)
            if "任务目标" in tx or "任务目标" in tx2:
                if a != b and not (len(lb) - len(la) <= 8 and lb.startswith(la)):
                    continue
            ok = la == lb or ((lb.startswith(la) or la in lb)
                              and (len(lb) - len(la) <= 10 or len(la) >= 8))
            if not ok and abs(t2 - t) <= 2 and len(la) >= 8:
                # 教学卡的高亮行会被单独识别成一条，正文里包含同一句
                ok = _frag(la, lb)
            if not ok and abs(len(a) - len(b)) <= 2 and not re.search(r"\d", a + b):
                ok = _sim(a, b) >= 0.88
            if ok:
                drop.add(short)
    return [ln for i, ln in enumerate(lines) if i not in drop]

FINAL_REP = [("]」", "」"), ("］」", "」"), ("踏砂", "踏鞴砂"), ("4洛列夫茨基", "科洛列夫茨基")]

def final_fix(lines):
    out = []
    for ln in lines:
        for a, b in FINAL_REP:
            ln = ln.replace(a, b)
        out.append(ln)
    return out

DIALOG_RE = re.compile(r"^\[(\d+):(\d+)\] ([^：]{1,12})：(.+)$")
LABEL_RE = re.compile(r"^\[(\d+):(\d+)\] 画面文字：(.+的肚子)$")
ONO_RE = re.compile(r"^\[(\d+):(\d+)\] 画面文字：((?:咕|哗|呼)[^，。！？\s]{0,4}…)$")

def dedupe_lines(lines, win=4, same_win=10):
    """同一说话人 4 秒内被逐帧累积出的截断/重识别台词，只保留完整的一条。"""
    items = {}
    for i, ln in enumerate(lines):
        m = DIALOG_RE.match(ln)
        if not m or m.group(3) == "画面文字":
            continue
        items[i] = (int(m.group(1)) * 60 + int(m.group(2)), m.group(3), norm(m.group(4)))
    drop = set()
    keys = sorted(items)
    for pos, i in enumerate(keys):
        if i in drop:
            continue
        t, sp, a = items[i]
        for j in keys[pos + 1:]:
            t2, sp2, b = items[j]
            if t2 - t > same_win:
                break
            if j in drop or sp2 != sp:
                continue
            short, long_ = (i, j) if len(a) <= len(b) else (j, i)
            la, lb = (a, b) if len(a) <= len(b) else (b, a)
            same = la == lb
            # 空正文（如「……」）不能当作任意长句的前缀
            trunc = 0 < len(la) <= 6 and len(lb) - len(la) <= 20 and lb.startswith(la)
            if same:
                drop.add(j)
            elif trunc and t2 - t <= win:
                drop.add(short)
    return [ln for i, ln in enumerate(lines) if i not in drop]

def restore_device_label(lines):
    """「光之镜」台词旁同屏显示的设备名牌「无恒预设应答终端」也是画面文字，
    按「宁多录不漏录」原则补回；12 秒窗口内只补一次，避免重复。"""
    have = []
    for ln in lines:
        m = re.match(r"^\[(\d+):(\d+)\]", ln)
        if m and "无恒预设应答终端" in ln:
            have.append(int(m.group(1)) * 60 + int(m.group(2)))
    res, last = [], -999
    for ln in lines:
        m = re.match(r"^\[(\d+):(\d+)\] 「光之镜」：", ln)
        if m:
            t = int(m.group(1)) * 60 + int(m.group(2))
            if t - last > 12 and not any(abs(t - h) <= 12 for h in have):
                res.append(f"[{m.group(1)}:{m.group(2)}] 画面文字：「光之镜」无恒预设应答终端")
                last = t
        res.append(ln)
    return res

def balance_quotes(lines, win=2):
    """补全未闭合的「，并清掉孤立的」；画面文字分支同样处理。"""
    # 先处理孤立后引号：前面没有未闭合的「，后面又直接接正文或标点
    fixed = []
    for ln in lines:
        m = SCREEN_RE.match(ln)
        body = m.group(3) if m else (
            ln.split("：", 1)[1] if re.match(r"^\[\d+:\d+\] .+：", ln) else None)
        if body is not None and "」" in body:
            out, depth = [], 0
            for i2, ch in enumerate(body):
                if ch == "「":
                    depth += 1
                elif ch == "」":
                    if depth:
                        depth -= 1
                    elif i2 and i2 + 1 < len(body):
                        prev, nxt = body[i2 - 1], body[i2 + 1]
                        if (prev in "…——、，,." or "一" <= prev <= "鿿") and (
                                nxt in "，。、；：！？…——" or "一" <= nxt <= "鿿"):
                            continue
                out.append(ch)
            nb = "".join(out)
            if nb != body:
                head = ln[: len(ln) - len(body)]
                ln = head + nb
        fixed.append(ln)
    lines = fixed

    items = []
    for i, ln in enumerate(lines):
        m = re.match(r"^\[(\d+):(\d+)\] (.+)$", ln)
        if m:
            items.append((i, int(m.group(1)) * 60 + int(m.group(2)), m.group(3)))
    for pos, (i, t, rest) in enumerate(items):
        if "：" not in rest:
            continue
        body = rest.split("：", 1)[1]
        need = body.count("「") - body.count("」")
        if need <= 0 or body[-1:] in "，,、；;：:":
            continue
        nxt = items[pos + 1] if pos + 1 < len(items) else None
        # 「画面文字」条目之间不是同句续写，不能因为下一行也是画面文字就跳过补引号
        if (nxt and not rest.startswith("画面文字：")
                and nxt[2].split("：", 1)[0] == rest.split("：", 1)[0]
                and nxt[1] - t <= win):
            continue
        lines[i] = lines[i].rstrip() + "」" * min(need, 2)
    return lines

def drop_echo_screen(lines, win=3):
    """字幕帧丢失名牌时，同一句会以无姓名的画面文字再出现一次，去掉这条回声。"""
    dialogs = {}
    for ln in lines:
        m = DIALOG_RE.match(ln)
        if m and m.group(3) != "画面文字":
            t = int(m.group(1)) * 60 + int(m.group(2))
            dialogs.setdefault(norm(m.group(4)), []).append(t)
    out = []
    for ln in lines:
        m = SCREEN_RE.match(ln)
        if m:
            t = int(m.group(1)) * 60 + int(m.group(2))
            k = norm(m.group(3))
            if len(k) >= 4 and any(abs(t2 - t) <= win for t2 in dialogs.get(k, [])):
                continue
        out.append(ln)
    return out

def merge_ono(lines, win=4):
    """说话人标签被拆成「名字+的肚子」时，把紧随其后的拟声词并回该标签。"""
    out, i = [], 0
    while i < len(lines):
        m = LABEL_RE.match(lines[i])
        if m and i + 1 < len(lines):
            m2 = ONO_RE.match(lines[i + 1])
            if m2:
                t = int(m.group(1)) * 60 + int(m.group(2))
                t2 = int(m2.group(1)) * 60 + int(m2.group(2))
                if t2 - t <= win:
                    out.append(f"[{hms(t)}] {m.group(3)}：{m2.group(3)}")
                    i += 2
                    continue
        out.append(lines[i])
        i += 1
    return out

def load_wiki(name):
    d = json.load(open(paths.work("wiki", "json", name + ".json"), encoding="utf-8"))
    seq = []
    for s in d.get("sections", []):
        for it in s.get("items", []):
            if it.get("t") == "line":
                seq.append({"sp": it.get("sp") or "", "tx": it.get("tx") or ""})
    return seq, d

def align(lines, seq, th=0.72, start=0):
    p = start
    hits, review, miss = [], [], []
    pending = []
    for l in lines:
        if l.get("kind") != "line":
            continue
        ck = norm(l["body"])
        if len(ck) < 3:
            continue
        best, bi = 0.0, -1
        for j in range(max(0, p - 1), len(seq)):
            s = _sim(ck, norm(seq[j]["tx"]))
            if s > best:
                best, bi = s, j
        gap = bi - p
        if best >= th and gap > 30 and best < 0.97:
            best = 0.0
        if best >= th:
            w = seq[bi]
            if "旅行者" in w["tx"] or "主角" in w["tx"]:
                nm = next((n for n in PLAYER_NAMES if n in l["body"]), "")
                if nm:
                    w = {"sp": w["sp"], "tx": w["tx"].replace("旅行者", nm).replace("主角", nm)}
            wk = norm(w["tx"])
            same_name = True
            auto = best >= 0.86 and abs(len(ck) - len(wk)) <= 3 and same_name
            # OCR 把名牌标题并进正文（如「纳菲斯生论派贤者…」），正文尾部与剧本一致
            if not auto and best >= 0.70 and wk and len(ck) > len(wk) + 3 and ck.endswith(wk):
                auto = True
            if auto and w["tx"] != l["body"]:
                hits.append({"t": l["t"], "ocr": l["body"], "wiki": w["tx"], "sp": w["sp"],
                             "sim": round(best, 3)})
                l["body"] = w["tx"]
            elif not auto and w["tx"] != l["body"]:
                review.append({"t": l["t"], "ocr": l["body"], "wiki": w["tx"], "sp": w["sp"],
                               "sim": round(best, 3)})
            if not l.get("name") and w["sp"]:
                l["name"] = w["sp"]
            l["wi"] = bi
            p = bi + 1
        else:
            pending.append((l, ck))
    # 自由探索段（如至冬宫随行人员闲聊）玩家访问顺序与剧本不同，退化为全剧本无序匹配
    for l, ck in pending:
        best, bi = 0.0, -1
        if len(ck) >= 4:
            for j in range(len(seq)):
                s = _sim(ck, norm(seq[j]["tx"]))
                if s > best:
                    best, bi = s, j
        if best >= 0.88:
            w = seq[bi]
            if "旅行者" in w["tx"] or "主角" in w["tx"]:
                nm = next((n for n in PLAYER_NAMES if n in l["body"]), "")
                if nm:
                    w = {"sp": w["sp"], "tx": w["tx"].replace("旅行者", nm).replace("主角", nm)}
            if w["tx"] != l["body"]:
                hits.append({"t": l["t"], "ocr": l["body"], "wiki": w["tx"], "sp": w["sp"],
                             "sim": round(best, 3)})
                l["body"] = w["tx"]
            if not l.get("name") and w["sp"]:
                l["name"] = w["sp"]
            l["wi"] = bi
            continue
        miss.append({"t": l["t"], "body": l["body"], "best": round(best, 3),
                     "cand": seq[bi]["tx"] if bi >= 0 else ""})
    return hits, review, miss, p

def collapse(lines, rounds=3):
    """fold banner-occluded fragments of the same line into the longest variant"""
    for _ in range(rounds):
        out, changed = [], False
        for l in lines:
            if l.get("kind") != "line":
                out.append(l)
                continue
            merged = False
            for i in range(len(out) - 1, max(-1, len(out) - 4), -1):
                p = out[i]
                if p.get("kind") != "line" or l["t"] - p["end"] > 3:
                    continue
                pk, ck = norm(clean_body(p["body"])), norm(clean_body(l["body"]))
                if len(pk) >= 2 and len(ck) >= 2 and (
                        _subseq(pk, ck) or _subseq(ck, pk)
                        or (abs(len(pk) - len(ck)) >= 3 and _sim(pk, ck) >= 0.55)
                        or _sim(pk, ck) >= 0.8):
                    if len(ck) > len(pk):
                        p["body"] = l["body"]
                        p["q"] = l["q"]
                        if not p.get("name"):
                            p["name"] = l.get("name", "")
                    p["end"] = l["t"]
                    merged = changed = True
                    break
            if not merged:
                out.append(l)
        lines = out
        if not changed:
            break
    return lines

def apply_fixes(lines, fixes):
    """逐段人工修正。每条修正形如：
        {"t": 秒, "find": "原文片段", "repl": "替换后"}                   # 改正文
        {"t": 秒, "find": "...", "repl": "...", "field": "name"}          # 改说话人
        {"t": 秒, "find": "...", "repl": "...", "kind": "screen"}         # 只匹配画面文字条目
        {"t": 秒, "find": "...", "repl": "...", "name": "新说话人"}        # 正文替换并把说话人改成新值
    kind 缺省时 line 与 screen 都匹配（先 line 后 screen）。
    """
    for fx in fixes:
        want_kind = fx.get("kind")
        field = fx.get("field", "body")
        for kind in (["line", "screen"] if want_kind is None else [want_kind]):
            hit = False
            for l in lines:
                if l.get("kind") != kind:
                    continue
                if abs(l["t"] - fx["t"]) > 3:
                    continue
                cur = l.get(field) or ""
                if fx["find"] not in cur:
                    continue
                l[field] = cur.replace(fx["find"], fx["repl"])
                if "name" in fx and kind == "line":
                    l["name"] = fx["name"]
                hit = True
                break
            if hit:
                break

def strip_label_prefix(lines):
    """说话人名牌被 OCR 并进正文时剔除，例如「光之镜」无恒预设应答终端…"""
    for l in lines:
        if l.get("kind") != "line" or not l["body"].startswith("「光之镜」"):
            continue
        rest = re.sub(r"^「光之镜」\s*(无恒预设应答终端)?\s*", "", l["body"])
        if not rest or rest == l["body"]:
            continue
        l["body"] = rest
        if not l.get("name"):
            l["name"] = "「光之镜」"

def split_merged(lines, seq):
    """两句不同说话人因字幕重叠被 OCR 并成一行时，按剧本拆回两行"""
    out = []
    for l in lines:
        wi = l.get("wi")
        if wi and l.get("body"):
            pw, cw = seq[wi - 1], seq[wi]
            pt, ct = norm(pw["tx"]), norm(cw["tx"])
            b = norm(clean_body(l["body"]))
            if (pw["sp"] and cw["sp"] and pw["sp"] != cw["sp"]
                    and 2 <= len(pt) <= 12 and b.startswith(pt) and len(b) > len(pt) + 3
                    and ct.startswith(pt) and _sim(b[len(pt):], ct[len(pt):]) >= 0.85):
                out.append({"t": max(0, l["t"] - 1), "end": l["t"], "name": pw["sp"],
                            "body": pw["tx"], "q": l.get("q", 0), "kind": "line"})
                l["body"] = cw["tx"]
                l["name"] = cw["sp"]
        out.append(l)
    return out

# Bubble-dialogue keys (action mode) — configure via game_profile.json -> bubble_keys
BUBBLE_KEYS = tuple(PROFILE.get("bubble_keys", ()))

try:
    from src.acquire import bub_ocr
except ImportError:
    bub_ocr = None


def build(key, title, filename, dur, wl):
    recs = [json.loads(l) for l in open(paths.work("ocr", key + ".jsonl"), encoding="utf-8")]
    lines, opts, descs = merge(recs, wl)
    if key in BUBBLE_KEYS and bub_ocr:
        screen_only = [dict(l, kind="screen", name="") for l in lines if l.get("body")]
        lines = screen_only + bub_ocr.parse(key)
        lines.sort(key=lambda l: l["t"])
    lines = collapse(lines)
    fixes = []
    for cfg_path in (paths.profile_path("corrections.json"),
                     paths.profile_path(os.path.join("corrections.d", key + ".json"))):
        if os.path.exists(cfg_path):
            data = json.load(open(cfg_path, encoding="utf-8"))
            fixes += data.get(key, []) if cfg_path.endswith("corrections.json") else data
    if fixes:
        apply_fixes(lines, fixes)
    canonical_names(lines)
    strip_label_prefix(lines)
    wiki_name = WIKI.get(key)
    hits, review, miss, wd = [], [], [], None
    if key in CURSOR_KEYS:
        cursor_wikis = PROFILE.get("align_cursor_wikis", [])
        seq = []
        for nm in cursor_wikis:
            s, _ = load_wiki(nm)
            seq += s
        start = 0
        if key != CURSOR_KEYS[0] and os.path.exists(CURSOR):
            start = json.load(open(CURSOR, encoding="utf-8")).get("cursor", 0)
        hits, review, miss, endp = align(lines, seq, start=start)
        cur = {}
        if os.path.exists(CURSOR):
            cur = json.load(open(CURSOR, encoding="utf-8"))
        cur["cursor"] = endp
        os.makedirs(os.path.dirname(CURSOR), exist_ok=True)
        json.dump(cur, open(CURSOR, "w", encoding="utf-8"))
    elif wiki_name:
        seq, wd = load_wiki(wiki_name)
        hits, review, miss, _ = align(lines, seq)
    else:
        seq = None
    if seq:
        lines = split_merged(lines, seq)

    # 单字碎片与相邻同名长句重复，视为截断噪声
    lines = [l for l in lines if not (
        l.get("kind") == "line" and len(norm(clean_body(l["body"]))) == 1
        and any(o is not l and o.get("kind") == "line" and o.get("name") == l.get("name")
                and abs(o["t"] - l["t"]) <= 2 and len(norm(clean_body(o["body"]))) > 3
                for o in lines))]

    events = [(l["t"], 0, "line", l) for l in lines]
    events += [(o["t"], 1, "opt", o) for o in opts]
    if key in TIPS_KEYS:
        # 右侧裁切只能截到战报浮窗的一角，改用整块重采的浮窗文本
        events += [(x["t"], 3, "tip", x) for x in tips.load(key)]
    elif key in MAP_PANEL_KEYS:
        # 行动模式的右侧行动面板：desc 裁切只截到一角，改用整块重采。
        # 面板正文是整段长文本，同样要接受 corrections.d 的逐段修正。
        map_items = map_panel.load(key)
        if fixes:
            for it in map_items:
                for fx in fixes:
                    for f in ("head", "body"):
                        if fx["find"] in it[f]:
                            it[f] = it[f].replace(fx["find"], fx["repl"])
        events += [(x["t"], 3, "map", x) for x in map_items]
    else:
        events += [(d["t"], 3, "desc", d) for d in descs]

    runs, prev, start = [], None, 0
    for r in recs:
        obj = "｜".join(tidy(z[4]) for z in sorted(r.get("panel") or [], key=lambda z: (z[0], z[1]))
                       if len(tidy(z[4])) >= 2 and "追踪" not in z[4]
                       and not re.match(r"^(高处|低处)?\s*\d+(\.\d+)?\s*m$", tidy(z[4])))
        if obj != prev:
            if prev and r["t"] - start >= 5:
                runs.append((start, prev))
            prev, start = obj, r["t"]
    if prev and recs and recs[-1]["t"] - start >= 5:
        runs.append((start, prev))
    events += [(t, 2, "obj", o) for t, o in runs]
    events.sort(key=lambda e: (e[0], e[1]))

    head = [f"【{title}】", f"对应视频：{filename}", f"时长：{hms(dur)}",
            "台词来源：画面内嵌中文字幕（OCR 识别），已与 BWiki 剧本逐句对齐校正" if wiki_name
            else "台词来源：画面内嵌中文字幕（OCR 识别）",
            "说话人来源：画面中显示的角色名，逐帧识别后与台词按画面时间对齐",
            "标记说明：??? = 游戏画面本身未显示姓名；画面文字 = 界面/教程/字卡/选项/任务目标等非台词文本"]
    if wd:
        head.append(f"任务描述：{wd['meta'].get('描述','')}")
    head.append("=" * 56)
    out = head + [""]

    last_opt = last_opt_t = last_opt_idx = None
    last_obj = last_obj_t = None
    screen_at = []
    line_ts = [(l["t"], norm(l["body"])) for l in lines
               if l.get("kind") == "line" and l["body"] and l.get("name")
               and not re.search(r"[·.]", l["name"])]
    name_set = {nkey(l["name"]) for l in lines if l.get("name")}
    def _load_drop(name):
        p = paths.profile_path(name)
        if not os.path.exists(p):
            return set()
        return set(json.load(open(p, encoding="utf-8")).get(key, []))
    drop = _load_drop("screen_drop.json")
    drop_name = _load_drop("speaker_drop.json")
    unknown_name = _load_drop("name_unknown.json")

    def split_speaker(text):
        """姓名+职位被 OCR 并进正文时拆回说话人，例如「艾蒂安梅洛彼得堡看守朱斯蒂娜小姐…」"""
        t = fix_brackets(text).strip()
        for n in sorted(name_set, key=len, reverse=True):
            if not (2 <= len(n) <= 6) or not t.startswith(n):
                continue
            rest = t[len(n):]
            for k in range(min(10, len(rest)), 0, -1):
                cand = rest[:k]
                if not is_title(cand):
                    continue
                body = rest[k:].lstrip("：:，,、 ")
                if len(norm(body)) >= 4 and not body.startswith(("，", "。", "！", "？", "、", "…")):
                    return n, body
        return None

    def emit_screen(t, text, allow_split=True):
        text = clean_body(text)
        if not text or text in ("时间", "星期", "任务", "地图", "背包", "设置", "队伍"):
            return
        # 画面文字策略：一律保留。地名标签、职务牌等即使像噪音也照收，
        # 宁多录不漏录；screen_drop.json 只作参考，不再据此整条丢弃。
        if nkey(text) in name_set:
            return
        # 名牌未进入姓名带、姓名被并进正文时，按已知说话人拆回台词。
        # desc 浮层用「｜」拼标题与正文，不是「姓名+正文」，不参与拆分。
        if allow_split and "｜" not in text:
            for n in sorted(name_set, key=len, reverse=True):
                if 3 <= len(n) <= 6 and text.startswith(n):
                    rest = text[len(n):].lstrip("：:，,、 ")
                    if rest.startswith("的"):
                        continue
                    if len(norm(rest)) >= 3 and "/" not in rest:
                        out.append(f"[{hms(t)}] {n}：{rest}")
                        return
        if len(norm(text)) < 2:
            return
        if not re.search(r"[一-鿿A-Za-z]", text):
            return
        if ">" in text or "＜" in text or "<" in text:
            # NPC 界面的 <职位>姓名 名牌：去掉尖括号后作为画面文字保留
            text = re.sub(r"[<>＜＞{｛}｝]", "", text).strip("｜| ")
            if not text:
                return
        # 只丢弃纯操作提示，其余界面文字一律保留
        if re.fullmatch(r"(点击|双击|长按)?(空白区域|屏幕|后)?继续", text) or text in ("双击跳过", "点击后继续"):
            return
        k = norm(text)
        for lt, lk in line_ts:
            # 同一秒的自身行不算回声，否则字卡正文会被自己的台词档掉
            if lt == t or abs(lt - t) > 5 or not lk or not k:
                continue
            # 短句（如「护盾」「时间」这类字卡标题）不判回声，避免误杀
            if len(k) < 6:
                continue
            if _sim(k, lk) >= 0.75 or _lcp(k, lk) >= 9:
                return
        for i in range(len(screen_at) - 1, -1, -1):
            et, idx, ek = screen_at[i]
            if t - et > 12:
                break
            if k and ek and (k in ek or ek in k):
                if len(k) > len(ek):
                    # 保留更完整的版本，并按它实际出现的时间落位，避免旧条目被改写后顺序错乱
                    out[idx] = None
                    screen_at[i] = (t, len(out), k)
                    out.append(f"[{hms(t)}] 画面文字：{text}")
                else:
                    screen_at[i] = (t, idx, ek)
                return
        screen_at.append((t, len(out), k))
        out.append(f"[{hms(t)}] 画面文字：{text}")

    for t, order, kind, data in events:
        if kind == "opt":
            ktxt = " / ".join(clean_body(x).replace("·", "…") for x in data["texts"])
            if not ktxt or ktxt in drop or any(w in ktxt for w in ("奖励一览", "前往任务", "点击领取", "空月祝福")):
                continue
            nk = norm(ktxt)
            if nk == last_opt and t - last_opt_t <= 120:
                last_opt_t = t
                continue
            if last_opt and t - last_opt_t <= 30 and (nk in last_opt or last_opt in nk):
                # 选项条逐帧识别，可能只截到其中一行；保留完整的那组
                if len(nk) > len(last_opt):
                    out[last_opt_idx] = f"[{hms(t)}] 画面文字：{ktxt}"
                    last_opt, last_opt_t = nk, t
                continue
            out.append(f"[{hms(t)}] 画面文字：{ktxt}")
            last_opt, last_opt_t = nk, t
            last_opt_idx = len(out) - 1
            continue
        if kind == "obj":
            if any(s in data for s in ("全域镇卫·逆捍谬罚", "坏灭肇始之时", "寄自彼岸的昨日")):
                continue
            obj_txt = clean_body(data)
            if obj_txt == last_obj and t - last_obj_t <= 120:
                last_obj_t = t
                continue
            out.append(f"[{hms(t)}] 画面文字：任务目标·{obj_txt}")
            last_obj, last_obj_t = obj_txt, t
            continue
        if kind == "tip":
            t2 = clean_body(data["title"]) if data["title"] else ""
            u2 = clean_body(data["unit"]) if data["unit"] else ""
            head_txt = f"{t2}｜{u2}" if u2 else t2
            head_txt = head_txt.replace("]」", "」").replace("］」", "」").replace("】", "」")
            head_txt = re.sub(r"茶[词诃]之(座)?$", "", head_txt)
            if head_txt.count("「") > head_txt.count("」"):
                head_txt += "」" * (head_txt.count("「") - head_txt.count("」"))
            if head_txt not in drop and len(norm(head_txt)) >= 3:
                out.append(f"[{hms(t)}] 画面文字：{head_txt}")
            for para in data["body"].split("\n"):
                para = clean_body(para)
                if para and para not in drop and len(norm(para)) >= 3:
                    out.append(f"[{hms(t)}] 画面文字：{para}")
            continue
        if kind == "map":
            head2 = clean_body(data["head"])
            body2 = clean_body(data["body"])
            if head2:
                emit_screen(t, head2, False)
            if body2:
                emit_screen(t, body2, False)
            for nm2 in data["names"]:
                emit_screen(t, f"救援目标·{nm2}", False)
            continue
        if kind == "desc":
            title2 = clean_body(data["title"])
            body2 = clean_body(data["body"])
            if not body2 and not title2:
                continue
            emit_screen(t, f"{title2}｜{body2}" if title2 and body2 else (body2 or title2), False)
            continue
        body = clean_body(data["body"])
        if not body:
            continue
        name = data.get("name", "")
        if any(w in name for w in ("点击", "跳过", "领取", "奖励", "追踪", "已开启")):
            name = ""
        # 字卡标题被误当说话人（如「圣土化的影响」），正文本身已含该标题
        if name and len(norm(name)) >= 4 and norm(body).startswith(norm(name)):
            name = ""
        # 名牌被并进正文（如「石头：石头「解翠行」老板…」），去掉正文开头的重复名字
        if name and nkey(name) in name_set and len(norm(name)) >= 2:
            nb, nn = norm(body), norm(name)
            if nb.startswith(nn) and len(nb) - len(nn) >= 3:
                i = cnt = 0
                while i < len(body) and cnt < len(nn):
                    if body[i] not in "「」『』[]［］·…，、。！？:： ":
                        cnt += 1
                    i += 1
                body = body[i:].lstrip("：:，,、 」』]］")
        if body.startswith("成就达成"):
            rest = body[4:].lstrip("：: ")
            if rest:
                emit_screen(t, f"成就达成｜{rest}")
            continue
        if nkey(name) in drop_name:
            # 名牌实为地图标签/界面残留：不删台词，降级为画面文字
            emit_screen(t, (clean_body(name) + "｜" + body) if body else clean_body(name))
            continue
        if any(w in body for w in ("退出行动", "再次行动", "选择行动")):
            continue
        if nkey(name) == "偕续试炼":
            emit_screen(t, body)
            continue
        if nkey(name) in unknown_name:
            name = "???"
        if data.get("kind") == "screen" or not name:
            sp = split_speaker(body)
            if sp:
                out.append(f"[{hms(t)}] {sp[0]}：{sp[1]}")
            else:
                emit_screen(t, body)
        elif name in ("元素反应", "战斗天赋", "角色培养"):
            emit_screen(t, f"{name}｜{body}")
        elif ("·" in name or "." in name) and nkey(name).rstrip("·.…") not in name_set:
            # 教学卡标题被当成说话人（如「圣土化的影响.·.」），按画面文字输出正文
            emit_screen(t, body)
        elif re.search(r"[…·]$", name):
            emit_screen(t, f"{clean_body(name.rstrip('…·'))}……{body}")
        else:
            out.append(f"[{hms(t)}] {name}：{body}")

    out = [x for x in out if x]
    out = restore_device_label(out)
    out = balance_quotes(out)
    out = dedupe_screen(final_fix(out))
    out = merge_ono(out)
    out = dedupe_lines(out)
    out = drop_echo_screen(out)
    report = {"key": key, "title": title, "fixes": hits, "review": review, "unmatched": miss}
    return "\n".join(out) + "\n", report

def main(keys=None):
    out_dir = paths.ensure_work("txt", "final")
    align_dir = paths.ensure_work("align")
    wl = build_whitelist()
    written = []
    for key, title, filename, dur in VIDEOS:
        if keys and key not in keys:
            continue
        if not os.path.exists(paths.work("ocr", key + ".jsonl")):
            print("MISSING", key)
            continue
        text, rep = build(key, title, filename, dur, wl)
        dst = os.path.join(out_dir, f"{key}_{title}.txt")
        with open(dst, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        with open(os.path.join(align_dir, key + ".json"), "w", encoding="utf-8", newline="\n") as handle:
            json.dump(rep, handle, ensure_ascii=False, indent=1)
        written.append(dst)
        print(f"{key}: {len(rep['fixes'])} fixes, {len(rep['review'])} review, {len(rep['unmatched'])} unmatched")
    return written

if __name__ == "__main__":
    main(sys.argv[1:] or None)
