#!/usr/bin/env python3
"""Migração idempotente: normaliza expires_at para ISO 8601 (YYYY-MM-DD HH:MM:SS).

Aceita o formato BR legado ('DD/MM/YYYY às HH:MM') que causava o ValueError nos
lembretes. Faz backup do banco antes de alterar. Seguro para reexecução.
"""
import os
import re
import shutil
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "playtv.db")
TABLES = ["orders", "free_trials", "pass_redemptions", "game_passes"]
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?$")


def parse_any(s):
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M",
                "%d/%m/%Y às %H:%M", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def main():
    if not os.path.exists(DB_PATH):
        print(f"Banco não encontrado: {DB_PATH}")
        return
    backup = DB_PATH + ".bak_dates"
    shutil.copy2(DB_PATH, backup)
    print(f"Backup criado: {backup}")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    total = 0
    for table in TABLES:
        try:
            rows = c.execute(
                f"SELECT rowid, expires_at FROM {table} WHERE expires_at IS NOT NULL"
            ).fetchall()
        except sqlite3.OperationalError as e:
            print(f"  {table}: pulado ({e})")
            continue
        changed = 0
        for rowid, raw in rows:
            if raw and ISO_RE.match(str(raw).strip()):
                continue
            dt = parse_any(raw)
            if not dt:
                print(f"  {table} rowid={rowid}: não parseável -> {raw!r}")
                continue
            iso = dt.strftime("%Y-%m-%d %H:%M:%S")
            c.execute(f"UPDATE {table} SET expires_at = ? WHERE rowid = ?", (iso, rowid))
            changed += 1
        total += changed
        print(f"  {table}: {changed}/{len(rows)} normalizados")
    conn.commit()
    conn.close()
    print(f"Total normalizado: {total}")


if __name__ == "__main__":
    main()
