#!/usr/bin/env python3
"""Valida existência real de handles do Telegram via t.me (público, sem login)."""
import re, sys, json, urllib.request, urllib.error, concurrent.futures

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36"

def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en,pt;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")
    except Exception as e:
        return None, f"ERR:{e}"

def parse(html):
    if not html or html.startswith("ERR:"):
        return {"title": None, "desc": None, "extra": None, "exists": False}
    exists = "tgme_page_title" in html
    t = re.search(r'tgme_page_title"[^>]*>\s*<span[^>]*>(.*?)</span>', html, re.S)
    d = re.search(r'tgme_page_description[^>]*>(.*?)</div>', html, re.S)
    e = re.search(r'tgme_page_extra">(.*?)</div>', html, re.S)
    def clean(x):
        if not x: return None
        return re.sub(r"<[^>]+>", "", x.group(1)).strip()
    return {"title": clean(t), "desc": clean(d), "extra": clean(e), "exists": exists}

def check(handle, kind):
    handle = handle.lstrip("@")
    out = {"handle": handle, "kind": kind}
    st, html = fetch(f"https://t.me/{handle}")
    out["http_main"] = st
    p = parse(html)
    out.update({"exists": p["exists"], "title": p["title"], "extra": p["extra"], "desc": p["desc"]})
    if kind == "channel":
        st2, h2 = fetch(f"https://t.me/s/{handle}")
        out["http_s"] = st2
        # count posts markers
        out["posts"] = len(re.findall(r'data-post="', h2 or ""))
    return out

if __name__ == "__main__":
    jobs = json.load(sys.stdin)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        res = list(ex.map(lambda j: check(j[0], j[1]), jobs))
    print(json.dumps(res, ensure_ascii=False, indent=2))
