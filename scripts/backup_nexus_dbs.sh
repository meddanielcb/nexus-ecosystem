#!/usr/bin/env bash
# backup_nexus_dbs.sh — Backup diário/rotativo dos bancos SQLite do Nexus
set -euo pipefail

BACKUP_DIR="/opt/data/backups/sqlite"
DATE_STR="$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "=== Backup de Bancos Nexus ($DATE_STR) ==="

# 1. Backup do PlayTV DB
if [ -f "/opt/data/nexus_playtv_bot/data/playtv.db" ]; then
    /opt/hermes/.venv/bin/python3 -c "
import sqlite3
src = sqlite3.connect('/opt/data/nexus_playtv_bot/data/playtv.db')
dst = sqlite3.connect('$BACKUP_DIR/playtv_$DATE_STR.db')
src.backup(dst)
dst.close()
src.close()
"
    echo "  [OK] playtv.db salvo em $BACKUP_DIR/playtv_$DATE_STR.db"
fi

# 2. Rotação: manter últimos 7 dias de backups e expirar os mais antigos
find "$BACKUP_DIR" -type f -name "*.db" -mtime +7 -delete
echo "=== Backup Concluído ==="
