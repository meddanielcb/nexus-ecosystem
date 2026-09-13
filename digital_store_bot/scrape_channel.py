#!/usr/bin/env python3
"""Baixa t.me/s/<canal> e extrai texto limpo das mensagens recentes."""
import re, sys, urllib.request, html as htmlmod

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36"

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "ignore")

def text_of(channel):
    h = get(f"https://t.me/s/{channel}")
    # cada mensagem fica em div class="tgme_widget_message_text ..."
    blocks = re.findall(r'tgme_widget_message_text[^>]*>(.*?)</div>', h, re.S)
    out = []
    for b in blocks:
        b = re.sub(r"<br\s*/?>", "\n", b)
        b = re.sub(r"<[^>]+>", "", b)
        b = htmlmod.unescape(b).strip()
        if b:
            out.append(b)
    return out

if __name__ == "__main__":
    for ch in sys.argv[1:]:
        try:
            msgs = text_of(ch)
        except Exception as e:
            print(f"### {ch}: ERRO {e}\n")
            continue
        print(f"\n########## t.me/{ch}  ({len(msgs)} mensagens) ##########")
        for m in msgs[-12:]:
            print("- " + m.replace("\n", " | ")[:600])
