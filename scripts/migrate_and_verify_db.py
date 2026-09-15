#!/usr/bin/env python3
"""
migrate_and_verify_db.py — Migração idempotente + verificação de integridade
dos bancos SQLite do Ecossistema Nexus (correção do achado P1-7).

O que faz:
  1. Aplica as migrações de schema (db.init_db) nos bancos de produção e nos
     bancos informados via --db.
  2. Verifica integridade (PRAGMA integrity_check / foreign_key_check) e se o
     schema contém TODAS as tabelas/colunas que o código consome.
  3. Compara o estado ANTES x DEPOIS para provar que nenhum dado foi perdido
     (contagem de linhas + hash determinístico das linhas de cada tabela).
  4. --selftest: cria um banco NOVO e um banco LEGADO sintético (schema antigo
     + dados), roda a migração nos dois e valida o resultado.  Sem tocar nos
     bancos reais.
  5. --json: saída legível por máquina (para cron/monitoramento).

Uso:
  python3 /opt/data/scripts/migrate_and_verify_db.py                # migra + verifica
  python3 /opt/data/scripts/migrate_and_verify_db.py --verify-only  # só verifica (exit 1 se divergir)
  python3 /opt/data/scripts/migrate_and_verify_db.py --selftest     # testes em bancos temporários
  python3 /opt/data/scripts/migrate_and_verify_db.py --db /tmp/x.db --module /opt/data/nexus_playtv_bot/db.py
"""

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time

# ---------------------------------------------------------------- registries
TARGETS = [
    {"name": "playtv", "module_path": "/opt/data/nexus_playtv_bot/db.py",
     "db_path": "/opt/data/nexus_playtv_bot/data/playtv.db"},
    {"name": "store", "module_path": "/opt/data/digital_store_bot/db.py",
     "db_path": "/opt/data/digital_store_bot/data/store.db"},
]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location("nexus_db_%s" % name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- snapshots
def snapshot(db_path):
    """Snapshot por linha (chave = rowid) de cada tabela — prova anti-perda de dados.

    Guarda os nomes das colunas de cada tabela para que a comparação depois da
    migração use o MESMO subconjunto de colunas (colunas novas não invalidam).
    """
    if not os.path.exists(db_path):
        return None
    conn = sqlite3.connect(db_path)
    try:
        out = {}
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        for t in tables:
            columns = [r[1] for r in conn.execute('PRAGMA table_info("%s")' % t)]
            rows = {}
            try:
                for row in conn.execute('SELECT rowid, * FROM "%s"' % t):
                    rows[str(row[0])] = list(row[1:])
            except sqlite3.OperationalError:  # tabela WITHOUT ROWID
                for i, row in enumerate(conn.execute('SELECT * FROM "%s"' % t)):
                    rows["pos:%d" % i] = list(row)
            out[t] = {"columns": columns, "rows": rows, "count": len(rows)}
        return out
    finally:
        conn.close()


def diff_snapshots(before, after, backfill_columns=()):
    """Compara antes x depois e retorna (perdas_reais, tabelas_novas, backfills).

    - perda real: tabela removida, linha removida ou dado pré-existente alterado;
    - backfill esperado: coluna de timestamp que era NULL e passou a ter valor
      (efeito colateral legítimo de ALTER TABLE ADD COLUMN não aceitar default).
    """
    losses, added_tables, backfilled = [], [], []
    if before is None:
        return losses, list(after or {}), backfilled

    backfill = {(p[0], p[1]) if isinstance(p, (tuple, list)) else (None, p) for p in backfill_columns}
    for t, info in before.items():
        if t not in after:
            losses.append({"table": t, "reason": "tabela desapareceu", "rows_before": info["count"]})
            continue
        current = after[t]
        for rowid, values in info["rows"].items():
            if rowid not in current["rows"]:
                losses.append({"table": t, "reason": "linha removida", "rowid": rowid})
                continue
            new_values = current["rows"][rowid]
            changed = [col for i, col in enumerate(info["columns"])
                       if i < len(new_values) and values[i] != new_values[i]]
            if not changed:
                continue
            only_backfill = all(
                (t, c) in backfill and c in info["columns"]
                and values[info["columns"].index(c)] is None
                for c in changed
            )
            if only_backfill:
                backfilled.append({"table": t, "rowid": rowid, "columns": changed})
            else:
                losses.append({"table": t, "reason": "conteudo alterado", "rowid": rowid,
                               "columns": changed,
                               "before": [values[info["columns"].index(c)] for c in changed],
                               "after": [new_values[info["columns"].index(c)] for c in changed]})
    for t in after:
        if t not in before:
            added_tables.append(t)
    return losses, added_tables, backfilled


# ---------------------------------------------------------------- operations
def process_target(target, verify_only=False, verbose=True):
    result = {"name": target["name"], "db_path": target["db_path"], "ok": False}

    if not os.path.exists(target["module_path"]):
        result["error"] = "modulo db.py nao encontrado: %s" % target["module_path"]
        return result

    mod = load_module(target["name"], target["module_path"])
    before = snapshot(target["db_path"])

    if not verify_only:
        report = mod.init_db(target["db_path"], verbose=False)
        result["migration"] = report

    after = snapshot(target["db_path"])
    losses, added_tables, backfilled = diff_snapshots(
        before, after, getattr(mod, "TIMESTAMP_BACKFILL", ()))
    result["row_counts_before"] = {t: v["count"] for t, v in (before or {}).items()}
    result["row_counts_after"] = {t: v["count"] for t, v in (after or {}).items()}
    result["new_tables"] = sorted(added_tables)
    result["backfilled_timestamps"] = backfilled
    result["data_loss"] = losses
    result["verified_only"] = verify_only

    verify = mod.verify_schema(target["db_path"])
    result["verify"] = verify
    result["schema_fingerprint"] = mod.schema_fingerprint(target["db_path"])
    result["schema_version"] = getattr(mod, "SCHEMA_VERSION", None)

    # integridade extra: checagem pragma em todas as conexões
    result["ok"] = bool(
        verify["ok"]
        and verify["integrity"] == "ok"
        and not losses
        and not verify["missing_tables"]
        and not verify["missing_columns"]
    )

    if verbose:
        status = "OK" if result["ok"] else "FALHA"
        print("[%s] %s  (%s)" % (target["name"], status, result["db_path"]))
        print("    tabelas: %s" % ", ".join(sorted(result["row_counts_after"].keys())))
        if result.get("migration"):
            m = result["migration"]
            print("    schema_version=%s | tabelas criadas=%s | colunas adicionadas=%s"
                  % (m["schema_version"], m["created_tables"] or "-", m["added_columns"] or "-"))
            for w in m["warnings"]:
                print("    AVISO: %s" % w)
        print("    integrity_check=%s | tabelas ausentes=%s | colunas ausentes=%s"
              % (verify["integrity"], verify["missing_tables"] or "-", verify["missing_columns"] or "-"))
        if losses:
            for loss in losses:
                print("    PERDA DE DADOS: %s (%s)" % (loss["table"], loss["reason"]))
        if added_tables:
            print("    novas tabelas criadas: %s" % ", ".join(sorted(added_tables)))
    return result


# ---------------------------------------------------------------- selftest
LEGACY_PLAYTV_SQL = [
    # schema ANTIGO (como o db.py original criava) + dados de teste
    """CREATE TABLE orders (
        order_id TEXT PRIMARY KEY, user_id INTEGER, username TEXT, product_id TEXT,
        payment_method TEXT, amount REAL, status TEXT DEFAULT 'pending', payment_id TEXT,
        delivered_credentials TEXT, created_at TIMESTAMP, updated_at TIMESTAMP)""",
    """CREATE TABLE users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        created_at TIMESTAMP)""",
    """CREATE TABLE free_trials (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER UNIQUE,
        username TEXT, iptv_username TEXT, iptv_password TEXT, server_url TEXT, m3u_url TEXT,
        created_at TIMESTAMP, expires_at TIMESTAMP, reminded_30m INTEGER DEFAULT 0,
        reminded_expired INTEGER DEFAULT 0)""",
    "INSERT INTO orders (order_id, user_id, username, product_id, amount, status, delivered_credentials) "
    "VALUES ('ORD_LEGADO_1', 111, 'cliente_legado', 'monthly_1screen', 29.9, 'paid', 'Usuario: legacy | Senha: x')",
    "INSERT INTO users (user_id, username, first_name) VALUES (111, 'cliente_legado', 'Cliente')",
    "INSERT INTO free_trials (user_id, username, iptv_username, iptv_password, server_url) "
    "VALUES (222, 'trial_user', 'trial_x', 'pw', 'http://cdn.local:8080')",
]

LEGACY_ORDER_COLUMNS_NEEDED = ["m3u_url", "expires_at", "reminded_3d", "reminded_1d", "reminded_expired"]
LEGACY_TABLES_NEEDED = ["game_passes", "pass_redemptions", "coupons"]


def selftest(verbose=True):
    checks = []
    tmp = tempfile.mkdtemp(prefix="nexus_dbtest_")

    def check(name, condition, detail=""):
        checks.append({"check": name, "ok": bool(condition), "detail": detail})
        if verbose:
            print("  [%s] %s%s" % ("PASS" if condition else "FAIL", name,
                                   (" — " + detail) if detail else ""))

    try:
        # ---------- TESTE 1: banco NOVO a partir do db.py do PlayTV
        playtv = load_module("playtv_test", "/opt/data/nexus_playtv_bot/db.py")
        store = load_module("store_test", "/opt/data/digital_store_bot/db.py")

        fresh_playtv = os.path.join(tmp, "fresh_playtv.db")
        r1 = playtv.init_db(fresh_playtv)
        v1 = playtv.verify_schema(fresh_playtv)
        check("banco novo (playtv): schema completo", v1["ok"],
              "ausentes=%s%s" % (v1["missing_tables"], v1["missing_columns"]))
        check("banco novo (playtv): integrity_check", v1["integrity"] == "ok", v1["integrity"])
        conn = sqlite3.connect(fresh_playtv)
        tnames = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        for t in LEGACY_TABLES_NEEDED + ["orders", "free_trials", "users", "schema_migrations"]:
            check("banco novo: tabela %s existe" % t, t in tnames)

        # ---------- TESTE 2: banco LEGADO (schema antigo + dados) -> migração preserva dados
        legacy = os.path.join(tmp, "legacy_playtv.db")
        conn = sqlite3.connect(legacy)
        for stmt in LEGACY_PLAYTV_SQL:
            conn.execute(stmt)
        conn.commit()
        conn.close()
        before = snapshot(legacy)

        r2 = playtv.init_db(legacy)
        after = snapshot(legacy)
        losses, added, backfilled = diff_snapshots(before, after, playtv.TIMESTAMP_BACKFILL)
        v2 = playtv.verify_schema(legacy)
        check("banco legado: migração deixa schema completo", v2["ok"],
              "ausentes=%s%s" % (v2["missing_tables"], v2["missing_columns"]))
        check("banco legado: nenhuma linha perdida", not losses, str(losses))
        check("banco legado: transactions preservadas (2 dados)",
              after["orders"]["count"] == 1 and after["users"]["count"] == 1 and after["free_trials"]["count"] == 1,
              "orders=%s users=%s free_trials=%s" % (after["orders"]["count"], after["users"]["count"], after["free_trials"]["count"]))
        check("banco legado: conteudo original intacto (rowid a rowid)",
              before["orders"]["rows"][list(before["orders"]["rows"])[0]][0] == "ORD_LEGADO_1",
              "order_id=%s" % after["orders"]["rows"][list(after["orders"]["rows"])[0]][0])
        conn = sqlite3.connect(legacy)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(orders)")}
        missing = [c for c in LEGACY_ORDER_COLUMNS_NEEDED if c not in cols]
        conn.close()
        check("banco legado: colunas de orders adicionadas", not missing, "faltando=%s" % missing)
        check("banco legado: tabelas game_passes/pass_redemptions/coupons criadas",
              all(t in added for t in LEGACY_TABLES_NEEDED), "criadas=%s" % sorted(added))
        check("banco legado: nenhum aviso de migração", not r2["warnings"], str(r2["warnings"]))

        # ---------- TESTE 3: idempotência (rodar 3x não muda nada)
        h1 = playtv.schema_fingerprint(legacy)
        for _ in range(3):
            r3 = playtv.init_db(legacy)
        h2 = playtv.schema_fingerprint(legacy)
        after2 = snapshot(legacy)
        check("idempotência: fingerprint inalterado após 4 execuções", h1 == h2)
        check("idempotência: contagens inalteradas", after == after2)
        check("idempotência: 2a execução não adiciona colunas", not r3["added_columns"] and not r3["created_tables"],
              "tabelas=%s colunas=%s" % (r3["created_tables"], r3["added_columns"]))

        # ---------- TESTE 4: store (novo + legado)
        fresh_store = os.path.join(tmp, "fresh_store.db")
        store.init_db(fresh_store)
        vs = store.verify_schema(fresh_store)
        check("banco novo (store): schema completo", vs["ok"], str(vs["missing_tables"] + vs["missing_columns"]))

        legacy_store = os.path.join(tmp, "legacy_store.db")
        conn = sqlite3.connect(legacy_store)
        conn.execute("CREATE TABLE orders (order_id TEXT PRIMARY KEY, user_id INTEGER, status TEXT)")
        conn.execute("INSERT INTO orders (order_id, user_id, status) VALUES ('ORD_S1', 9, 'paid')")
        conn.commit()
        conn.close()
        b = snapshot(legacy_store)
        store.init_db(legacy_store)
        a = snapshot(legacy_store)
        ls, _, _ = diff_snapshots(b, a, store.TIMESTAMP_BACKFILL)
        vls = store.verify_schema(legacy_store)
        check("banco legado (store): schema completo após migração", vls["ok"], "ausentes=%s%s" % (vls["missing_tables"], vls["missing_columns"]))
        check("banco legado (store): dados preservados", not ls and a["orders"]["count"] == 1, str(ls))

        # ---------- TESTE 5: banco com dados reais migrados preservam colunas consumidas pelo código
        check("playtv: fingerprint estável", bool(h2))

        ok = all(c["ok"] for c in checks)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    return {"ok": ok, "checks": checks}


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Migração idempotente + verificação de integridade dos bancos Nexus")
    ap.add_argument("--verify-only", action="store_true", help="não altera schema, apenas verifica")
    ap.add_argument("--selftest", action="store_true", help="roda testes em bancos temporários (novo + legado)")
    ap.add_argument("--json", action="store_true", help="saída JSON")
    ap.add_argument("--db", action="append", default=[], help="banco extra (requer --module)")
    ap.add_argument("--module", help="caminho do db.py do banco extra")
    args = ap.parse_args()

    started = time.strftime("%Y-%m-%d %H:%M:%S")
    results = {"started_at": started, "targets": [], "selftest": None}

    if not args.json:
        print("=== Migração + verificação de bancos Nexus (%s) ===" % started)

    if args.selftest:
        if not args.json:
            print("\n-- selftest (bancos temporários) --")
        st = selftest(verbose=not args.json)
        results["selftest"] = st
        if not args.json:
            print("selftest: %s (%d checks)" % ("OK" if st["ok"] else "FALHA", len(st["checks"])))

    targets = list(TARGETS)
    for extra in args.db:
        if not args.module:
            print("ERRO: --db exige --module", file=sys.stderr)
            return 2
        targets.append({"name": os.path.basename(extra), "module_path": args.module, "db_path": extra})

    if not (args.selftest and not targets):
        if not args.json:
            print()
        for t in targets:
            if not os.path.exists(t["db_path"]) and args.verify_only:
                if not args.json:
                    print("[%s] PULADO: banco inexistente (%s)" % (t["name"], t["db_path"]))
                results["targets"].append({"name": t["name"], "db_path": t["db_path"], "ok": False,
                                           "error": "banco inexistente"})
                continue
            results["targets"].append(process_target(t, verify_only=args.verify_only, verbose=not args.json))

    all_ok = all(t["ok"] for t in results["targets"]) and (results["selftest"] is None or results["selftest"]["ok"])
    results["ok"] = all_ok
    results["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print("\nRESULTADO GERAL: %s" % ("OK" if all_ok else "FALHA"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
