"""
Nexus PlayTV — camada de banco de dados (schema + migrações idempotentes).

P1-7 (schema drift): este módulo agora é a fonte de verdade do schema do
playtv.db.  Ele cria TODAS as tabelas e colunas consumidas por
run_playtv.py / webhook_server.py e aplica migrações idempotentes em bancos
legados (ALTER TABLE ... ADD COLUMN apenas quando a coluna não existe).

Seguro para rodar:
  * em banco novo (cria tudo);
  * em banco legado (adiciona só o que falta, preservando 100% dos dados);
  * quantas vezes for necessário (nunca falha com "already exists").

CLI:
    python3 db.py                 # inicializa/migra o banco padrão
    python3 db.py --check         # só verifica, não altera (exit 1 se divergir)
    python3 db.py --db /tmp/x.db  # opera em outro arquivo
"""

import os
import sqlite3
import sys

DB_PATH = "/opt/data/nexus_playtv_bot/data/playtv.db"


def db_connect(path=None):
    """Conexão SQLite resiliente.

    Todo o ecossistema (bot, webhook, scheduler) escreve no mesmo arquivo,
    então usamos um timeout generoso + PRAGMA busy_timeout para que escritas
    concorrentes esperem a vez em vez de estourar "database is locked".
    """
    conn = sqlite3.connect(path or DB_PATH, timeout=30)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
    except Exception:
        pass
    return conn

# Versão lógica do schema.  Toda vez que SCHEMA/COLUMN_MIGRATIONS mudar,
# incremente e registre o motivo em MIGRATION_NOTES.
SCHEMA_VERSION = 2

MIGRATION_NOTES = {
    1: "Schema inicial versionado (orders, free_trials, users).",
    2: "P1-7: adiciona game_passes, pass_redemptions, coupons e as colunas "
       "m3u_url/expires_at/reminded_3d/reminded_1d/reminded_expired em orders.",
}

# --------------------------------------------------------------------------
# Schema desejado (banco novo)
# --------------------------------------------------------------------------
SCHEMA = {
    "orders": """
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            user_id INTEGER,
            username TEXT,
            product_id TEXT,
            payment_method TEXT,
            amount REAL,
            status TEXT DEFAULT 'pending',
            payment_id TEXT,
            delivered_credentials TEXT,
            m3u_url TEXT,
            expires_at TIMESTAMP,
            reminded_3d INTEGER DEFAULT 0,
            reminded_1d INTEGER DEFAULT 0,
            reminded_expired INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "free_trials": """
        CREATE TABLE IF NOT EXISTS free_trials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            username TEXT,
            iptv_username TEXT,
            iptv_password TEXT,
            server_url TEXT,
            m3u_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            reminded_30m INTEGER DEFAULT 0,
            reminded_expired INTEGER DEFAULT 0
        )
    """,
    "users": """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "game_passes": """
        CREATE TABLE IF NOT EXISTS game_passes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            order_id TEXT,
            total_passes INTEGER DEFAULT 0,
            remaining_passes INTEGER DEFAULT 0,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "pass_redemptions": """
        CREATE TABLE IF NOT EXISTS pass_redemptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            pass_id INTEGER,
            username TEXT,
            password TEXT,
            m3u_url TEXT,
            redeemed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        )
    """,
    "coupons": """
        CREATE TABLE IF NOT EXISTS coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            discount_pct INTEGER,
            max_uses INTEGER DEFAULT 1,
            used_count INTEGER DEFAULT 0,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "referrals": """
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_user_id INTEGER UNIQUE,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "bonus_rewards": """
        CREATE TABLE IF NOT EXISTS bonus_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            reward_type TEXT DEFAULT 'monthly_plan',
            days INTEGER DEFAULT 30,
            status TEXT DEFAULT 'available',
            source_referral_id INTEGER,
            activated_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
}

# Colunas que podem faltar em bancos legados -> (tabela, coluna, DDL do ALTER).
# NOTA: SQLite não aceita DEFAULT CURRENT_TIMESTAMP/expressão em ADD COLUMN,
# então colunas de data são adicionadas sem default e preenchidas depois.
COLUMN_MIGRATIONS = [
    # orders (P1-7)
    ("orders", "m3u_url", "ALTER TABLE orders ADD COLUMN m3u_url TEXT"),
    ("orders", "expires_at", "ALTER TABLE orders ADD COLUMN expires_at TIMESTAMP"),
    ("orders", "reminded_3d", "ALTER TABLE orders ADD COLUMN reminded_3d INTEGER DEFAULT 0"),
    ("orders", "reminded_1d", "ALTER TABLE orders ADD COLUMN reminded_1d INTEGER DEFAULT 0"),
    ("orders", "reminded_expired", "ALTER TABLE orders ADD COLUMN reminded_expired INTEGER DEFAULT 0"),
    ("orders", "delivered_credentials", "ALTER TABLE orders ADD COLUMN delivered_credentials TEXT"),
    ("orders", "username", "ALTER TABLE orders ADD COLUMN username TEXT"),
    ("orders", "payment_method", "ALTER TABLE orders ADD COLUMN payment_method TEXT"),
    ("orders", "amount", "ALTER TABLE orders ADD COLUMN amount REAL"),
    ("orders", "payment_id", "ALTER TABLE orders ADD COLUMN payment_id TEXT"),
    ("orders", "created_at", "ALTER TABLE orders ADD COLUMN created_at TIMESTAMP"),
    ("orders", "updated_at", "ALTER TABLE orders ADD COLUMN updated_at TIMESTAMP"),
    # free_trials
    ("free_trials", "iptv_username", "ALTER TABLE free_trials ADD COLUMN iptv_username TEXT"),
    ("free_trials", "iptv_password", "ALTER TABLE free_trials ADD COLUMN iptv_password TEXT"),
    ("free_trials", "server_url", "ALTER TABLE free_trials ADD COLUMN server_url TEXT"),
    ("free_trials", "m3u_url", "ALTER TABLE free_trials ADD COLUMN m3u_url TEXT"),
    ("free_trials", "expires_at", "ALTER TABLE free_trials ADD COLUMN expires_at TIMESTAMP"),
    ("free_trials", "reminded_30m", "ALTER TABLE free_trials ADD COLUMN reminded_30m INTEGER DEFAULT 0"),
    ("free_trials", "reminded_expired", "ALTER TABLE free_trials ADD COLUMN reminded_expired INTEGER DEFAULT 0"),
    ("free_trials", "username", "ALTER TABLE free_trials ADD COLUMN username TEXT"),
    ("free_trials", "created_at", "ALTER TABLE free_trials ADD COLUMN created_at TIMESTAMP"),
    # users
    ("users", "first_name", "ALTER TABLE users ADD COLUMN first_name TEXT"),
    ("users", "username", "ALTER TABLE users ADD COLUMN username TEXT"),
    ("users", "created_at", "ALTER TABLE users ADD COLUMN created_at TIMESTAMP"),
    # game_passes
    ("game_passes", "order_id", "ALTER TABLE game_passes ADD COLUMN order_id TEXT"),
    ("game_passes", "total_passes", "ALTER TABLE game_passes ADD COLUMN total_passes INTEGER DEFAULT 0"),
    ("game_passes", "remaining_passes", "ALTER TABLE game_passes ADD COLUMN remaining_passes INTEGER DEFAULT 0"),
    ("game_passes", "expires_at", "ALTER TABLE game_passes ADD COLUMN expires_at TIMESTAMP"),
    ("game_passes", "created_at", "ALTER TABLE game_passes ADD COLUMN created_at TIMESTAMP"),
    # pass_redemptions
    ("pass_redemptions", "pass_id", "ALTER TABLE pass_redemptions ADD COLUMN pass_id INTEGER"),
    ("pass_redemptions", "username", "ALTER TABLE pass_redemptions ADD COLUMN username TEXT"),
    ("pass_redemptions", "password", "ALTER TABLE pass_redemptions ADD COLUMN password TEXT"),
    ("pass_redemptions", "m3u_url", "ALTER TABLE pass_redemptions ADD COLUMN m3u_url TEXT"),
    ("pass_redemptions", "redeemed_at", "ALTER TABLE pass_redemptions ADD COLUMN redeemed_at TIMESTAMP"),
    ("pass_redemptions", "expires_at", "ALTER TABLE pass_redemptions ADD COLUMN expires_at TIMESTAMP"),
    # coupons
    ("coupons", "discount_pct", "ALTER TABLE coupons ADD COLUMN discount_pct INTEGER"),
    ("coupons", "max_uses", "ALTER TABLE coupons ADD COLUMN max_uses INTEGER DEFAULT 1"),
    ("coupons", "used_count", "ALTER TABLE coupons ADD COLUMN used_count INTEGER DEFAULT 0"),
    ("coupons", "created_by", "ALTER TABLE coupons ADD COLUMN created_by TEXT"),
    ("coupons", "created_at", "ALTER TABLE coupons ADD COLUMN created_at TIMESTAMP"),
]

# Colunas de data que devem ser retro-preenchidas quando criadas via ALTER.
TIMESTAMP_BACKFILL = [
    ("orders", "created_at"), ("orders", "updated_at"),
    ("free_trials", "created_at"),
    ("users", "created_at"),
    ("game_passes", "created_at"),
    ("pass_redemptions", "redeemed_at"),
    ("coupons", "created_at"),
]

# Índices (idempotentes).  (nome, DDL, único?)
INDEXES = [
    ("idx_orders_user_id", "CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)", False),
    ("idx_orders_payment_id", "CREATE INDEX IF NOT EXISTS idx_orders_payment_id ON orders(payment_id)", False),
    ("idx_orders_status_expires", "CREATE INDEX IF NOT EXISTS idx_orders_status_expires ON orders(status, expires_at)", False),
    ("idx_free_trials_user_id", "CREATE INDEX IF NOT EXISTS idx_free_trials_user_id ON free_trials(user_id)", False),
    ("idx_game_passes_user_id", "CREATE INDEX IF NOT EXISTS idx_game_passes_user_id ON game_passes(user_id, remaining_passes)", False),
    ("idx_pass_redemptions_user_id", "CREATE INDEX IF NOT EXISTS idx_pass_redemptions_user_id ON pass_redemptions(user_id)", False),
    ("idx_coupons_code", "CREATE UNIQUE INDEX IF NOT EXISTS idx_coupons_code ON coupons(code)", True),
]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def connect(db_path=None):
    """Abre conexão com o banco (row_factory de dicionário não é usado para
    manter compatibilidade com os `fetchone()[0]` do bot)."""
    path = db_path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    return conn


def _table_exists(cursor, table):
    return cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _columns(cursor, table):
    return {row[1] for row in cursor.execute('PRAGMA table_info("%s")' % table)}


def _ensure_migrations_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            description TEXT,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


# --------------------------------------------------------------------------
# init_db / migrate
# --------------------------------------------------------------------------
def init_db(db_path=None, verbose=False):
    """Cria o schema se necessário e aplica migrações idempotentes.

    Retorna um dict com o que foi criado/alterado (para log/auditoria).
    """
    created_tables, added_columns, created_indexes, warnings = [], [], [], []

    conn = connect(db_path)
    try:
        cursor = conn.cursor()
        _ensure_migrations_table(cursor)

        # 1) Criar tabelas que não existem (com o schema COMPLETO atual)
        for table, ddl in SCHEMA.items():
            if not _table_exists(cursor, table):
                cursor.execute(ddl)
                created_tables.append(table)
                if verbose:
                    print("[migrate] tabela criada: %s" % table)

        # 2) ADD COLUMN para bases legadas (só o que falta)
        for table, column, ddl in COLUMN_MIGRATIONS:
            if not _table_exists(cursor, table):
                continue
            if column not in _columns(cursor, table):
                try:
                    cursor.execute(ddl)
                    added_columns.append("%s.%s" % (table, column))
                    if verbose:
                        print("[migrate] coluna adicionada: %s.%s" % (table, column))
                except sqlite3.OperationalError as exc:
                    warnings.append("falha ao adicionar %s.%s: %s" % (table, column, exc))

        # 3) Retro-preencher timestamps criados por ALTER (nulos => now)
        for table, column in TIMESTAMP_BACKFILL:
            if not _table_exists(cursor, table) or column not in _columns(cursor, table):
                continue
            try:
                cursor.execute(
                    'UPDATE "%s" SET "%s" = CURRENT_TIMESTAMP WHERE "%s" IS NULL'
                    % (table, column, column)
                )
            except sqlite3.OperationalError as exc:  # pragma: no cover
                warnings.append("backfill %s.%s: %s" % (table, column, exc))

        # 4) Índices
        for name, ddl, is_unique in INDEXES:
            try:
                cursor.execute(ddl)
                created_indexes.append(name)
            except sqlite3.IntegrityError as exc:
                warnings.append("indice unico %s nao criado (dados duplicados): %s" % (name, exc))
            except sqlite3.OperationalError as exc:
                warnings.append("indice %s: %s" % (name, exc))

        # 5) Registrar versão aplicada
        cursor.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, description) VALUES (?, ?)",
            (SCHEMA_VERSION, MIGRATION_NOTES.get(SCHEMA_VERSION, "schema update")),
        )
        for version, note in MIGRATION_NOTES.items():
            cursor.execute(
                "INSERT OR IGNORE INTO schema_migrations (version, description) VALUES (?, ?)",
                (version, note),
            )

        conn.commit()
    finally:
        conn.close()

    return {
        "db_path": db_path or DB_PATH,
        "schema_version": SCHEMA_VERSION,
        "created_tables": created_tables,
        "added_columns": added_columns,
        "indexes": created_indexes,
        "warnings": warnings,
    }


def verify_schema(db_path=None):
    """Confere se o banco contém tudo o que o código espera.

    Retorna {"ok": bool, "missing_tables": [...], "missing_columns": [...],
             "integrity": str, "foreign_key_errors": [...]}.
    """
    path = db_path or DB_PATH
    missing_tables, missing_columns = [], []

    if not os.path.exists(path):
        return {"ok": False, "db_path": path, "missing_tables": list(SCHEMA.keys()),
                "missing_columns": [], "integrity": "db inexistente", "foreign_key_errors": []}

    # colunas esperadas = DDL da tabela + colunas que as migrações garantem
    expected = {}
    for table, ddl in SCHEMA.items():
        cols = set()
        for line in ddl.splitlines():
            line = line.strip()
            if not line or line.lower().startswith(("create table", ")", "(")):
                continue
            cols.add(line.split()[0].strip(","))
        expected[table] = cols
    for table, column, _ in COLUMN_MIGRATIONS:
        expected.setdefault(table, set()).add(column)

    conn = sqlite3.connect(path)
    try:
        cursor = conn.cursor()
        integrity = cursor.execute("PRAGMA integrity_check").fetchone()[0]
        try:
            fk_errors = cursor.execute("PRAGMA foreign_key_check").fetchall()
        except sqlite3.OperationalError:
            fk_errors = []
        for table, cols in expected.items():
            if not _table_exists(cursor, table):
                missing_tables.append(table)
                continue
            have = _columns(cursor, table)
            for col in sorted(cols - have):
                missing_columns.append("%s.%s" % (table, col))
    finally:
        conn.close()

    return {
        "ok": integrity == "ok" and not missing_tables and not missing_columns,
        "db_path": path,
        "missing_tables": sorted(missing_tables),
        "missing_columns": sorted(missing_columns),
        "integrity": integrity,
        "foreign_key_errors": fk_errors,
    }


def schema_fingerprint(db_path=None):
    """Assinatura ordenada do schema — útil para comparar bancos/ambientes."""
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    try:
        parts = []
        for name, sql in conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ):
            cols = []
            for row in conn.execute('PRAGMA table_info("%s")' % name):
                cols.append(row[1])
            parts.append(name + "(" + ",".join(sorted(cols)) + ")")
        return "|".join(parts)
    finally:
        conn.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    target = DB_PATH
    if "--db" in args:
        target = args[args.index("--db") + 1]

    if "--check" in args:
        result = verify_schema(target)
        print("verificacao de schema: %s" % ("OK" if result["ok"] else "DIVERGENTE"))
        if result["missing_tables"]:
            print("  tabelas ausentes: %s" % ", ".join(result["missing_tables"]))
        if result["missing_columns"]:
            print("  colunas ausentes: %s" % ", ".join(result["missing_columns"]))
        print("  integrity_check: %s" % result["integrity"])
        sys.exit(0 if result["ok"] else 1)

    report = init_db(target, verbose=True)
    print("Banco Nexus PlayTV inicializado/migrado: %s" % report["db_path"])
    print("  schema_version=%s" % report["schema_version"])
    print("  tabelas criadas: %s" % (report["created_tables"] or "-"))
    print("  colunas adicionadas: %s" % (report["added_columns"] or "-"))
    if report["warnings"]:
        for w in report["warnings"]:
            print("  AVISO: %s" % w)
