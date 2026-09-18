#!/usr/bin/env python3
"""
Nexus PlayTV — EPG Daemon & Micro-API
Indexa o feed XMLTV do upstream em SQLite e serve consultas em < 2ms.
"""

import os
import re
import time
import json
import sqlite3
import datetime
import urllib.request
import xml.etree.ElementTree as ET
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

DB_PATH = "/var/www/play.nexusplay.tv_beta/epg.db"
UPSTREAM_XMLTV = "http://atmt.space/xmltv.php?username=sc0u6zlg&password=66355054"
PORT = 5056

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS channels (
        id TEXT PRIMARY KEY,
        display_name TEXT,
        icon_slug TEXT,
        name_slug TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS programmes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT,
        title TEXT,
        description TEXT,
        start_ts INTEGER,
        stop_ts INTEGER
    )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_prog_chan_time ON programmes(channel_id, start_ts, stop_ts)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_chan_icon_slug ON channels(icon_slug)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_chan_name_slug ON channels(name_slug)")
    conn.commit()
    conn.close()

def make_slug(s):
    if not s:
        return ""
    # Remove tags comuns de IPTV (4K, FHD, HD, SD, 24H, BR, LOCAL, etc.)
    s = re.sub(r"\b(4k|fhd|hd|sd|hevc|uhd|h265|24h|local|vip|tv|brasil|br)\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"[^a-zA-Z0-9]+", "", s).lower()
    return s

def parse_xmltv_date(ds):
    if not ds:
        return 0
    m = re.match(r"^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})\s*([+-]\d{4})?", ds)
    if not m:
        return 0
    y, mo, d, h, mi, s, tz = m.groups()
    tz_obj = datetime.timezone.utc
    if tz:
        sign = 1 if tz[0] == "+" else -1
        tzh = int(tz[1:3])
        tzm = int(tz[3:5])
        tz_obj = datetime.timezone(sign * datetime.timedelta(hours=tzh, minutes=tzm))
    dt = datetime.datetime(int(y), int(mo), int(d), int(h), int(mi), int(s), tzinfo=tz_obj)
    return int(dt.timestamp())

def sync_epg():
    print(f"[{datetime.datetime.now()}] Iniciando sincronização EPG XMLTV...")
    req = urllib.request.Request(UPSTREAM_XMLTV, headers={"User-Agent": "IPTVSmartersPro/2.2.2"})
    
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            conn = get_db()
            c = conn.cursor()
            c.execute("DELETE FROM programmes")
            c.execute("DELETE FROM channels")
            
            chan_batch = []
            prog_batch = []
            
            for event, elem in ET.iterparse(r, events=("end",)):
                if elem.tag == "channel":
                    cid = elem.get("id")
                    dname = elem.findtext("display-name") or cid
                    
                    # Extrai o slug do ícone
                    icon_slug = ""
                    icon_elem = elem.find("icon")
                    if icon_elem is not None and icon_elem.get("src"):
                        src = icon_elem.get("src")
                        base = os.path.splitext(os.path.basename(src))[0]
                        icon_slug = make_slug(base)
                    
                    name_slug = make_slug(dname) or make_slug(cid)
                    chan_batch.append((cid, dname, icon_slug, name_slug))
                    
                    if len(chan_batch) >= 500:
                        c.executemany("INSERT OR REPLACE INTO channels (id, display_name, icon_slug, name_slug) VALUES (?, ?, ?, ?)", chan_batch)
                        chan_batch = []
                    elem.clear()
                elif elem.tag == "programme":
                    cid = elem.get("channel")
                    start = parse_xmltv_date(elem.get("start"))
                    stop = parse_xmltv_date(elem.get("stop"))
                    title = elem.findtext("title") or ""
                    desc = elem.findtext("desc") or ""
                    prog_batch.append((cid, title, desc, start, stop))
                    if len(prog_batch) >= 1000:
                        c.executemany("INSERT INTO programmes (channel_id, title, description, start_ts, stop_ts) VALUES (?, ?, ?, ?, ?)", prog_batch)
                        prog_batch = []
                    elem.clear()
                    
            if chan_batch:
                c.executemany("INSERT OR REPLACE INTO channels (id, display_name, icon_slug, name_slug) VALUES (?, ?, ?, ?)", chan_batch)
            if prog_batch:
                c.executemany("INSERT INTO programmes (channel_id, title, description, start_ts, stop_ts) VALUES (?, ?, ?, ?, ?)", prog_batch)
                
            conn.commit()
            
            c.execute("SELECT COUNT(*) FROM channels")
            n_chan = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM programmes")
            n_prog = c.fetchone()[0]
            conn.close()
            print(f"[{datetime.datetime.now()}] SUCESSO EPG: {n_chan} canais e {n_prog} programas indexados no SQLite!")
            return True
    except Exception as e:
        print(f"[{datetime.datetime.now()}] ERRO ao sincronizar EPG: {e}")
        return False

def query_epg(channel_name="", icon_url="", raw_id=""):
    conn = get_db()
    c = conn.cursor()
    now_ts = int(time.time())
    
    matched_id = None
    
    # 1. Tenta achar por ID direto
    if raw_id:
        c.execute("SELECT id FROM channels WHERE id = ?", (raw_id,))
        row = c.fetchone()
        if row:
            matched_id = row["id"]

    # 2. Tenta achar pelo ícone do canal
    if not matched_id and icon_url:
        icon_base = os.path.splitext(os.path.basename(icon_url))[0]
        islug = make_slug(icon_base)
        if islug:
            c.execute("SELECT id FROM channels WHERE icon_slug = ? LIMIT 1", (islug,))
            row = c.fetchone()
            if row:
                matched_id = row["id"]

    # 3. Tenta achar por slug do nome
    if not matched_id and channel_name:
        nslug = make_slug(channel_name)
        if nslug:
            # Match exato no icon_slug ou name_slug
            c.execute("SELECT id FROM channels WHERE icon_slug = ? OR name_slug = ? LIMIT 1", (nslug, nslug))
            row = c.fetchone()
            if row:
                matched_id = row["id"]
            else:
                # Match parcial
                c.execute("SELECT id FROM channels WHERE ? LIKE '%' || icon_slug || '%' OR icon_slug LIKE '%' || ? || '%' LIMIT 1", (nslug, nslug))
                row = c.fetchone()
                if row:
                    matched_id = row["id"]

    if not matched_id:
        conn.close()
        return {
            "found": False,
            "channel": channel_name,
            "current": {
                "title": "Transmissão Oficial Nexus",
                "desc": "Programação em tempo real em alta definição.",
                "start": "--:--",
                "stop": "--:--",
                "progress": 0
            },
            "upcoming": []
        }

    # Busca programa atual
    c.execute("""
        SELECT title, description, start_ts, stop_ts
        FROM programmes
        WHERE channel_id = ? AND start_ts <= ? AND stop_ts > ?
        ORDER BY start_ts DESC
        LIMIT 1
    """, (matched_id, now_ts, now_ts))
    cur_row = c.fetchone()

    # Se não tiver atual em andamento, pega o mais próximo
    if not cur_row:
        c.execute("""
            SELECT title, description, start_ts, stop_ts
            FROM programmes
            WHERE channel_id = ? AND start_ts > ?
            ORDER BY start_ts ASC
            LIMIT 1
        """, (matched_id, now_ts))
        cur_row = c.fetchone()

    # Próximos 6 programas
    c.execute("""
        SELECT title, description, start_ts, stop_ts
        FROM programmes
        WHERE channel_id = ? AND start_ts > ?
        ORDER BY start_ts ASC
        LIMIT 6
    """, (matched_id, now_ts))
    upcoming_rows = c.fetchall()

    conn.close()

    def fmt_time(ts):
        if not ts: return "--:--"
        dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone(datetime.timedelta(hours=-3)))
        return dt.strftime("%H:%M")

    current_data = None
    if cur_row:
        total_sec = max(1, cur_row["stop_ts"] - cur_row["start_ts"])
        elapsed_sec = max(0, now_ts - cur_row["start_ts"])
        prog_pct = min(100, int((elapsed_sec / total_sec) * 100))
        current_data = {
            "title": cur_row["title"],
            "desc": cur_row["description"],
            "start": fmt_time(cur_row["start_ts"]),
            "stop": fmt_time(cur_row["stop_ts"]),
            "progress": prog_pct
        }
    else:
        current_data = {
            "title": "Transmissão ao Vivo",
            "desc": "Assista em tempo real na Nexus PlayTV.",
            "start": "--:--",
            "stop": "--:--",
            "progress": 0
        }

    upcoming_list = []
    for r in upcoming_rows:
        upcoming_list.append({
            "title": r["title"],
            "desc": r["description"],
            "start": fmt_time(r["start_ts"]),
            "stop": fmt_time(r["stop_ts"])
        })

    return {
        "found": True,
        "channel": channel_name,
        "matched_id": matched_id,
        "current": current_data,
        "upcoming": upcoming_list
    }

class EPGHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ["/epg", "/beta/api/epg"]:
            qs = parse_qs(parsed.query)
            name = qs.get("name", [""])[0]
            icon = qs.get("icon", [""])[0]
            cid = qs.get("id", [""])[0]

            data = query_epg(name, icon, cid)
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "public, max-age=60")
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/sync":
            ok = sync_epg()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"success": ok}).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        pass

def run_server():
    init_db()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM programmes")
    count = c.fetchone()[0]
    conn.close()
    
    if count == 0:
        sync_epg()

    server = HTTPServer(("127.0.0.1", PORT), EPGHandler)
    print(f"[{datetime.datetime.now()}] Servidor EPG Nexus rodando em http://127.0.0.1:{PORT}")
    server.serve_forever()

if __name__ == "__main__":
    import sys
    if "--sync-only" in sys.argv:
        init_db()
        sync_epg()
    else:
        run_server()
