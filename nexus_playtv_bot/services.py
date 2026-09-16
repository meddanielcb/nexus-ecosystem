import os
import requests
import json
import uuid
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("playtv_services")

# Gateways herdados da infraestrutura existente
CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN", "337775:AAqPZ5T1Tf43R4Q1k3Vj5n6m7l8k9j0h")
PIXGET_API_KEY = os.getenv("PIXGET_API_KEY", "")
PIXGET_BASE_URL = os.getenv("PIXGET_BASE_URL", "https://pixget.app")
BLOCKBEE_API_KEY = os.getenv("BLOCKBEE_API_KEY", "U8ukQhhdEhxT9nfuCCOJCSVVTVHJvzTL4F5Ykl8QwUB5ONEJ5XBAiMqfz5XbwiXW")

def get_pixget_headers():
    api_key = PIXGET_API_KEY
    if not api_key:
        env_file = "/opt/data/.env"
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    if line.startswith("PIXGET_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

def create_pixget_charge(amount_brl: float, order_id: str, description: str, cpf: str = "00000000000") -> dict:
    url = f"{PIXGET_BASE_URL.rstrip('/')}/api/v1/checkout"
    cleaned_cpf = "".join(c for c in str(cpf) if c.isdigit())
    payload = {
        "amount": round(float(amount_brl), 2),
        "externalId": order_id,
        "customerCpf": cleaned_cpf,
        "description": description[:200]
    }
    res = requests.post(url, json=payload, headers=get_pixget_headers(), timeout=10)
    data = res.json()
    if res.status_code == 200 and "data" in data:
        cdata = data["data"]
        return {
            "qr_code": cdata.get("qrCode"),
            "qr_code_url": cdata.get("qrCodeUrl"),
            "payment_id": cdata.get("id")
        }
    else:
        err_msg = data.get("error") or data.get("message") or res.text
        raise Exception(f"Pixget Error: {err_msg}")

def create_cryptobot_invoice(amount_usd: float, order_id: str, description: str) -> dict:
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
    payload = {
        "asset": "USDT",
        "amount": str(amount_usd),
        "description": description[:1024],
        "payload": json.dumps({"order_id": order_id}),
        "expires_in": 3600
    }
    res = requests.post(url, json=payload, headers=headers, timeout=10)
    data = res.json()
    if data.get("ok"):
        return {
            "pay_url": data["result"]["pay_url"],
            "invoice_id": data["result"]["invoice_id"]
        }
    else:
        raise Exception(f"CryptoBot Error: {data.get('error')}")

def convert_usd_to_crypto(ticker: str, amount_usd: float) -> tuple[float, str]:
    if any(ticker.endswith(s) for s in ["usdt", "usdc", "usdt0"]):
        return amount_usd, f"{amount_usd:.2f}"
    try:
        url = f"https://api.blockbee.io/{ticker}/convert/?apikey={BLOCKBEE_API_KEY}&value={amount_usd}&from=usd"
        res = requests.get(url, timeout=5).json()
        if res.get("status") == "success" and "value_coin" in res:
            val = float(res["value_coin"])
            return val, f"{val:.8f}".rstrip('0').rstrip('.')
    except Exception as e:
        logger.warning(f"Erro ao converter {amount_usd} USD para {ticker}: {e}")
        
    fallback_rates = {"btc": 65000.0, "eth": 2600.0}
    if ticker in fallback_rates:
        val = amount_usd / fallback_rates[ticker]
        return val, f"{val:.8f}".rstrip('0').rstrip('.')
    return amount_usd, f"{amount_usd:.6f}"

def get_network_fee_estimate(coin: str) -> float:
    fees = {
        "bep20/usdt": 0.02,
        "polygon/usdt": 0.01,
        "sol/usdt": 0.00,
        "arbitrum/usdc": 0.01,
        "base/usdc": 0.78,
        "btc": 0.16,
        "eth": 0.23,
        "erc20/usdt": 0.83
    }
    return fees.get(coin, 0.50)

def create_blockbee_payment(coin: str, order_id: str) -> dict:
    callback_url = f"https://nexus.pixget.io/api/webhooks/blockbee?order_id={order_id}"
    url = f"https://api.blockbee.io/{coin}/create/"
    params = {
        "apikey": BLOCKBEE_API_KEY,
        "callback": callback_url,
        "pending": 1
    }
    res = requests.get(url, params=params, timeout=10).json()
    if res.get("status") == "success":
        return {
            "address_in": res.get("address_in"),
            "qr_code": res.get("qr_code")
        }
    else:
        raise Exception(f"BlockBee Error: {res.get('error')}")

def generate_iptv_access(duration_days: int = 30, is_trial: bool = False, username: str = None, password: str = None, phone: str = None) -> dict:
    """
    Gera as credenciais oficiais de acesso IPTV MasterX / StreamCore via API REST nativa.
    Servidor oficial: http://atmt.space

    IMPORTANTE: não existe fallback local. Se a API MasterX falhar, o erro é
    logado em detalhe e a exceção é repassada ao chamador (MasterXError ou a
    exceção original), que deve tratar a falha de forma explícita (ex.: avisar
    o cliente e não cobrar/entregar). Nunca fabricar credenciais fictícias
    aqui — elas nunca funcionariam no painel real e enganariam o cliente.
    """
    from masterx_api import create_masterx_line, MasterXError
    try:
        return create_masterx_line(is_trial=is_trial, duration_days=duration_days, phone=phone)
    except MasterXError:
        logger.error(
            f"Erro ao emitir linha via MasterX API (is_trial={is_trial}, duration_days={duration_days}, phone={phone})",
            exc_info=True,
        )
        raise
    except Exception as e:
        logger.error(
            f"Erro inesperado ao emitir linha via MasterX API (is_trial={is_trial}, duration_days={duration_days}, phone={phone}): {e}",
            exc_info=True,
        )
        raise MasterXError(f"Falha inesperada ao gerar acesso IPTV via MasterX: {e}") from e
