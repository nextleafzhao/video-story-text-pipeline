"""Merge per-second OCR frames into a dialogue timeline.

band: subtitle band (1360x230, crop y780-1010)
opt:  dialogue option strip (520x130, crop x1140-1660 y690-820)
panel: quest panel (620x136, crop x0-620 y224-360)
"""
import json, re, sys, os
from collections import Counter

PUNCT_RE = re.compile(r"[，。！？、…：；,.!?·]")

def norm(s):
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", s or "")

def fix_brackets(s):
    return (s or "").replace("】", "」").replace("]", "」").replace("］", "」").replace("】", "」").replace("【", "「").replace("[", "「").replace("［", "「").replace("〔", "「")

def tidy(s):
    s = s.strip()
    s = re.sub(r"[·]{2,}", "…", s)
    s = re.sub(r"[，,]{2,}", "，", s)
    s = re.sub(r"[。]{2,}", "。", s)
    s = re.sub(r"[？?]{2,}", "？", s)
    s = re.sub(r"[！!]{2,}", "！", s)
    s = s.replace("，，", "，").replace("··", "…")
    if re.search(r"[\u4e00-\u9fff]", s):
        s = re.sub(r"\.$", "。", s)
    return s.strip()

def _sim(a, b):
    ca = Counter(a[i:i+2] for i in range(len(a)-1))
    cb = Counter(b[i:i+2] for i in range(len(b)-1))
    inter = sum((ca & cb).values())
    return 2*inter/(max(1, len(a)-1)+max(1, len(b)-1))

def _subseq(a, b):
    """a appears inside b as an ordered subsequence, allowing inserted chars"""
    it = iter(b)
    return all(c in it for c in a)

def rows_of_boxes(lines):
    """Group OCR boxes into visual rows (y overlap), order rows top->bottom."""
    rows = []
    for z in sorted(lines, key=lambda z: (z[0], z[1])):
        placed = False
        for r in rows:
            if min(r[0][2], z[2]) - max(r[0][0], z[0]) > 0.4 * min(z[2]-z[0], r[0][2]-r[0][0]):
                r.append(z); placed = True; break
        if not placed:
            rows.append([z])
    rows.sort(key=lambda r: min(z[0] for z in r))
    return rows

def rows_of(lines):
    rows = rows_of_boxes(lines)
    return ["".join(z[4] for z in sorted(r, key=lambda z: z[1])) for r in rows]

NUM_RE = re.compile(r"^[+\-]?[0-9]+(%|/[0-9]+)?$")
DIST_RE = re.compile(r"^[0-9]+(\.[0-9]+)?m$", re.I)
NAV_RE = re.compile(r"^[上下一]?[页頁]$")
NAV_WORDS = {"成就达成"}

def band_lines(lines):
    """filtered, sorted OCR boxes of the subtitle band"""
    ls = [z for z in lines if not (len(z[4]) <= 1 and z[5] < 0.8)]
    ls = [z for z in ls if re.search(r"[\u4e00-\u9fffA-Za-z0-9]", z[4])]
    ls = [z for z in ls if not (z[1] >= 700 and z[0] < 60)]
    ls = [z for z in ls if not NUM_RE.match(z[4].strip()) and not DIST_RE.match(z[4].strip())]
    ls = [z for z in ls if not NAV_RE.match(z[4].strip()) and z[4].strip() not in NAV_WORDS]
    ls.sort(key=lambda z: (z[0], z[1]))
    return ls

def name_candidate(lines):
    ls = band_lines(lines)
    if not ls:
        return ""
    top = ls[0]
    cand = clean_name(top[4])
    rest = ls[1:]
    if (len(cand) <= 14 and not SENT_PUNCT.search(cand)
            and not re.search(r"点击|继续|跳过|领取|奖励|追踪|已开启|成就|挑战", cand)
            and (not rest or rest[0][0] - top[2] >= 5 or len(rest[0][4]) >= 12)):
        return cand
    return ""

def clean_name(s):
    s = fix_brackets(s.strip())
    s = re.sub(r"^[^「\u4e00-\u9fff]+", "", s)
    return s.strip()

SENT_PUNCT = re.compile(r"[，。！？、…：；,!?]")
TITLE_END = "员长宫女士使卿师者人匠兵商家王公侯伯督相令卫官队节军尉士徒手臣爵侍从仆役书部事守领察祭头代探心」司老"

def is_title(s):
    """NPC 对话界面的职位行，如「修女」「情报交易员」「拂晓的枢机卿」"""
    # OCR 常把行尾的」认成］/】/』，先归一化括号再判断，否则称号会被并进正文
    s = fix_brackets((s or "").strip())
    t = nkey(s).strip()
    if not t or len(t) > 8 or SENT_PUNCT.search(t):
        return False
    if s.startswith("「") and "」" in s:
        return True
    return t[-1] in TITLE_END


def is_plate(s):
    """铭牌上的机体/装备称号可能超过 8 字，如「超重型陆巡舰·机动战垒改」。"""
    s = fix_brackets((s or "").strip())
    t = nkey(s).strip()
    return bool(t) and len(t) <= 16 and not SENT_PUNCT.search(t) and "·" in s

def parse_band(lines, wl):
    """-> (name, body, heading, quality, is_name_only)"""
    ls = band_lines(lines)
    if not ls:
        return "", "", "", 0, False
    name, heading, body_ls = "", "", ls
    top = ls[0]
    cand = clean_name(top[4])
    rest = ls[1:]
    cand_ok = bool(cand) and len(cand) <= 14 and not SENT_PUNCT.search(cand)
    m = match_wl(cand, wl) if cand_ok else None
    slot = (cand_ok and (not rest or rest[0][0] - top[2] >= 4 or len(rest[0][4]) >= 12))
    if slot and not rest:
        if m:
            return cand, "", "", top[5], True
        return "", cand, "", top[5], False
    if len(rest) >= 2 and cand_ok and (is_title(rest[0][4]) or is_plate(rest[0][4])):
        # 职位牌（如「野蛮熊」一把手 / 千岩军中队长）也要收录，不能吞掉
        name, body_ls = cand, rest[1:]
        heading = clean_name(rest[0][4])
    elif (len(rest) == 1 and cand_ok and not is_title(cand)
            and is_title(rest[0][4]) and len(nkey(rest[0][4])) >= 3):
        # 只有两行（姓名 + 称号），正文「……」没有被 OCR 识别到：保留说话人与称号
        return cand, "", clean_name(rest[0][4]), top[5], True
    elif slot or (m and m == nkey(cand)):
        # 已确认是说话人时，即使名牌与正文间距过小、正文又短，也不能当标题吞掉
        # （如「众千岩军」「愚人众士兵」「优菈」）
        if m:
            name = cand if m == nkey(cand) else m
            body_ls = rest
        else:
            heading = cand
            body_ls = rest
    if body_ls:
        rows = rows_of_boxes(body_ls)
        r0 = rows[0]
        h0 = max(z[2] for z in r0) - min(z[0] for z in r0)
        # 仅当还没有 heading 时，才把首行当标题吃掉；否则首行是正文，必须保留
        if len(rows) >= 2 and min(z[0] for z in r0) < 70 and h0 <= 24 and not heading:
            heading = "".join(z[4] for z in sorted(r0, key=lambda z: z[1]))
            body_ls = [z for r in rows[1:] for z in r]
    body = "".join(rows_of(body_ls)) if body_ls else ""
    if name and body:
        body = re.sub(r"^[「『\[]?%s[」』\]]?[：:，,、]?\s*" % re.escape(nkey(name)), "", body).lstrip()
    q = min(z[5] for z in body_ls) if body_ls else (top[5] if not body else 0)
    return name, body, heading, q, False

def parse_opt(lines):
    ls = [z for z in lines if len(z[4].strip()) >= 2 and z[5] >= 0.6]
    ls.sort(key=lambda z: z[0])
    out, seen = [], set()
    for z in ls:
        t = tidy(z[4])
        k = norm(t)
        if k and k not in seen:
            seen.add(k); out.append(t)
    return out

def parse_panel(lines):
    ls = [z for z in lines if len(z[4].strip()) >= 2 and z[5] >= 0.6]
    ls.sort(key=lambda z: (z[0], z[1]))
    return tidy("".join(z[4] for z in ls))

def parse_desc(lines):
    """right-side info panel: title on top, wrapped body below"""
    ls = [z for z in lines if len(z[4].strip()) >= 2 and z[5] >= 0.55]
    ls.sort(key=lambda z: (z[0], z[1]))
    if not ls:
        return "", ""
    title_ls = [z for z in ls if z[0] < 70]
    body_ls = [z for z in ls if z[0] >= 70]
    title = tidy("".join(z[4] for z in sorted(title_ls, key=lambda z: z[1])))
    body = "".join(rows_of(body_ls)) if body_ls else ""
    if len(norm(body)) < 8 and len(norm(title)) < 8:
        return "", ""
    return title, body

def add_screen(out, t, text, q):
    if not text:
        return
    ck = norm(text)
    for p in reversed(out[-2:]):
        if p.get("kind") != "screen":
            continue
        pk = norm(p["body"])
        if (pk == ck or (len(pk) >= 3 and len(ck) >= 3 and (ck.startswith(pk) or pk.startswith(ck) or _sim(pk, ck) >= 0.9))) and t - p["end"] <= 3:
            p["end"] = t
            if len(ck) > len(pk):
                p["body"] = text
            return
    out.append({"t": t, "end": t, "name": "", "body": text, "q": q, "kind": "screen"})

def nkey(s):
    return re.sub(r"[「」『』]", "", s or "")

def match_wl(cand, wl):
    """把 OCR 认出的姓名候选映射到白名单条目（先精确，再近似）。

    近似匹配必须**确定性**且**拒绝歧义**：
      - wl 是 set，直接遍历的命中顺序随 PYTHONHASHSEED 变化，会让同一份
        OCR 数据每次跑出不同的说话人（20 段的匿叶龙「波奇奇」曾被随机
        认成基尼奇/西蒙·佩奇/班尼特/林尼…）。所以先 sorted() 再遍历。
      - 同一候选命中多个白名单条目时，说明证据不足，直接判为无匹配，
        不再取「第一个命中的」。
      - 多候选时优先取「包含度」更高、长度更接近的那个，仍然并列则弃权。
    """
    k = nkey(cand)
    if k in wl:
        return k
    # 界面标签（含「·」）与纯重复字符（如「哈哈哈哈哈」）不做模糊映射，
    # 否则会被误认成某个说话人，进而把无名牌台词错配姓名
    if "·" in k or re.match(r"^(.)\1{3,}$", k):
        return None
    if len(k) >= 3:
        hits = []
        for w in sorted(wl):
            if len(w) - len(k) > 2 or len(k) - len(w) > 1:
                continue
            cover = sum(1 for c in k if c in w) / len(k)
            if cover >= 0.6:
                # 排序键：包含度降序、长度差升序、字典序兜底
                hits.append((-round(cover, 4), abs(len(w) - len(k)), w))
        if not hits:
            return None
        hits.sort()
        # 并列第一（包含度与长度差都相同）→ 歧义，弃权
        if len(hits) > 1 and hits[0][:2] == hits[1][:2]:
            return None
        return hits[0][2]
    return None

def collect_candidates(records):
    """candidate -> number of separate appearances (for speaker whitelist)"""
    cnt = {}
    last, seg_last_t = "", -9
    for r in records:
        c = name_candidate(r.get("band") or [])
        if not c:
            continue
        c = nkey(c)
        if c == last and r["t"] - seg_last_t <= 2:
            seg_last_t = r["t"]
            continue
        cnt[c] = cnt.get(c, 0) + 1
        last, seg_last_t = c, r["t"]
    return cnt

def collect_frames(records):
    """candidate -> 出现帧数；只统计名牌下方确实跟着台词的那些帧"""
    cnt = Counter()
    for r in records:
        c = name_candidate(r.get("band") or [])
        if not c:
            continue
        ls = band_lines(r.get("band") or [])
        body = "".join(rows_of(ls[1:])) if ls[1:] else ""
        if len(norm(body)) < 8:
            continue
        cnt[nkey(c)] += 1
    return cnt

def merge(records, wl=frozenset()):
    out, opts, descs = [], [], []
    prev_opt = []
    prev_desc = None
    for r in records:
        t = r["t"]
        name, body, heading, q, name_only = parse_band(r.get("band") or [], wl)
        dt, db = parse_desc(r.get("desc") or [])
        dk = norm(dt + db)
        if dk and len(dk) >= 4:
            if (prev_desc and t - prev_desc["end"] <= 3
                    and (dk == prev_desc["k"] or _sim(dk, prev_desc["k"]) >= 0.85)):
                prev_desc["end"] = t
                if len(dk) > len(prev_desc["k"]):
                    prev_desc.update(k=dk, title=dt, body=db)
            else:
                prev_desc = {"t": t, "end": t, "k": dk, "title": dt, "body": db}
                descs.append(prev_desc)
        o = parse_opt(r.get("opt") or [])
        if o:
            if prev_opt and set(map(norm, o)) == set(map(norm, prev_opt)) and opts and opts[-1]["end"] >= t-1:
                opts[-1]["end"] = t
            elif prev_opt and set(map(norm, o)).issubset(set(map(norm, prev_opt))) and opts and opts[-1]["end"] >= t-1:
                opts[-1]["end"] = t
            else:
                opts.append({"t": t, "end": t, "texts": o})
            prev_opt = o
        else:
            prev_opt = []
        if heading:
            add_screen(out, t, heading, q)
            if not body and not name:
                continue
        if not body:
            if name:
                if out and out[-1].get("pending"):
                    if len(name) >= len(out[-1]["name"]):
                        out[-1]["name"] = name
                        out[-1]["end"] = t
                else:
                    out.append({"t": t, "end": t, "name": name, "body": "", "q": q, "pending": True, "kind": "line"})
            continue
        # 中间可能插入标题/称号的 screen 条目，待定台词要看最后一条 line
        pend = None
        for o in reversed(out):
            if o.get("kind", "line") == "line":
                pend = o
                break
        if pend and pend.get("pending"):
            p = pend
            if name and norm(name) != norm(p["name"]):
                p["pending"] = False
                if not p["body"]:
                    p["body"] = "……"
            else:
                p["pending"] = False
                p["body"] = body; p["q"] = q; p["end"] = t
                p["name"] = p["name"] or name
                continue
        if out and out[-1].get("kind", "line") == "line":
            prev = out[-1]
            pk, ck = norm(prev["body"]), norm(body)
            same = False
            if pk == ck:
                same = True
            elif len(pk) >= 2 and len(ck) >= 2:
                if ck.startswith(pk) or pk.startswith(ck):
                    same = True
                elif _subseq(pk, ck) and len(ck) - len(pk) <= (12 if len(pk) >= 6 else 4):
                    same = True
                elif len(ck) > len(pk) and _sim(pk, ck[:len(pk)+2]) >= 0.85:
                    same = True
                elif len(pk) > len(ck) and _sim(ck, pk[:len(ck)+2]) >= 0.85:
                    same = True
                elif abs(len(pk)-len(ck)) <= 4 and _sim(pk, ck) >= 0.85:
                    same = True
                elif abs(len(pk)-len(ck)) >= 3 and _sim(pk, ck) >= 0.5:
                    same = True
                elif len(pk) <= 9 and len(ck) > len(pk) and ck.startswith(pk[:4]):
                    same = True
            if same and t - prev["end"] <= 3:
                pn, cn = nkey(prev.get("name", "")), nkey(name)
                # 短促的语气词/专有名词独立成句，若下句换了说话人则不合并
                if pn and cn and pn != cn and len(pk) <= 8 and len(ck) > len(pk):
                    out.append({"t": t, "end": t, "name": name, "body": body, "q": q, "kind": "line"})
                    continue
                prev["end"] = t
                if len(ck) > len(pk):
                    nm = prev.get("name")
                    if nm:
                        body = re.sub(r"^[「『\[]?%s[」』\]]?[：:，,、]?\s*" % re.escape(nkey(nm)), "", body).lstrip()
                    prev["body"] = body; prev["q"] = q
                if name and len(name) >= len(prev.get("name", "")):
                    prev["name"] = name
                continue
        out.append({"t": t, "end": t, "name": name, "body": body, "q": q, "kind": "line"})
    for o in out:
        o.pop("pending", None)
    return out, opts, descs

def run(path, out):
    recs = [json.loads(l) for l in open(path, encoding="utf-8")]
    lines, opts, descs = merge(recs)
    json.dump({"lines": lines, "opts": opts, "descs": descs}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{os.path.basename(path)}: {len(recs)} frames -> {len(lines)} lines, {len(opts)} option groups, {len(descs)} info panels")
    for l in lines[:20]:
        print(f'  [{l["t"]}-{l["end"]}] {l["name"]}｜{l["body"]}')
    for o in opts[:10]:
        print(f'  OPT [{o["t"]}-{o["end"]}] {" / ".join(o["texts"])}')

if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2])
