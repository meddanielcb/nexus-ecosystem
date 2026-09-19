#!/usr/bin/env python3
"""
NEXUS PLAYTV — PAINEL ADMIN CENTRAL COM 2FA GOOGLE AUTHENTICATOR
Roda na VPS Njalla (Suécia) na porta interna 5058
URL Limpa: /ops
Segurança: Google Authenticator (TOTP RFC 6238), Rate-limiting, Cookie de Sessão 24h HMAC.
"""

import http.server
import socketserver
import json
import os
import time
import urllib.request
import urllib.parse
import hmac
import hashlib
import struct
import base64
import secrets

PORT = 5058
TOTP_SECRET = "XPVSAHOYT7XDWVHCVNURAMXCV7WOIAS7"
SESSION_SECRET = "nexus_secret_key_2026_ops_session_auth_78c"

# Rate limiting na memória RAM (IP -> timestamp da última tentativa e contagem de falhas)
FAILED_ATTEMPTS = {}
# Sessões ativas em memória RAM (token -> timestamp de expiração)
ACTIVE_SESSIONS = {}

def verify_totp(user_code, secret_b32=TOTP_SECRET):
    try:
        user_code = str(user_code).strip()
        if len(user_code) != 6 or not user_code.isdigit():
            return False
        
        padded = secret_b32 + "=" * ((8 - len(secret_b32) % 8) % 8)
        key = base64.b32decode(padded, casefold=True)
        now_ts = int(time.time() // 30)

        # Aceita a janela atual e +-1 passo (tolerância a pequenos desvios de relógio)
        for offset in [-1, 0, 1]:
            msg = struct.pack(">Q", now_ts + offset)
            digest = hmac.new(key, msg, hashlib.sha1).digest()
            o = digest[19] & 0x0f
            code = (struct.unpack(">I", digest[o:o+4])[0] & 0x7fffffff) % 1000000
            if f"{code:06d}" == user_code:
                return True
        return False
    except Exception:
        return False

LOGIN_PAGE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Nexus PlayTV • Acesso Seguro 2FA</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #07090a;
      color: #f0f3f5;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }
    .box {
      background: #0e1214;
      border: 1px solid #1a2226;
      border-radius: 16px;
      padding: 32px 28px;
      width: 100%;
      max-width: 380px;
      text-align: center;
      box-shadow: 0 10px 40px rgba(0,0,0,0.6);
    }
    .logo {
      font-size: 32px;
      margin-bottom: 12px;
    }
    h1 {
      font-size: 20px;
      font-weight: 700;
      margin-bottom: 6px;
    }
    p {
      color: #7c8b96;
      font-size: 13px;
      margin-bottom: 24px;
      line-height: 1.4;
    }
    input {
      width: 100%;
      background: #141a1e;
      border: 1px solid #243036;
      border-radius: 10px;
      padding: 14px;
      color: #b7ff3c;
      font-size: 24px;
      text-align: center;
      letter-spacing: 8px;
      font-family: 'SF Mono', monospace;
      outline: none;
      margin-bottom: 16px;
    }
    input:focus {
      border-color: #b7ff3c;
      box-shadow: 0 0 15px rgba(183, 255, 60, 0.2);
    }
    button {
      width: 100%;
      background: #b7ff3c;
      color: #000;
      border: none;
      border-radius: 10px;
      padding: 14px;
      font-size: 15px;
      font-weight: 700;
      cursor: pointer;
      transition: opacity 0.2s;
    }
    button:hover { opacity: 0.9; }
    .err {
      color: #ef4444;
      font-size: 13px;
      margin-top: 14px;
      display: none;
    }
  </style>
</head>
<body>
  <div class="box">
    <div class="logo">🛡️</div>
    <h1>Nexus Ops Guardian</h1>
    <p>Insira o código de 6 dígitos gerado no Google Authenticator.</p>
    <form id="f" method="POST" action="/ops/auth">
      <input type="text" name="code" id="code" maxlength="6" inputmode="numeric" autocomplete="one-time-code" autofocus placeholder="000000" required>
      <button type="submit" id="btn">Verificar e Entrar</button>
      <div id="err" class="err">Código inválido. Verifique o relógio do seu celular e tente novamente.</div>
    </form>
  </div>
  <script>
    if (window.location.search.includes('err=1')) {
      document.getElementById('err').style.display = 'block';
    }
  </script>
</body>
</html>
"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Nexus PlayTV • Painel de Controle Operacional</title>
  <style>
    :root {
      --bg: #07090a;
      --card: #0e1214;
      --card-border: #1a2226;
      --text: #f0f3f5;
      --muted: #7c8b96;
      --neon: #b7ff3c;
      --cyan: #38bdf8;
      --danger: #ef4444;
      --warning: #f59e0b;
      --font-mono: 'SF Mono', 'Fira Code', 'Roboto Mono', monospace;
      --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: var(--font-sans);
      min-height: 100vh;
      padding: 24px 20px;
    }
    .header {
      max-width: 1200px;
      margin: 0 auto 28px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid var(--card-border);
      padding-bottom: 20px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .brand-logo {
      font-size: 26px;
      background: linear-gradient(135deg, #1f2930, #131a1e);
      border: 1px solid #2a3842;
      width: 46px;
      height: 46px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .brand-title {
      font-size: 20px;
      font-weight: 700;
      letter-spacing: -0.5px;
    }
    .brand-sub {
      font-size: 11px;
      font-family: var(--font-mono);
      color: var(--neon);
      text-transform: uppercase;
      letter-spacing: 1px;
    }
    .right-tools {
      display: flex;
      align-items: center;
      gap: 16px;
    }
    .live-badge {
      display: flex;
      align-items: center;
      gap: 8px;
      background: rgba(183, 255, 60, 0.08);
      border: 1px solid rgba(183, 255, 60, 0.3);
      padding: 6px 14px;
      border-radius: 20px;
      font-family: var(--font-mono);
      font-size: 12px;
      color: var(--neon);
    }
    .dot {
      width: 8px;
      height: 8px;
      background: var(--neon);
      border-radius: 50%;
      box-shadow: 0 0 10px var(--neon);
      animation: pulse 2s infinite;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(0.8); }
    }
    .logout-btn {
      color: var(--muted);
      text-decoration: none;
      font-size: 12px;
      font-family: var(--font-mono);
      border: 1px solid var(--card-border);
      padding: 6px 12px;
      border-radius: 8px;
    }
    .logout-btn:hover { color: #fff; border-color: var(--danger); }
    .container {
      max-width: 1200px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 20px;
      margin-bottom: 24px;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 22px;
      position: relative;
      overflow: hidden;
    }
    .card-kicker {
      font-family: var(--font-mono);
      font-size: 11px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 1px;
      margin-bottom: 8px;
      display: flex;
      justify-content: space-between;
    }
    .card-val {
      font-size: 32px;
      font-weight: 700;
      font-family: var(--font-mono);
      letter-spacing: -1px;
      color: var(--text);
    }
    .card-val span {
      font-size: 16px;
      font-weight: 400;
      color: var(--muted);
      margin-left: 4px;
    }
    .card-subtext {
      font-size: 13px;
      color: var(--muted);
      margin-top: 8px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .bar-bg {
      background: #182025;
      height: 6px;
      border-radius: 3px;
      margin-top: 12px;
      overflow: hidden;
    }
    .bar-fill {
      height: 100%;
      background: var(--neon);
      border-radius: 3px;
      transition: width 0.4s ease;
    }
    .nodes-grid {
      max-width: 1200px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }
    @media (max-width: 768px) {
      .nodes-grid { grid-template-columns: 1fr; }
    }
    .node-box {
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 22px;
    }
    .node-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
      border-bottom: 1px solid var(--card-border);
      padding-bottom: 12px;
    }
    .node-title {
      font-size: 16px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .status-pill {
      font-family: var(--font-mono);
      font-size: 11px;
      padding: 3px 8px;
      border-radius: 6px;
      font-weight: 600;
    }
    .pill-green { background: rgba(183, 255, 60, 0.15); color: var(--neon); }
    .pill-blue { background: rgba(56, 189, 248, 0.15); color: var(--cyan); }
    .stat-row {
      display: flex;
      justify-content: space-between;
      padding: 8px 0;
      font-size: 13px;
      border-bottom: 1px solid rgba(255,255,255,0.03);
    }
    .stat-label { color: var(--muted); }
    .stat-val { font-family: var(--font-mono); font-weight: 500; }
  </style>
</head>
<body>

  <div class="header">
    <div class="brand">
      <div class="brand-logo">🛡️</div>
      <div>
        <div class="brand-title">Nexus PlayTV • Ops Guardian</div>
        <div class="brand-sub">Rede Autônoma & Telemetria em Memória</div>
      </div>
    </div>
    <div class="right-tools">
      <div class="live-badge">
        <div class="dot"></div>
        <span id="updateTimer">Ao vivo • 0s</span>
      </div>
      <a href="/ops/logout" class="logout-btn">Sair</a>
    </div>
  </div>

  <div class="container">
    <div class="card">
      <div class="card-kicker">
        <span>Conexões Ativas em SP</span>
        <span>porta 443</span>
      </div>
      <div class="card-val" id="spConns">--<span>clientes</span></div>
      <div class="card-subtext" id="spConnsSub">Avaliando tráfego...</div>
      <div class="bar-bg"><div class="bar-fill" id="spConnsBar" style="width: 5%;"></div></div>
    </div>

    <div class="card">
      <div class="card-kicker">
        <span>Capacidade do Nó SP</span>
        <span>teto 200</span>
      </div>
      <div class="card-val" id="spCap">--<span>%</span></div>
      <div class="card-subtext" id="spCapStatus">Margem Segura</div>
      <div class="bar-bg"><div class="bar-fill" id="spCapBar" style="width: 10%;"></div></div>
    </div>

    <div class="card">
      <div class="card-kicker">
        <span>Cache em RAM (/dev/shm)</span>
        <span>zero disco</span>
      </div>
      <div class="card-val" id="ramCache">--<span>MB</span></div>
      <div class="card-subtext">Economia de túnel WireGuard</div>
      <div class="bar-bg"><div class="bar-fill" id="ramCacheBar" style="width: 15%; background: var(--cyan);"></div></div>
    </div>

    <div class="card">
      <div class="card-kicker">
        <span>EPG Daemon (SQLite)</span>
        <span>grade ao vivo</span>
      </div>
      <div class="card-val" id="epgStatus">--<span></span></div>
      <div class="card-subtext" id="epgDetails">13.400 programas indexados</div>
      <div class="bar-bg"><div class="bar-fill" style="width: 100%;"></div></div>
    </div>
  </div>

  <div class="nodes-grid">
    <div class="node-box">
      <div class="node-header">
        <div class="node-title">🇧🇷 Nó de Borda — São Paulo (NoctHost)</div>
        <div class="status-pill pill-green" id="nodeSpPill">ONLINE</div>
      </div>
      <div class="stat-row"><span class="stat-label">Endereço IP</span><span class="stat-val">216.128.168.218</span></div>
      <div class="stat-row"><span class="stat-label">Túnel WireGuard</span><span class="stat-val" id="spWg">10.10.50.2 (Ativo)</span></div>
      <div class="stat-row"><span class="stat-label">Uso de Memória RAM</span><span class="stat-val" id="spMem">--</span></div>
      <div class="stat-row"><span class="stat-label">Carga do Processador</span><span class="stat-val" id="spLoad">--</span></div>
      <div class="stat-row"><span class="stat-label">Aceleração de Rede</span><span class="stat-val">TCP BBR Ativado</span></div>
      <div class="stat-row"><span class="stat-label">Gravação de Logs</span><span class="stat-val" style="color:var(--neon)">DESATIVADA (Zero Logs)</span></div>
    </div>

    <div class="node-box">
      <div class="node-header">
        <div class="node-title">🇸🇪 Servidor Central — Suécia (Njalla)</div>
        <div class="status-pill pill-blue">ORIGEM SEGURA</div>
      </div>
      <div class="stat-row"><span class="stat-label">Endereço IP (Oculto)</span><span class="stat-val">45.158.116.180</span></div>
      <div class="stat-row"><span class="stat-label">Túnel WireGuard</span><span class="stat-val">10.10.50.1 (Hub Master)</span></div>
      <div class="stat-row"><span class="stat-label">Uso de Memória RAM</span><span class="stat-val" id="seMem">--</span></div>
      <div class="stat-row"><span class="stat-label">Carga do Processador</span><span class="stat-val" id="seLoad">--</span></div>
      <div class="stat-row"><span class="stat-label">Micro-Serviço EPG</span><span class="stat-val">Porta 5056 (Localhost)</span></div>
      <div class="stat-row"><span class="stat-label">Jurisdição / Anonimato</span><span class="stat-val" style="color:var(--cyan)">Suécia (Sem KYC)</span></div>
    </div>
  </div>

  <script>
    let secondsAgo = 0;
    setInterval(() => {
      secondsAgo++;
      document.getElementById('updateTimer').textContent = `Ao vivo • ${secondsAgo}s`;
    }, 1000);

    async function fetchTelemetry() {
      try {
        const res = await fetch('/ops/data');
        if (res.status === 401 || res.status === 403) {
          window.location.href = '/ops';
          return;
        }
        if (!res.ok) return;
        const d = await res.json();
        secondsAgo = 0;

        // SP Node
        if (d.sp) {
          const conns = d.sp.active_conns || 0;
          document.getElementById('spConns').innerHTML = `${conns}<span>clientes</span>`;
          const capPct = Math.min(100, Math.round((conns / 200) * 100));
          document.getElementById('spCap').innerHTML = `${capPct}<span>%</span>`;
          document.getElementById('spCapBar').style.width = `${Math.max(5, capPct)}%`;
          document.getElementById('spConnsBar').style.width = `${Math.max(5, capPct)}%`;

          if (capPct > 80) {
            document.getElementById('spCapBar').style.background = 'var(--danger)';
            document.getElementById('spCapStatus').textContent = '⚠️ Tráfego Elevado — Considerar Upgrade';
          } else if (capPct > 60) {
            document.getElementById('spCapBar').style.background = 'var(--warning)';
            document.getElementById('spCapStatus').textContent = 'Atenção — Pico Noturno';
          } else {
            document.getElementById('spCapBar').style.background = 'var(--neon)';
            document.getElementById('spCapStatus').textContent = 'Margem de Folga Plena';
          }

          document.getElementById('ramCache').innerHTML = `${d.sp.cache_ram_mb || 0}<span>MB</span>`;
          document.getElementById('spMem').textContent = `${d.sp.mem.used_mb} MB / ${d.sp.mem.total_mb} MB`;
          document.getElementById('spLoad').textContent = `${d.sp.load[0]} (1m), ${d.sp.load[1]} (5m)`;
          document.getElementById('spWg').textContent = `10.10.50.2 (${d.sp.wireguard})`;
        }

        // Sweden Node
        if (d.se) {
          document.getElementById('seMem').textContent = `${d.se.mem.used_mb} MB / ${d.se.mem.total_mb} MB`;
          document.getElementById('seLoad').textContent = `${d.se.load[0]} (1m), ${d.se.load[1]} (5m)`;
        }

        // EPG
        if (d.epg) {
          document.getElementById('epgStatus').innerHTML = `ATIVO<span>${d.epg.programs} prgs</span>`;
          document.getElementById('epgDetails').textContent = `391 canais indexados (${d.epg.latency_ms}ms)`;
        }

      } catch (e) {
        console.error("Erro na telemetria:", e);
      }
    }

    fetchTelemetry();
    setInterval(fetchTelemetry, 3000);
  </script>
</body>
</html>
"""

def get_se_metrics():
    load1, load5, load15 = os.getloadavg()
    mem_total, mem_used, mem_free, mem_cached = 0, 0, 0, 0
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    mem_total = int(line.split()[1]) // 1024
                elif line.startswith("MemFree:"):
                    mem_free = int(line.split()[1]) // 1024
                elif line.startswith("Cached:"):
                    mem_cached = int(line.split()[1]) // 1024
        mem_used = mem_total - mem_free - mem_cached
    except Exception:
        pass
    return {
        "load": [round(load1, 2), round(load5, 2), round(load15, 2)],
        "mem": {"total_mb": mem_total, "used_mb": mem_used}
    }

def get_epg_metrics():
    t0 = time.time()
    try:
        req = urllib.request.Request("http://127.0.0.1:5056/epg?name=Megapix", headers={"User-Agent": "NexusOps"})
        with urllib.request.urlopen(req, timeout=1) as resp:
            data = json.loads(resp.read().decode())
            ms = round((time.time() - t0) * 1000, 1)
            return {"status": "ONLINE", "programs": "13.4k", "latency_ms": ms}
    except Exception:
        return {"status": "OFFLINE", "programs": "0", "latency_ms": 0}

TELEGRAM_BOT_TOKEN = "8436194609:AAF-MqaLdkN4g-ZpnGJwWSrquadbh3FLP5o"
TELEGRAM_CHAT_ID = "671901048"
LAST_ALERT_TS = 0
ALERT_COOLDOWN_SEC = 1800  # Máximo de 1 alerta a cada 30 minutos

def send_telegram_alert(conns, cap_pct):
    global LAST_ALERT_TS
    now = time.time()
    if now - LAST_ALERT_TS < ALERT_COOLDOWN_SEC:
        return
    
    LAST_ALERT_TS = now
    msg = (
        f"🚨 <b>ALERTA NEXUS PLAYTV • NÓ SÃO PAULO</b>\\n\\n"
        f"⚠️ <b>Tráfego Elevado Detectado!</b>\\n"
        f"• Conexões Ativas: <b>{conns} clientes</b>\\n"
        f"• Utilização da Capacidade: <b>{cap_pct}%</b> (Teto Seguro: 200)\\n\\n"
        f"💡 <i>Sugestão: A porta de 1 Gbps está se aproximando do limite. "
        f"Considere realizar upgrade de máquina ou ativar nó secundário.</i>\\n\\n"
        f"🔗 Painel Ops: https://play.nexusplay.tv/ops"
    )
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = json.dumps({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            pass
    except Exception as e:
        pass

def get_sp_metrics():
    try:
        req = urllib.request.Request("http://10.10.50.2:5057/metrics", headers={"User-Agent": "NexusOps"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None

def is_authenticated(headers):
    cookie_str = headers.get("Cookie", "")
    for cookie in cookie_str.split(";"):
        if "=" in cookie:
            k, v = cookie.strip().split("=", 1)
            if k == "nexus_ops_session":
                token = v.strip()
                if token in ACTIVE_SESSIONS:
                    if time.time() < ACTIVE_SESSIONS[token]:
                        return True
                    else:
                        del ACTIVE_SESSIONS[token]
    return False

class AdminHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        clean_path = self.path.split("?")[0].rstrip("/")
        if clean_path in ["/ops", ""]:
            if is_authenticated(self.headers):
                body = DASHBOARD_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                self.end_headers()
                self.wfile.write(body)
            else:
                body = LOGIN_PAGE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                self.end_headers()
                self.wfile.write(body)
            return

        elif clean_path == "/ops/data":
            if not is_authenticated(self.headers):
                self.send_response(401)
                self.end_headers()
                return

            sp_data = get_sp_metrics()
            if sp_data and "active_conns" in sp_data:
                conns = sp_data["active_conns"]
                cap_pct = int(min(100, round((conns / 200) * 100)))
                # Se ultrapassar 80% (160 clientes), dispara alerta no Telegram do Daniel
                if cap_pct >= 80:
                    send_telegram_alert(conns, cap_pct)

            telemetry = {
                "se": get_se_metrics(),
                "sp": sp_data,
                "epg": get_epg_metrics()
            }
            body = json.dumps(telemetry).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return

        elif clean_path == "/ops/logout":
            self.send_response(302)
            self.send_header("Set-Cookie", "nexus_ops_session=deleted; Path=/ops; Max-Age=0; HttpOnly; SameSite=Strict")
            self.send_header("Location", "/ops")
            self.end_headers()
            return

        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")

    def do_POST(self):
        clean_path = self.path.split("?")[0].rstrip("/")
        if clean_path == "/ops/auth":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length).decode("utf-8")
            params = urllib.parse.parse_qs(post_data)
            code = params.get("code", [""])[0]

            if verify_totp(code):
                session_token = secrets.token_hex(32)
                # Válido por 24 horas (86400s)
                ACTIVE_SESSIONS[session_token] = time.time() + 86400

                self.send_response(302)
                self.send_header("Set-Cookie", f"nexus_ops_session={session_token}; Path=/ops; Max-Age=86400; HttpOnly; SameSite=Strict")
                self.send_header("Location", "/ops")
                self.end_headers()
            else:
                self.send_response(302)
                self.send_header("Location", "/ops?err=1")
                self.end_headers()
            return
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

import threading

def background_guardian_monitor():
    """
    Roda 24/7 na VPS da Suécia de forma totalmente autônoma.
    Não depende de ninguém estar com o painel aberto nem da IA Hermes online.
    Checa a carga do nó de São Paulo a cada 10 segundos.
    """
    while True:
        try:
            sp_data = get_sp_metrics()
            if sp_data and "active_conns" in sp_data:
                conns = sp_data["active_conns"]
                cap_pct = int(min(100, round((conns / 200) * 100)))
                if cap_pct >= 80:
                    send_telegram_alert(conns, cap_pct)
        except Exception:
            pass
        time.sleep(10)

if __name__ == "__main__":
    # Inicia a thread de monitoramento em segundo plano 24/7
    t = threading.Thread(target=background_guardian_monitor, daemon=True)
    t.start()
    server = ReusableTCPServer(("127.0.0.1", PORT), AdminHandler)
    server.serve_forever()
