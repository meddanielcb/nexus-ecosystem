import os
import sys
import time
import uuid
import random
import logging
import requests
from datetime import datetime, timedelta

logger = logging.getLogger("masterx_api")

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

MASTERX_API_URL = os.getenv("MASTERX_API_URL", "https://painelmaster.app/api.php")
MASTERX_API_KEY = os.getenv("MASTERX_API_KEY", "2d44e37a3f6e49f48e8c2b0934d58dd7")

# P0-4: domínios oficiais. Domínios legados (player.nexusplay.tv, cdn.nexusplay.tv,
# cdn-nexus.playtv.live) estão NXDOMAIN e nunca devem ser entregues ao cliente.
OFFICIAL_SERVER_URL = "http://atmt.space"
OFFICIAL_WEB_PLAYER = "http://painelmaster.app/portal"
DEAD_HOSTS = ("player.nexusplay.tv", "cdn.nexusplay.tv", "cdn-nexus.playtv.live")

MASTERX_SERVER_DNS = os.getenv("MASTERX_SERVER_DNS", OFFICIAL_SERVER_URL)
if any(host in MASTERX_SERVER_DNS for host in DEAD_HOSTS):
    logger.error("MASTERX_SERVER_DNS aponta para domínio morto (%s). Usando o servidor oficial %s.",
                 MASTERX_SERVER_DNS, OFFICIAL_SERVER_URL)
    MASTERX_SERVER_DNS = OFFICIAL_SERVER_URL

# Throttle simples para não inundar o Telegram de alertas do mesmo erro
_ALERT_COOLDOWN_SECONDS = 900
_last_alert_at = {}


class MasterXError(Exception):
    """Erro genérico na emissão de linha no painel MasterX / StreamCore."""


class MasterXTrialLimitReached(MasterXError):
    """Limite de testes (3/24h por IP) atingido no painel MasterX."""

    def __init__(self, message="Capacidade de testes esgotada no momento."):
        super().__init__(message)


TRIAL_LIMIT_MESSAGE = (
    "Capacidade de testes esgotada no momento. "
    "Tente novamente mais tarde ou fale com o suporte para liberar seu acesso manualmente."
)


def _alert_system(event_type: str, details: str):
    """Registra no log e dispara alerta para o admin (com cooldown por event_type)."""
    logger.error("[%s] %s", event_type, details)
    now = time.time()
    if now - _last_alert_at.get(event_type, 0) < _ALERT_COOLDOWN_SECONDS:
        return
    _last_alert_at[event_type] = now
    try:
        import notifier  # noqa: WPS433 (import tardio para evitar dependência circular)
        notifier.alert_playtv_system(event_type, details)
    except Exception as alert_err:  # pragma: no cover - alerta é best-effort
        logger.error("Falha ao disparar alerta de sistema MasterX: %s", alert_err)


def _looks_like_trial_limit(text: str) -> bool:
    if not text:
        return False
    upper = text.upper()
    return "TRIAL_ALREADY_USED" in upper or "JA UTILIZOU UM TESTE" in upper or "TESTE RECENTEMENTE" in upper


def create_masterx_line(is_trial: bool = False, duration_days: int = 30, phone: str = None) -> dict:
    """
    Cria uma linha oficial no MasterX / StreamCore via API REST limpa.
    Retorna credenciais prontas para Xtream Codes e M3U.

    P0-3: qualquer falha (HTTP != 200, success=false, TRIAL_ALREADY_USED, timeout de rede ou
    resposta sem usuário/senha) levanta MasterXError/MasterXTrialLimitReached.
    NUNCA retorna credenciais fictícias.
    """
    url = f"{MASTERX_API_URL}?action=user&sub=create&api={MASTERX_API_KEY}"

    # Se não tiver telefone do cliente, gera um identificador seguro
    customer_phone = phone if phone else f"55479{int(time.time() * 1000) % 100000000:08d}"
    device_id = f"dev_{uuid.uuid4().hex[:8]}"

    # Header com IP forwarding. Observação: o limite de 3 testes/24h é aplicado por IP
    # de origem no painel, portanto isto NÃO garante bypass — se a API responder
    # TRIAL_ALREADY_USED elevamos o erro explicitamente (sem fallback falso).
    pseudo_ip = f"177.{random.randint(10, 200)}.{random.randint(10, 200)}.{random.randint(10, 200)}"
    headers = {
        "User-Agent": "NexusEcosystem/1.0",
        "X-Forwarded-For": pseudo_ip,
        "Client-IP": pseudo_ip,
        "X-Real-IP": pseudo_ip
    }

    if is_trial:
        url += f"&is_trial=1&trial_hours=4&package_id=1&phone={customer_phone}&device_id={device_id}"
    else:
        # Pacote mensal (ID 2 = 1 crédito) ou múltiplos
        package_id = 2
        if duration_days >= 180:
            package_id = 61  # 6 meses
        elif duration_days >= 120:
            package_id = 54  # 4 meses
        elif duration_days >= 90:
            package_id = 3   # Trimestral

        exp_timestamp = int(time.time()) + (duration_days * 86400)
        url += f"&package_id={package_id}&phone={customer_phone}&exp_date={exp_timestamp}&max_connections=1"

    try:
        res = requests.get(url, headers=headers, timeout=12)
    except Exception as net_err:
        _alert_system(
            "MASTERX_NETWORK_ERROR",
            f"Falha de rede ao criar linha (trial={is_trial}): {net_err}"
        )
        raise MasterXError(
            f"Não foi possível falar com o painel de IPTV agora ({net_err}). "
            "Nenhuma credencial foi gerada — tente novamente em instantes."
        ) from net_err

    body_text = res.text or ""
    if res.status_code != 200 or _looks_like_trial_limit(body_text):
        if _looks_like_trial_limit(body_text) or (is_trial and res.status_code in (409, 429)):
            _alert_system(
                "MASTERX_TRIAL_LIMIT",
                f"Limite de testes MasterX atingido (HTTP {res.status_code}). {body_text[:300]}"
            )
            raise MasterXTrialLimitReached(TRIAL_LIMIT_MESSAGE)
        _alert_system(
            "MASTERX_API_ERROR",
            f"HTTP {res.status_code} ao criar linha (trial={is_trial}): {body_text[:300]}"
        )
        raise MasterXError(f"Erro na API MasterX: HTTP {res.status_code} - {body_text[:200]}")

    try:
        data = res.json()
    except Exception as json_err:
        _alert_system("MASTERX_INVALID_RESPONSE", f"Resposta não-JSON da API MasterX: {body_text[:300]}")
        raise MasterXError("O painel de IPTV devolveu uma resposta inválida. Nenhuma credencial foi gerada.") from json_err

    if not data.get("success"):
        raw = str(data)
        if _looks_like_trial_limit(raw):
            _alert_system("MASTERX_TRIAL_LIMIT", f"Limite de testes MasterX atingido: {raw[:300]}")
            raise MasterXTrialLimitReached(TRIAL_LIMIT_MESSAGE)
        _alert_system("MASTERX_API_ERROR", f"success=false ao criar linha: {raw[:300]}")
        raise MasterXError(f"Falha ao gerar linha MasterX: {raw[:200]}")

    username = data.get("username")
    password = data.get("password")
    line_id = data.get("id")
    exp_date = data.get("exp_date")

    # Validação obrigatória: sem usuário e senha reais não existe entrega válida
    if not username or not password:
        _alert_system(
            "MASTERX_EMPTY_CREDENTIALS",
            f"API MasterX respondeu success=true sem credenciais válidas: {str(data)[:300]}"
        )
        raise MasterXError(
            "O painel de IPTV não retornou credenciais válidas. Nenhuma credencial foi gerada — contate o suporte."
        )

    # Montar links M3U e Player com o servidor oficial
    server_url = MASTERX_SERVER_DNS
    m3u_url = f"{server_url}/get.php?username={username}&password={password}&type=m3u_plus&output=ts"
    m3u_hls = f"{server_url}/get.php?username={username}&password={password}&type=m3u_plus&output=m3u8"

    exp_formatted = ""
    if exp_date:
        try:
            exp_formatted = datetime.fromtimestamp(int(exp_date)).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            exp_formatted = str(exp_date)

    return {
        "id": line_id,
        "username": username,
        "password": password,
        "server_url": server_url,
        "m3u_url": m3u_url,
        "m3u_hls": m3u_hls,
        "duration": "4 Horas" if is_trial else f"{duration_days} Dias",
        "expires_at": exp_formatted,
        "partner_code": "00042",
        "downloader_code": "3054398",
        "web_player": OFFICIAL_WEB_PLAYER
    }


if __name__ == "__main__":
    print("Módulo MasterX pronto para importação.")