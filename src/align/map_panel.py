"""行动模式段右侧常驻任务面板的解析。

采集由 map_ocr.py 完成，产物 work/map/<key>.jsonl。

用法: python map_panel.py <key>      # 打印解析结果
"""
import json, os, re, sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.common import paths
from src.merge.merge import tidy, norm, rows_of_boxes, _sim

KEYS = ("17_qy9",)

# 行动面板上的常驻按钮/提示，不是正文 —— 按游戏调整
PANEL_UI = ()
# 面板正文里属于「救援目标」小标题的行
RESCUE_HEAD = "救援目标"


def panel_rows(boxes):
    rows = []
    for r in rows_of_boxes([tuple(b) for b in boxes]):
        r = sorted(r, key=lambda z: z[1])
        rows.append((min(z[0] for z in r), "".join(z[4] for z in r)))
    rows.sort()
    return rows


def panel_content(boxes):
    """-> (区域标题, 正文, [救援目标人名]) 或 None"""
    rows = [(y, tidy(t)) for y, t in panel_rows(boxes)]
    rows = [(y, t) for y, t in rows if t and not any(u in t for u in PANEL_UI)]
    if not rows:
        return None
    head = ""
    body, names = [], []
    in_rescue = False
    for y, t in rows:
        if not head:
            # 面板顶部是行动名「急刻进救」，下面是「急刻进救·区域名」
            if "急刻进救·" in t:
                head = t
                continue
            continue
        if t == RESCUE_HEAD or t.replace(" ", "") == RESCUE_HEAD:
            in_rescue = True
            continue
        if in_rescue:
            # 救援目标名单是纯人名，2–5 个汉字
            if re.fullmatch(r"[\u4e00-\u9fff]{2,5}", t):
                names.append(t)
            continue
        body.append(t)
    if not head or len(norm("".join(body))) < 15:
        return None
    return head, "".join(body), names


def load(key):
    """-> [{"t": 秒, "head": 区域标题, "body": 战况说明, "names": [救援目标]}]"""
    p = paths.work("map", key + ".jsonl")
    if not os.path.exists(p):
        return []
    recs = [json.loads(l) for l in open(p, encoding="utf-8")]
    items, prev = [], None
    for r in recs:
        pc = panel_content(r.get("map") or [])
        if not pc:
            continue
        k = norm(pc[0] + pc[1])
        # 同一块面板连续显示：标题相同且正文高度相似就并进上一条
        if items and pc[0] == items[-1]["head"] and (
                k == prev or prev in k or k in prev
                or _sim(k, prev or "") >= 0.9):
            if len(k) > len(norm(items[-1]["head"] + items[-1]["body"])):
                items[-1].update(body=pc[1], names=pc[2])
            prev = max(prev or "", k, key=len)
            continue
        prev = k
        items.append({"t": r["t"], "head": pc[0], "body": pc[1], "names": pc[2]})
    return items


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    for it in load(sys.argv[1]):
        print(it["t"], repr(it["head"]), repr(it["body"])[:100], it["names"])


if __name__ == "__main__":
    main()
