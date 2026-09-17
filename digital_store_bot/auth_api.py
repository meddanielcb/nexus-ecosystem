"""
auth_api.py — Autenticação sem senha (Magic OTP) para o Nexus PlayTV.

Fluxo:
  1. POST /api/auth/otp/request  -> request_otp(contact_type, contact_val, fingerprint, ip)
     Gera um código de 6 dígitos, grava uma sessão pendente em web_auth_sessions
     e dispara o código via WhatsApp (Evolution API) ou E-mail (Resend).
  2. POST /api/auth/otp/verify   -> verify_otp(session_token, otp_code)
     Valida o código (máx. 3 tentativas erradas, expira em 10 minutos).
     Em caso de sucesso, cria (ou recupera) a carteira do cliente em
     web_user_wallets e retorna os dados da carteira.
  3. GET  /api/auth/wallet       -> get_wallet(wallet_id=..., session_token=...)
     Retorna os dados da carteira do cliente já autenticado.

Nenhuma senha é usada em nenhum momento — a "wallet" é reconhecida pelo
contato (WhatsApp/e-mail) + fingerprint do dispositivo, validado por OTP.
"""
import sqlite3
import random
import string
import secrets
import json
import os
import re
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# Configuração / caminhos
# ---------------------------------------------------------------------------
# Caminho real usado em produção (VPS Njalla) pelo restante do sistema
# (webhook_server.py, checkout_api.py etc). Mantemos uma lista de candidatos
# para funcionar tanto no ambiente de deploy quanto no repositório de dev.
DB_PATH_CANDIDATES = [
    os.environ.get("PLAYTV_DB_PATH", ""),
    "/opt/data/nexus_playtv_bot/data/playtv.db",
    "/opt/nexus_repo/nexus_playtv_bot/data/playtv.db",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "nexus_playtv_bot", "data", "playtv.db"),
]

# Variável mutável em nível de módulo — testes podem sobrescrever
# `auth_api.DB_PATH = "/tmp/algum.db"` antes de chamar as funções.
DB_PATH = next((p for p in DB_PATH_CANDIDATES if p and os.path.exists(p)), DB_PATH_CANDIDATES[1])

EVOLUTION_URL = os.environ.get("EVOLUTION_URL", "http://127.0.0.1:8080")
EVOLUTION_INSTANCE = os.environ.get("EVOLUTION_INSTANCE", "nexus-playtv-1")
EVOLUTION_COMPOSE_PATH = "/opt/evolution-api/docker-compose.yml"

RESEND_API_URL = "https://api.resend.com/emails"
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "Nexus PlayTV <auth@nexusplay.tv>")

MAX_ATTEMPTS = 3
OTP_TTL_MINUTES = 10
RATE_LIMIT_WINDOW_MINUTES = 60
RATE_LIMIT_MAX_REQUESTS = 5

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthError(Exception):
    """Erro de validação/negócio -> devolvido ao cliente com status HTTP."""
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _evolution_api_key():
    """Lê a API key da Evolution API: env var tem prioridade; senão tenta
    ler do docker-compose.yml da VPS (onde o serviço realmente roda)."""
    key = os.environ.get("EVOLUTION_API_KEY", "")
    if key:
        return key
    try:
        with open(EVOLUTION_COMPOSE_PATH) as f:
            for line in f:
                if "AUTHENTICATION_API_KEY=" in line:
                    return line.split("AUTHENTICATION_API_KEY=")[1].strip()
    except Exception:
        pass
    return ""


def _resend_api_key():
    return os.environ.get("RESEND_API_KEY", "")


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
def db_connect():
    """Conecta ao banco definido em DB_PATH. Não há fallback dinâmico aqui:
    a resolução de caminho acontece uma única vez, no import do módulo
    (ou explicitamente, quando um teste sobrescreve `auth_api.DB_PATH`).
    Um fallback baseado em `os.path.exists` a cada chamada é perigoso:
    um arquivo sqlite novo (de teste, por ex.) só passa a existir depois
    da primeira conexão, então checar existência antes de conectar faria
    o código cair silenciosamente no banco de produção."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_schema(conn=None):
    """Cria as tabelas caso ainda não existam (idempotente). Útil para testes
    e para ambientes novos onde a migração ainda não rodou."""
    own_conn = conn is None
    conn = conn or db_connect()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS web_auth_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_token TEXT NOT NULL,
            contact_type TEXT NOT NULL,
            contact_val TEXT NOT NULL,
            otp_code TEXT NOT NULL,
            fingerprint TEXT,
            ip_address TEXT,
            attempts INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        )
    """)
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
    conn.commit()
    if own_conn:
        conn.close()


# ---------------------------------------------------------------------------
# Validação de entrada
# ---------------------------------------------------------------------------
def _normalize_phone(phone: str) -> str:
    clean = "".join(filter(str.isdigit, phone or ""))
    if clean and not clean.startswith("55") and len(clean) in (10, 11):
        clean = "55" + clean
    return clean


def _validate_contact(contact_type: str, contact_val: str) -> str:
    if contact_type not in ("whatsapp", "email"):
        raise AuthError("contact_type deve ser 'whatsapp' ou 'email'.")
    if not contact_val or not str(contact_val).strip():
        raise AuthError("contact_val é obrigatório.")
    if contact_type == "email":
        if not EMAIL_RE.match(contact_val.strip()):
            raise AuthError("E-mail inválido.")
        return contact_val.strip().lower()
    else:
        normalized = _normalize_phone(contact_val)
        if len(normalized) < 12:
            raise AuthError("Número de WhatsApp inválido.")
        return normalized


def generate_otp() -> str:
    """Gera um código numérico de 6 dígitos criptograficamente seguro."""
    return "".join(secrets.choice(string.digits) for _ in range(6))


# ---------------------------------------------------------------------------
# Disparo do código
# ---------------------------------------------------------------------------
def send_whatsapp_otp(phone: str, code: str) -> bool:
    clean_phone = _normalize_phone(phone)
    url = f"{EVOLUTION_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    headers = {
        "apikey": _evolution_api_key(),
        "Content-Type": "application/json",
    }
    msg = (
        f"🔐 *NEXUS PLAYTV — Código de Acesso*\n\n"
        f"Seu código de validação é: *{code}*\n\n"
        f"Válido por {OTP_TTL_MINUTES} minutos. Nunca compartilhe este código."
    )
    payload = {
        "number": clean_phone,
        "options": {"delay": 1200, "presence": "composing"},
        "textMessage": {"text": msg},
    }
    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(), headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status in (200, 201)
    except Exception as e:
        print(f"[AUTH_API] Erro ao disparar WhatsApp OTP para {clean_phone}: {e}")
        return False


def send_email_otp(email: str, code: str) -> bool:
    """Dispara o código via Resend (API REST, sem SDK)."""
    api_key = _resend_api_key()
    if not api_key:
        print("[AUTH_API] RESEND_API_KEY não configurada — e-mail OTP não enviado.")
        return False

    html = (
        f"<div style='font-family:sans-serif;padding:24px'>"
        f"<h2>Nexus PlayTV — Código de Acesso</h2>"
        f"<p>Seu código de validação é:</p>"
        f"<p style='font-size:32px;font-weight:bold;letter-spacing:4px'>{code}</p>"
        f"<p>Válido por {OTP_TTL_MINUTES} minutos. Nunca compartilhe este código.</p>"
        f"</div>"
    )
    payload = {
        "from": RESEND_FROM_EMAIL,
        "to": [email],
        "subject": "Seu código de acesso Nexus PlayTV",
        "html": html,
    }
    try:
        req = urllib.request.Request(
            RESEND_API_URL,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status in (200, 201)
    except Exception as e:
        print(f"[AUTH_API] Erro ao disparar e-mail OTP para {email}: {e}")
        return False


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------
def request_otp(contact_type: str, contact_val: str, fingerprint: str = "", ip: str = "") -> dict:
    contact_val = _validate_contact(contact_type, contact_val)

    conn = db_connect()
    ensure_schema(conn)
    c = conn.cursor()

    # 1. Anti-abuso: limita pedidos recentes por contato OU por fingerprint/IP.
    c.execute(
        f"""
        SELECT COUNT(*) FROM web_auth_sessions
        WHERE (contact_val = ? OR fingerprint = ? OR ip_address = ?)
          AND created_at > datetime('now', '-{RATE_LIMIT_WINDOW_MINUTES} minutes')
        """,
        (contact_val, fingerprint, ip),
    )
    if c.fetchone()[0] >= RATE_LIMIT_MAX_REQUESTS:
        conn.close()
        raise AuthError("Muitas tentativas recentes. Aguarde 1 hora e tente novamente.", status=429)

    otp = generate_otp()
    session_token = "SESS_" + secrets.token_hex(16)

    c.execute(
        f"""
        INSERT INTO web_auth_sessions
            (session_token, contact_type, contact_val, otp_code, fingerprint, ip_address, attempts, status, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, 0, 'pending', datetime('now', '+{OTP_TTL_MINUTES} minutes'))
        """,
        (session_token, contact_type, contact_val, otp, fingerprint, ip),
    )
    conn.commit()
    conn.close()

    sent = send_whatsapp_otp(contact_val, otp) if contact_type == "whatsapp" else send_email_otp(contact_val, otp)

    return {
        "ok": True,
        "session_token": session_token,
        "sent": sent,
        "expires_in": OTP_TTL_MINUTES * 60,
        "message": f"Código de 6 dígitos enviado para seu {contact_type}!",
    }


def verify_otp(session_token, otp_code) -> dict:
    if not session_token or not otp_code:
        raise AuthError("session_token e otp_code são obrigatórios.")

    conn = db_connect()
    ensure_schema(conn)
    c = conn.cursor()
    c.execute(
        """
        SELECT id, contact_type, contact_val, otp_code, fingerprint, attempts, status
        FROM web_auth_sessions
        WHERE session_token = ?
        """,
        (session_token,),
    )
    row = c.fetchone()

    if not row:
        conn.close()
        raise AuthError("Sessão inválida.", status=404)

    sess_id, contact_type, contact_val, real_otp, fingerprint, attempts, status = row

    # Expiração por tempo (10 min) mesmo se o status ainda estiver 'pending'.
    c.execute(
        "SELECT (expires_at <= datetime('now')) FROM web_auth_sessions WHERE id = ?",
        (sess_id,),
    )
    is_time_expired = bool(c.fetchone()[0])

    if status != "pending" or is_time_expired:
        if status == "pending" and is_time_expired:
            c.execute("UPDATE web_auth_sessions SET status = 'expired' WHERE id = ?", (sess_id,))
            conn.commit()
        conn.close()
        raise AuthError("Sessão expirada ou já utilizada. Solicite um novo código.", status=410)

    if attempts >= MAX_ATTEMPTS:
        c.execute("UPDATE web_auth_sessions SET status = 'expired' WHERE id = ?", (sess_id,))
        conn.commit()
        conn.close()
        raise AuthError("Limite de tentativas excedido. Solicite um novo código.", status=429)

    if otp_code.strip() != real_otp:
        c.execute("UPDATE web_auth_sessions SET attempts = attempts + 1 WHERE id = ?", (sess_id,))
        conn.commit()
        new_attempts = attempts + 1
        conn.close()
        remaining = max(0, MAX_ATTEMPTS - new_attempts)
        if remaining == 0:
            raise AuthError("Código incorreto. Limite de tentativas excedido.", status=429)
        raise AuthError(f"Código incorreto. Restam {remaining} tentativa(s).", status=400)

    # Sucesso — marca sessão como verificada.
    c.execute("UPDATE web_auth_sessions SET status = 'verified' WHERE id = ?", (sess_id,))

    # Cria ou recupera a carteira do cliente.
    c.execute(
        """
        SELECT wallet_id, free_trial_claimed, trial_credentials, referral_code, referral_days_balance
        FROM web_user_wallets WHERE contact_val = ?
        """,
        (contact_val,),
    )
    wallet_row = c.fetchone()

    if not wallet_row:
        wallet_id = "WLT_" + secrets.token_hex(8).upper()
        ref_code = "NX" + secrets.token_hex(4).upper()
        c.execute(
            """
            INSERT INTO web_user_wallets
                (wallet_id, contact_type, contact_val, fingerprint, referral_code, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            """,
            (wallet_id, contact_type, contact_val, fingerprint, ref_code),
        )
        trial_claimed, trial_cred, ref_balance = 0, None, 0
    else:
        wallet_id, trial_claimed, trial_cred, ref_code, ref_balance = wallet_row
        c.execute(
            "UPDATE web_user_wallets SET fingerprint = ?, updated_at = datetime('now') WHERE wallet_id = ?",
            (fingerprint, wallet_id),
        )

    conn.commit()
    conn.close()

    return {
        "ok": True,
        "session_token": session_token,
        "wallet": {
            "wallet_id": wallet_id,
            "contact_val": contact_val,
            "contact_type": contact_type,
            "trial_claimed": bool(trial_claimed),
            "trial_credentials": json.loads(trial_cred) if trial_cred else None,
            "referral_code": ref_code,
            "referral_days_balance": ref_balance,
        },
    }


def get_wallet(wallet_id=None, session_token=None) -> dict:
    if not wallet_id and not session_token:
        raise AuthError("Informe wallet_id ou session_token.")

    conn = db_connect()
    ensure_schema(conn)
    c = conn.cursor()

    if not wallet_id and session_token:
        c.execute(
            "SELECT contact_val, status FROM web_auth_sessions WHERE session_token = ?",
            (session_token,),
        )
        row = c.fetchone()
        if not row:
            conn.close()
            raise AuthError("Sessão inválida.", status=404)
        contact_val, status = row
        if status != "verified":
            conn.close()
            raise AuthError("Sessão ainda não verificada.", status=403)
        c.execute(
            """
            SELECT wallet_id, contact_type, contact_val, free_trial_claimed,
                   trial_credentials, referral_code, referred_by, referral_days_balance
            FROM web_user_wallets WHERE contact_val = ?
            """,
            (contact_val,),
        )
    else:
        c.execute(
            """
            SELECT wallet_id, contact_type, contact_val, free_trial_claimed,
                   trial_credentials, referral_code, referred_by, referral_days_balance
            FROM web_user_wallets WHERE wallet_id = ?
            """,
            (wallet_id,),
        )

    row = c.fetchone()
    conn.close()

    if not row:
        raise AuthError("Carteira não encontrada.", status=404)

    (wallet_id, contact_type, contact_val, trial_claimed,
     trial_cred, ref_code, referred_by, ref_balance) = row

    return {
        "ok": True,
        "wallet": {
            "wallet_id": wallet_id,
            "contact_type": contact_type,
            "contact_val": contact_val,
            "trial_claimed": bool(trial_claimed),
            "trial_credentials": json.loads(trial_cred) if trial_cred else None,
            "referral_code": ref_code,
            "referred_by": referred_by,
            "referral_days_balance": ref_balance,
        },
    }
