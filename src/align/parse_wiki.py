"""Parse BWiki quest raw pages into structured JSON."""
import re, json, os, glob, sys

RAW = "BWiki/raw"
OUT = "BWiki/json"

def split_params(s):
    parts, depth, cur, i = [], 0, [], 0
    while i < len(s):
        if s.startswith("{{", i) or s.startswith("[[", i):
            depth += 1; cur.append(s[i:i+2]); i += 2; continue
        if s.startswith("}}", i) or s.startswith("]]", i):
            depth -= 1; cur.append(s[i:i+2]); i += 2; continue
        if s[i] == "|" and depth == 0:
            parts.append("".join(cur)); cur = []; i += 1; continue
        cur.append(s[i]); i += 1
    parts.append("".join(cur))
    return parts

def clean_link(t):
    t = re.sub(r"\[\[([^\]|]*)\|([^\]]*)\]\]", r"\2", t)
    t = re.sub(r"\[\[([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"<[^>]+>", "", t)
    return t.strip()

def parse_icons(s):
    """{{图标|摩拉|31125}} -> 摩拉×31125"""
    def rep(m):
        ps = split_params(m.group(1))
        name = ps[1] if len(ps) > 1 else ""
        num = ps[2] if len(ps) > 2 else ""
        return f"{name}×{num}" if num else name
    return re.sub(r"\{\{图标\|([^}]*)\}\}", rep, s)

def parse_meta(text):
    m = re.search(r"\{\{任务\n(.*?)\n\}\}", text, re.S)
    if not m:
        return {}, ""
    body = m.group(1)
    meta = {}
    key = None
    for line in body.split("\n"):
        if "=" in line and not line.strip().startswith("*"):
            k, v = line.split("=", 1)
            key = k.strip().lstrip("|").strip()
            meta[key] = v.strip()
        elif key and line.strip():
            meta[key] = (meta[key] + "\n" + line).strip()
    rest = text[m.end():]
    return meta, rest

def parse_flow(meta):
    f = meta.get("任务流程", "")
    return [clean_link(x.lstrip("*").strip()) for x in f.split("\n") if x.strip().startswith("*")]

def parse_sections(rest):
    sections = []
    cur = {"title": "任务剧情", "level": 2, "items": []}
    lines = rest.split("\n")
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^(=+)\s*(.*?)\s*(=+)$", ln)
        if m and len(m.group(1)) >= 2:
            lvl = len(m.group(1))
            if cur["items"] or cur["title"] != "任务剧情":
                sections.append(cur)
            cur = {"title": clean_link(m.group(2)), "level": lvl, "items": []}
            i += 1; continue
        s = ln.strip()
        if s.startswith("{{剧情选项"):
            buf = s
            while buf.count("{{") > buf.count("}}") and i + 1 < len(lines):
                i += 1; buf += "\n" + lines[i]
            ps = split_params(buf[2:-2] if buf.endswith("}}") else buf[2:])
            opts = []
            for p in ps[1:]:
                if "=" in p:
                    k, v = p.split("=", 1)
                    if k.strip().startswith("选项"):
                        opts.append(clean_link(v.strip()))
            if opts:
                cur["items"].append({"t": "opt", "opts": opts})
            i += 1; continue
        if s == "-----":
            cur["items"].append({"t": "sep"})
            i += 1; continue
        if s.startswith("::"):
            txt = clean_link(re.sub(r"\{\{颜色\|[^|]*\|", "", s.lstrip(":")))
            txt = txt.rstrip("}")
            if txt:
                cur["items"].append({"t": "note", "tx": txt})
            i += 1; continue
        if s.startswith("*") and not s.startswith("**"):
            body = s.lstrip("*").strip()
            mm = re.match(r"^([^：:]{1,16})[：:](.*)$", body)
            if mm:
                sp, tx = mm.group(1).strip(), mm.group(2).strip()
            else:
                sp, tx = "", body
            # fix wiki typo: *「木偶」那东西——
            if not sp and body.startswith("「"):
                mm2 = re.match(r"^(「[^」]*」)(.*)$", body)
                if mm2:
                    sp, tx = mm2.group(1), mm2.group(2)
            if tx:
                cur["items"].append({"t": "line", "sp": sp, "tx": clean_link(tx)})
            i += 1; continue
        i += 1
    if cur["items"]:
        sections.append(cur)
    return sections

def parse_file(path):
    text = open(path, encoding="utf-8").read()
    meta, rest = parse_meta(text)
    page = os.path.basename(path)[:-4]
    return {
        "page": page,
        "meta": {
            "名称": meta.get("任务名称", page),
            "版本": meta.get("所属版本", ""),
            "类型": meta.get("任务类型", ""),
            "地区": meta.get("任务地区", ""),
            "描述": clean_link(meta.get("任务描述", "")),
            "条件": clean_link(meta.get("任务条件", "")),
            "等级": meta.get("开放等级", ""),
            "奖励": clean_link(parse_icons(meta.get("奖励", ""))),
            "成就": clean_link(meta.get("相关成就", "")),
            "系列": clean_link(meta.get("系列任务", "")),
            "编号": meta.get("任务编号", ""),
            "出场": clean_link(meta.get("出场人物", "")),
        },
        "flow": parse_flow(meta),
        "sections": parse_sections(rest),
    }

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for p in sorted(glob.glob(os.path.join(RAW, "*.raw"))):
        if os.path.getsize(p) < 500:
            continue
        d = parse_file(p)
        out = os.path.join(OUT, d["page"] + ".json")
        json.dump(d, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        nl = sum(1 for s in d["sections"] for it in s["items"] if it["t"] == "line")
        print(f'{d["page"]}: meta={d["meta"]["名称"]} sections={len(d["sections"])} lines={nl} flow={len(d["flow"])}')
