import os
import requests
import json
import uuid
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("playtv_services")

# Gateways herdados da infraestrutura existente
CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN", "")
PIXGET_API_KEY = os.getenv("PIXGET_API_KEY", "")
PIXGET_BASE_URL = os.getenv("PIXGET_BASE_URL", "https://pixget.app")
BLOCKBEE_API_KEY = os.getenv("BLOCKBEE_API_KEY", "")

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
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }

def create_pixget_charge(amount_brl: float, order_id: str, description: str, cpf: str = "00000000000") -> dict:
    url = f"{PIXGET_BASE_URL.rstrip('/')}/api/v1/checkout"
    payload = {
        "amount": round(amount_brl, 2),
        "external_id": order_id,
        "payer_document": cpf.replace(".", "").replace("-", "").strip() or "00000000000",
        "description": description[:100]
    }
    res = requests.post(url, json=payload, headers=get_pixget_headers(), timeout=10)
    data = res.json()
    if res.status_code in (200, 201) and data.get("success"):
        cdata = data.get("data", {})
        return {
            "qr_code": cdata.get("qr_code"),
            "qr_code_url": cdata.get("qr_code_url"),
            "payment_id": cdata.get("id")
        }
    else:
        raise Exception(f"Pixget Error: {data.get('message', res.text)}")

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

def generate_iptv_access(duration_days: int = 30, is_trial: bool = False, username: str = None, password: str = None) -> dict:
    """
    Gera as credenciais oficiais de acesso IPTV P2Braz (Xtream Codes / M3U).
    Servidor oficial: http://man77.work
    """
    if username and password:
        iptv_user = username
        iptv_pass = password
    else:
        suffix = uuid.uuid4().hex[:6].lower()
        prefix = "trial" if is_trial else "nexus"
        iptv_user = f"{prefix}_{suffix}"
        iptv_pass = uuid.uuid4().hex[:8]

    server_dns = "http://man77.work"
    m3u_link = f"http://man77.work/get.php?username={iptv_user}&password={iptv_pass}&type=m3u_plus&output=ts"
    
    return {
        "username": iptv_user,
        "password": iptv_pass,
        "server_url": server_dns,
        "m3u_url": m3u_link,
        "duration": f"{duration_days} Dias" if not is_trial else "4 Horas",
        "expires_at": (datetime.now() + (timedelta(hours=4) if is_trial else timedelta(days=duration_days))).strftime("%d/%m/%Y às %H:%M")
    }
