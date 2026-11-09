"""Fetch wiki page source (action=raw) for given titles.

Usage:
  python fetch_wiki.py <wiki-base-url> title1 title2 ...
  e.g. python fetch_wiki.py "https://wiki.biligame.com/ys" 任务标题1 任务标题2
"""
import urllib.parse, subprocess, os, time, sys

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "work", "wiki_raw")
os.makedirs(RAW, exist_ok=True)


def get(base, title):
    url = base.rstrip("/") + "/" + urllib.parse.quote(title) + "?action=raw"
    p = subprocess.run(["curl", "-sS", "-m", "60", "-A", UA, url], capture_output=True)
    return p.stdout


def ok(data):
    if not data or len(data) < 20:
        return False
    head = data[:200].lstrip()
    return not head.startswith(b"<!doctype") and b"EdgeOne" not in data[:4000]


def main():
    if len(sys.argv) < 3:
        print("usage: python fetch_wiki.py <wiki-base-url> title1 title2 ...")
        return
    base = sys.argv[1]
    titles = sys.argv[2:]
    for t in titles:
        out = os.path.join(RAW, t.replace("/", "_") + ".raw")
        if os.path.exists(out) and os.path.getsize(out) > 20:
            print("SKIP", t, flush=True)
            continue
        for attempt in range(4):
            d = get(base, t)
            if ok(d):
                open(out, "wb").write(d)
                print("OK", t, len(d), flush=True)
                break
            print("BLOCKED", t, len(d), "attempt", attempt, flush=True)
            time.sleep(20 + attempt * 15)
        time.sleep(4.5)


if __name__ == "__main__":
    main()
