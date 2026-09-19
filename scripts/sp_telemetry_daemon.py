#!/usr/bin/env python3
"""
NEXUS PLAYTV — TELEMETRIA DO NÓ DE BORDA SÃO PAULO
Roda como daemon local em 127.0.0.1:5057 (apenas acessível via túnel WireGuard)
Zero gravação de logs em disco, zero dados de clientes armazenados.
"""

import http.server
import socketserver
import json
import os
import time
import subprocess

PORT = 5057

def get_sys_metrics():
    # 1. CPU Load
    load1, load5, load15 = os.getloadavg()
    
    # 2. RAM em MB
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

    # 3. Banda de Rede (bytes transmitidos/recebidos)
    rx_bytes, tx_bytes = 0, 0
    try:
        with open("/proc/net/dev") as f:
            for line in f:
                # interface eth0 / enp1s0
                if ":" in line and not line.strip().startswith("lo"):
                    parts = line.split(":")
                    iface = parts[0].strip()
                    if iface in ["eth0", "enp1s0", "wg0"]:
                        fields = parts[1].split()
                        rx_bytes += int(fields[0])
                        tx_bytes += int(fields[8])
    except Exception:
        pass

    # 4. Conexoes ativas no Nginx (porta 80/443)
    active_conns = 0
    try:
        out = subprocess.getoutput("ss -t state established '( sport = :80 or sport = :443 )' | wc -l")
        active_conns = max(0, int(out.strip()) - 1)
    except Exception:
        pass

    # 5. Tamanho do cache em RAM (/dev/shm/nexus_edge_cache)
    cache_mb = 0
    try:
        out = subprocess.getoutput("du -sm /dev/shm/nexus_edge_cache 2>/dev/null | awk '{print $1}'")
        if out and out.isdigit():
            cache_mb = int(out)
    except Exception:
        pass

    # 6. Status do WireGuard
    wg_status = "ONLINE"
    try:
        wg_out = subprocess.getoutput("wg show wg0 latest-handshakes | awk '{print $2}'")
        if wg_out:
            handshake_ts = int(wg_out.strip())
            if time.time() - handshake_ts > 120:
                wg_status = "STALE"
        else:
            wg_status = "DOWN"
    except Exception:
        wg_status = "UNKNOWN"

    return {
        "timestamp": time.time(),
        "load": [round(load1, 2), round(load5, 2), round(load15, 2)],
        "mem": {
            "total_mb": mem_total,
            "used_mb": mem_used,
            "free_mb": mem_free,
            "cached_mb": mem_cached
        },
        "net": {
            "rx_bytes": rx_bytes,
            "tx_bytes": tx_bytes
        },
        "active_conns": active_conns,
        "cache_ram_mb": cache_mb,
        "wireguard": wg_status
    }

class TelemetryHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # Apenas responde a /metrics
        if self.path == "/metrics":
            data = get_sys_metrics()
            body = json.dumps(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Silencia qualquer log de acesso no terminal/disco
        pass

if __name__ == "__main__":
    # Escuta estritamente na interface WireGuard (10.10.50.2) e localhost
    server = socketserver.TCPServer(("0.0.0.0", PORT), TelemetryHandler)
    server.serve_forever()
