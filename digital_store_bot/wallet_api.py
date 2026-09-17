"""
wallet_api.py — Engine de Carteira do Usuário, Amarração Antifraude do Teste
de 4 Horas e Liberação Condicionada à Instalação do PWA (Nexus PlayTV).

Depende de `auth_api.py` (autenticação sem senha / OTP) já ter criado a
carteira em `web_user_wallets`. Este módulo NUNCA autentica ninguém: ele só
libera benefícios (teste grátis, listagem de credenciais) para uma
`wallet_id` que já existe.

Fluxo:
  1. POST /api/pwa/installed      -> register_pwa_install(...)
     Chamado quando o evento `appinstalled` (ou gatilho equivalente) do PWA
     confirma a instalação no dispositivo do cliente. Grava em `pwa_installs`.
     Sem este registro, `claim_trial()` nunca libera o teste — é a "Regra de
     Ouro" do funil de retenção descrita no roadmap do produto.
  2. POST /api/trial/claim        -> claim_trial(payload, request_ip)
     Regras, todas obrigatórias e verificadas nesta ordem:
       a) `wallet_id` presente e existente em `web_user_wallets` (carteira
          autenticada por OTP em auth_api.py). Sem carteira, 401.
       b) Amarração antifraude: nem o fingerprint do dispositivo, nem o
          contato (WhatsApp/e-mail) da carteira, nem a subrede do IP de
          origem podem já ter consumido um teste grátis em OUTRA carteira.
       c) PWA instalado: precisa existir um registro em `pwa_installs` para
          esta wallet_id ou fingerprint.
     Só então chama `create_masterx_line(is_trial=True)` (masterx_api.py) —
     que já garante, por conta própria (P0-3), que nenhuma credencial
     fictícia é devolvida em caso de erro/limite do fornecedor. O resultado é
     gravado em `web_user_wallets.trial_credentials`, em `orders` (order_id
     `TRIAL_...`, product_id `trial_4h`) e em `free_trials` (auditoria
     antifraude: fingerprint/ip/wallet_id de quem consumiu o teste).
  3. GET  /api/wallet/credentials -> get_wallet_credentials(wallet_id)
     Agrega, em um único payload, tudo que está ativo na carteira do
     cliente: teste grátis, assinaturas pagas e passes de jogo com saldo —
     para a tela "Minha Carteira" do PWA.
"""
import json
import os
import re
import secrets
import sqlite3
import sys
from datetime import datetime, timedelta

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

# masterx_api.py mora em nexus_playtv_bot — os mesmos candidatos de path
# usados pelo restante do ecossistema (produção na VPS e checkout de dev).
for _cand in (
    "/opt/data/nexus_playtv_bot",
    "/opt/nexus_repo/nexus_playtv_bot",
    os.path.join(_THIS_DIR, "..", "nexus_playtv_bot"),
):
    if _cand and _cand not in sys.path:
        sys.path.insert(0, _cand)

from masterx_api import create_masterx_line, MasterXError, MasterXTrialLimitReached  # noqa: E402

DB_PATH_CANDIDATES = [
    os.environ.get("PLAYTV_DB_PATH", ""),
    "/opt/data/nexus_playtv_bot/data/playtv.db",
    "/opt/nexus_repo/nexus_playtv_bot/data/playtv.db",
    os.path.join(_THIS_DIR, "..", "nexus_playtv_bot", "data", "playtv.db"),
]
DB_PATH = next((p for p in DB_PATH_CANDIDATES if p and os.path.exists(p)), DB_PATH_CANDIDATES[1])

TRIAL_HOURS = 4
OFFICIAL_SERVER_URL = "http://atmt.space"
PARTNER_CODE = "00042"
DATE_FMT = "%Y-%m-%d %H:%M:%S"


class WalletError(Exception):
    """Erro de validação/negócio -> devolvido ao cliente com status HTTP."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
def db_connect():
    path = DB_PATH if os.path.exists(DB_PATH) else next(
        (p for p in DB_PATH_CANDIDATES if p and os.path.exists(p)), DB_PATH
    )
    conn = sqlite3.connect(path, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def ensure_schema(conn=None):
    """Garante as tabelas/colunas usadas aqui, mesmo num banco onde
    db.py/auth_api.py ainda não tenham rodado (idempotente, nunca derruba
    dados existentes)."""
    own = conn is None
    conn = conn or db_connect()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS web_user_wallets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet_id TEXT NOT NULL,
            contact_type TEXT NOT NULL,
            contact_val TEXT NOT NULL,
            fingerprint TEXT,
            free_trial_claimed INTEGER DEFAULT 0,
            trial_credentials TEXT,
            referral_code TEXT,
            referred_by TEXT,
            referral_days_balance INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS pwa_installs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet_id TEXT,
            fingerprint TEXT,
            ip_address TEXT,
            user_agent TEXT,
            installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
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
    """)
    c.execute("""
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS game_passes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            order_id TEXT,
            total_passes INTEGER DEFAULT 0,
            remaining_passes INTEGER DEFAULT 0,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    for table, col, ddl in (
        ("free_trials", "wallet_id", "ALTER TABLE free_trials ADD COLUMN wallet_id TEXT"),
        ("free_trials", "fingerprint", "ALTER TABLE free_trials ADD COLUMN fingerprint TEXT"),
        ("free_trials", "ip_address", "ALTER TABLE free_trials ADD COLUMN ip_address TEXT"),
        ("orders", "wallet_id", "ALTER TABLE orders ADD COLUMN wallet_id TEXT"),
    ):
        cols = {r[1] for r in c.execute('PRAGMA table_info("%s")' % table)}
        if col not in cols:
            try:
                c.execute(ddl)
            except sqlite3.OperationalError:
                pass
    conn.commit()
    if own:
        conn.close()


# ---------------------------------------------------------------------------
# Antifraude
# ---------------------------------------------------------------------------
def _subnet(ip: str) -> str:
    """Reduz um IPv4 ao prefixo /24 e um IPv6 aos 4 primeiros grupos.

    É apenas um sinal antifraude adicional (proxies/CGNAT compartilham
    subrede legitimamente) — nunca a única razão para bloquear sozinha em
    definitivo, mas soma-se ao fingerprint e ao contato.
    """
    if not ip:
        return ""
    ip = ip.strip()
    if ":" in ip:  # IPv6
        return ":".join(ip.split(":")[:4])
    parts = ip.split(".")
    if len(parts) == 4:
        return ".".join(parts[:3])
    return ip


def _wallet_row(conn, wallet_id):
    c = conn.cursor()
    c.execute(
        """
        SELECT wallet_id, contact_type, contact_val, fingerprint, free_trial_claimed,
               trial_credentials, referral_code, referred_by, referral_days_balance
        FROM web_user_wallets WHERE wallet_id = ?
        """,
        (wallet_id,),
    )
    return c.fetchone()


def _antifraud_reason(conn, wallet_id, fingerprint, contact_val, ip):
    """Retorna uma mensagem se o fingerprint, o contato ou a subrede de IP já
    consumiram um teste grátis em OUTRA carteira; None se estiver liberado."""
    c = conn.cursor()

    if fingerprint:
        c.execute(
            """
            SELECT 1 FROM web_user_wallets
            WHERE fingerprint = ? AND free_trial_claimed = 1 AND wallet_id != ?
            LIMIT 1
            """,
            (fingerprint, wallet_id),
        )
        if c.fetchone():
            return "Este dispositivo já utilizou o teste grátis de 4 horas."

    if contact_val:
        c.execute(
            """
            SELECT 1 FROM web_user_wallets
            WHERE contact_val = ? AND free_trial_claimed = 1 AND wallet_id != ?
            LIMIT 1
            """,
            (contact_val, wallet_id),
        )
        if c.fetchone():
            return "Este contato (WhatsApp/e-mail) já utilizou o teste grátis de 4 horas."

    subnet = _subnet(ip)
    if subnet:
        c.execute(
            """
            SELECT 1 FROM free_trials
            WHERE ip_address LIKE ? AND (wallet_id IS NULL OR wallet_id != ?)
            LIMIT 1
            """,
            (subnet + "%", wallet_id),
        )
        if c.fetchone():
            return "Já existe um teste grátis recente originado desta rede/IP."

    return None


def _pwa_installed(conn, wallet_id, fingerprint):
    c = conn.cursor()
    if wallet_id:
        c.execute("SELECT 1 FROM pwa_installs WHERE wallet_id = ? LIMIT 1", (wallet_id,))
        if c.fetchone():
            return True
    if fingerprint:
        c.execute("SELECT 1 FROM pwa_installs WHERE fingerprint = ? LIMIT 1", (fingerprint,))
        if c.fetchone():
            return True
    return False


# ---------------------------------------------------------------------------
# POST /api/pwa/installed
# ---------------------------------------------------------------------------
def register_pwa_install(wallet_id=None, fingerprint=None, ip=None, user_agent=None) -> dict:
    wallet_id = (wallet_id or "").strip() or None
    fingerprint = (fingerprint or "").strip() or None
    if not wallet_id and not fingerprint:
        raise WalletError("wallet_id ou fingerprint é obrigatório para confirmar a instalação.", status=400)

    conn = db_connect()
    ensure_schema(conn)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO pwa_installs (wallet_id, fingerprint, ip_address, user_agent)
        VALUES (?, ?, ?, ?)
        """,
        (wallet_id, fingerprint, ip, user_agent),
    )
    conn.commit()
    conn.close()
    return {
        "ok": True,
        "installed": True,
        "message": "Instalação do PWA confirmada. Teste grátis de 4 horas liberado.",
    }


# ---------------------------------------------------------------------------
# POST /api/trial/claim
# ---------------------------------------------------------------------------
def claim_trial(payload: dict, request_ip: str = None) -> dict:
    payload = payload or {}
    wallet_id = (payload.get("wallet_id") or "").strip()
    fingerprint = (payload.get("fingerprint") or "").strip()
    # O IP detectado pelo próprio servidor (request_ip) tem prioridade sobre
    # qualquer valor enviado no corpo — não confiamos em IP informado pelo cliente.
    ip = (request_ip or payload.get("ip") or "").strip()

    if not wallet_id:
        raise WalletError(
            "Carteira não autenticada. Faça login com WhatsApp ou e-mail antes de solicitar o teste.",
            status=401,
        )

    conn = db_connect()
    ensure_schema(conn)

    row = _wallet_row(conn, wallet_id)
    if not row:
        conn.close()
        raise WalletError("Carteira não encontrada. Autentique-se novamente.", status=404)

    (wallet_id, contact_type, contact_val, wallet_fp, trial_claimed,
     trial_cred_json, ref_code, referred_by, ref_balance) = row

    effective_fp = fingerprint or wallet_fp or ""

    # Idempotência: se já reclamou, devolve o que já existe — nunca emite
    # uma segunda linha no MasterX para a mesma carteira.
    if trial_claimed:
        conn.close()
        cred = json.loads(trial_cred_json) if trial_cred_json else None
        if not cred:
            raise WalletError("Teste grátis já utilizado nesta carteira.", status=409)
        return {
            "ok": True,
            "already_claimed": True,
            "wallet_id": wallet_id,
            "trial": cred,
        }

    fraud_reason = _antifraud_reason(conn, wallet_id, effective_fp, contact_val, ip)
    if fraud_reason:
        conn.close()
        raise WalletError(fraud_reason, status=403)

    if not _pwa_installed(conn, wallet_id, effective_fp):
        conn.close()
        raise WalletError(
            "Instale o app (adicione à tela inicial) para liberar seu teste grátis de 4 horas.",
            status=412,  # Precondition Failed: PWA ainda não confirmado
        )

    conn.close()

    # Chamada de rede real ao painel do fornecedor — fora da conexão SQLite.
    # is_trial=True já limita a linha a 4h (masterx_api.py); nunca fabricamos
    # credencial: qualquer erro do fornecedor sobe como WalletError.
    phone = contact_val if contact_type == "whatsapp" else None
    try:
        cred = create_masterx_line(is_trial=True, phone=phone)
    except MasterXTrialLimitReached as e:
        raise WalletError(str(e), status=429) from e
    except MasterXError as e:
        raise WalletError(str(e), status=502) from e

    now = datetime.utcnow()
    expires_at = (now + timedelta(hours=TRIAL_HOURS)).strftime(DATE_FMT)
    server_url = cred.get("server_url") or OFFICIAL_SERVER_URL

    trial_payload = {
        "type": "trial",
        "partner_code": PARTNER_CODE,
        "username": cred.get("username"),
        "password": cred.get("password"),
        "server_url": server_url,
        "m3u_url": cred.get("m3u_url"),
        "m3u_hls": cred.get("m3u_hls"),
        "web_player": cred.get("web_player"),
        "duration_hours": TRIAL_HOURS,
        "claimed_at": now.strftime(DATE_FMT),
        "expires_at": expires_at,
    }
    cred_str = (
        f"Código Parceiro: {PARTNER_CODE} | Usuário: {cred.get('username')} | "
        f"Senha: {cred.get('password')} | Servidor: {server_url}"
    )
    order_id = "TRIAL_" + secrets.token_hex(6).upper()

    conn = db_connect()
    c = conn.cursor()
    try:
        c.execute(
            """
            UPDATE web_user_wallets
            SET free_trial_claimed = 1,
                trial_credentials = ?,
                fingerprint = COALESCE(fingerprint, ?),
                updated_at = datetime('now')
            WHERE wallet_id = ?
            """,
            (json.dumps(trial_payload), fingerprint or None, wallet_id),
        )
        c.execute(
            """
            INSERT INTO orders
                (order_id, user_id, username, product_id, payment_method, amount,
                 status, payment_id, delivered_credentials, m3u_url, expires_at, wallet_id)
            VALUES (?, NULL, ?, 'trial_4h', 'free_trial_pwa', 0, 'paid', ?, ?, ?, ?, ?)
            """,
            (order_id, contact_val, str(cred.get("id") or ""), cred_str,
             trial_payload["m3u_url"], expires_at, wallet_id),
        )
        c.execute(
            """
            INSERT INTO free_trials
                (username, iptv_username, iptv_password, server_url, m3u_url,
                 expires_at, wallet_id, fingerprint, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (contact_val, cred.get("username"), cred.get("password"), server_url,
             trial_payload["m3u_url"], expires_at, wallet_id, effective_fp, ip),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "ok": True,
        "already_claimed": False,
        "wallet_id": wallet_id,
        "order_id": order_id,
        "trial": trial_payload,
    }


# ---------------------------------------------------------------------------
# GET /api/wallet/credentials
# ---------------------------------------------------------------------------
def _is_active(expires_at, now):
    if not expires_at:
        return True  # sem validade cadastrada (ex.: saldo de passes) = ainda ativo
    try:
        exp = datetime.strptime(str(expires_at)[:19], DATE_FMT)
    except ValueError:
        return True
    return exp > now


def get_wallet_credentials(wallet_id: str) -> dict:
    wallet_id = (wallet_id or "").strip()
    if not wallet_id:
        raise WalletError("wallet_id é obrigatório.", status=400)

    conn = db_connect()
    ensure_schema(conn)

    row = _wallet_row(conn, wallet_id)
    if not row:
        conn.close()
        raise WalletError("Carteira não encontrada.", status=404)

    (wallet_id, contact_type, contact_val, fingerprint, trial_claimed,
     trial_cred_json, ref_code, referred_by, ref_balance) = row

    now = datetime.utcnow()
    c = conn.cursor()

    c.execute(
        """
        SELECT order_id, product_id, payment_method, amount, status,
               delivered_credentials, m3u_url, expires_at, created_at
        FROM orders WHERE wallet_id = ? ORDER BY created_at DESC
        """,
        (wallet_id,),
    )
    order_rows = c.fetchall()

    trial_order = None
    subscriptions = []
    for (order_id, product_id, payment_method, amount, status, delivered_credentials,
         m3u_url, expires_at, created_at) in order_rows:
        if status != "paid":
            continue
        entry = {
            "order_id": order_id,
            "product_id": product_id,
            "payment_method": payment_method,
            "amount": amount,
            "delivered_credentials": delivered_credentials,
            "m3u_url": m3u_url,
            "expires_at": expires_at,
            "created_at": created_at,
            "active": _is_active(expires_at, now),
        }
        if product_id == "trial_4h":
            if trial_order is None:
                trial_order = entry
        else:
            subscriptions.append(entry)

    c.execute(
        """
        SELECT gp.id, gp.order_id, gp.total_passes, gp.remaining_passes, gp.expires_at, gp.created_at
        FROM game_passes gp
        JOIN orders o ON o.order_id = gp.order_id
        WHERE o.wallet_id = ? AND gp.remaining_passes > 0
        ORDER BY gp.created_at DESC
        """,
        (wallet_id,),
    )
    game_passes = [
        {
            "pass_id": pid,
            "order_id": order_id,
            "total_passes": total_passes,
            "remaining_passes": remaining_passes,
            "expires_at": expires_at,
            "created_at": created_at,
            "active": _is_active(expires_at, now),
        }
        for (pid, order_id, total_passes, remaining_passes, expires_at, created_at) in c.fetchall()
    ]

    conn.close()

    trial_credentials = json.loads(trial_cred_json) if trial_cred_json else None
    if trial_credentials:
        trial_credentials = dict(trial_credentials)
        trial_credentials["active"] = trial_order["active"] if trial_order else _is_active(
            trial_credentials.get("expires_at"), now
        )
        if trial_order:
            trial_credentials["order_id"] = trial_order["order_id"]

    return {
        "ok": True,
        "wallet_id": wallet_id,
        "contact_type": contact_type,
        "contact_val": contact_val,
        "referral_code": ref_code,
        "referred_by": referred_by,
        "referral_days_balance": ref_balance,
        "trial_claimed": bool(trial_claimed),
        "trial_credentials": trial_credentials,
        "active_subscriptions": [s for s in subscriptions if s["active"]],
        "subscription_history": subscriptions,
        "game_passes": [g for g in game_passes if g["active"]],
    }


if __name__ == "__main__":
    print("Módulo wallet_api pronto para importação.")
