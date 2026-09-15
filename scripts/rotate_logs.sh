#!/usr/bin/env bash
# rotate_logs.sh — Rotação e truncamento de logs volumosos do Nexus
set -euo pipefail

LOGS_DIR="/opt/data/digital_store_bot/logs"
MAX_SIZE_BYTES=5242880 # 5 MB

echo "=== Rotação de Logs Nexus ($(date +'%Y-%m-%d %H:%M:%S')) ==="

for logfile in "$LOGS_DIR"/*.log; do
    if [ -f "$logfile" ]; then
        filesize=$(stat -c%s "$logfile")
        if [ "$filesize" -gt "$MAX_SIZE_BYTES" ]; then
            echo "Rotacionando $logfile ($filesize bytes)..."
            cp "$logfile" "${logfile}.1"
            tail -n 2000 "${logfile}.1" > "$logfile"
            rm -f "${logfile}.1"
            echo "  [OK] $logfile reduzido para últimas 2000 linhas."
        fi
    fi
done
echo "=== Rotação Concluída ==="
