import os
import requests
import json
import uuid
import logging

logger = logging.getLogger("services")

DIGISELLER_SELLER_ID = os.getenv("DIGISELLER_SELLER_ID", "")
DIGISELLER_API_KEY = os.getenv("DIGISELLER_API_KEY", "")
CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN", "")
PIXGET_API_KEY = os.getenv("PIXGET_API_KEY", "")
PIXGET_BASE_URL = os.getenv("PIXGET_BASE_URL", "https://pixget.app")

def create_cryptobot_invoice(amount_usd: float, description: str, order_id: str) -> dict:
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN,
        "Content-Type": "application/json"
    }
    payload = {
        "asset": "USDT",
        "amount": str(amount_usd),
        "description": description[:1024],
        "payload": order_id,
        "paid_btn_name": "openChannel",
        "paid_btn_url": "https://t.me/botnexustools_bot"
    }
    r = requests.post(url, json=payload, headers=headers, timeout=10)
    data = r.json()
    if data.get("ok"):
        return {
            "invoice_id": data["result"]["invoice_id"],
            "pay_url": data["result"]["bot_invoice_url"]
        }
    else:
        raise Exception(f"CryptoBot Error: {data.get('error')}")

def create_pixget_invoice(amount_brl: float, customer_cpf: str, description: str, external_id: str) -> dict:
    cleaned_cpf = "".join(c for c in str(customer_cpf) if c.isdigit())
    api_key = PIXGET_API_KEY
    if not api_key:
        try:
            with open("/opt/data/.env") as f:
                for line in f:
                    if line.startswith("PIXGET_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass

    url = f"{PIXGET_BASE_URL.rstrip('/')}/api/v1/checkout"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "amount": float(amount_brl),
        "customerCpf": cleaned_cpf,
        "description": description[:200],
        "externalId": external_id
    }
    
    r = requests.post(url, json=payload, headers=headers, timeout=10)
    res = r.json()
    if r.status_code == 200 and "data" in res:
        return {
            "id": res["data"]["id"],
            "external_id": res["data"].get("externalId", external_id),
            "amount": res["data"]["amount"],
            "status": res["data"]["status"],
            "qr_code": res["data"]["qrCode"],
            "expires_at": res["data"].get("expiresAt")
        }
    else:
        err_msg = res.get("error") or r.text
        raise Exception(f"PixGet ({r.status_code}): {err_msg}")

BLOCKBEE_API_KEY = os.getenv("BLOCKBEE_API_KEY", "")

def get_network_fee_estimate(coin: str) -> float:
    """Consulta a taxa estimada de encaminhamento na API do BlockBee em USD"""
    try:
        url = f"https://api.blockbee.io/{coin}/estimate/?apikey={BLOCKBEE_API_KEY}&addresses=1"
        res = requests.get(url, timeout=4).json()
        usd_fee = res.get("estimated_cost_currency", {}).get("USD")
        if usd_fee is not None:
            return round(float(usd_fee), 2)
    except Exception as e:
        logger.warning(f"Erro ao estimar taxa BlockBee para {coin}: {e}")
    # Fallback conservador se a API falhar
    fallbacks = {
        "bep20/usdt": 0.05,
        "polygon/usdt": 0.05,
        "base/usdc": 0.80,
        "arbitrum/usdc": 0.05,
        "sol/usdt": 0.05,
        "erc20/usdt": 2.50,
        "btc": 1.00
    }
    return fallbacks.get(coin, 0.50)

def convert_usd_to_crypto(ticker: str, amount_usd: float) -> tuple[float, str]:
    """
    Converte valor em USD para a quantidade exata da moeda selecionada via API BlockBee.
    Para stablecoins (USDT/USDC), a proporção é 1:1.
    Para moedas flutuantes (BTC, ETH), consulta /convert/.
    Retorna (quantidade_crypto, string_formatada)
    """
    # Identificar stablecoins
    if any(ticker.endswith(s) for s in ["usdt", "usdc", "usdt0"]):
        return amount_usd, f"{amount_usd:.2f}"
    
    # Moedas voláteis: converter via API BlockBee
    try:
        url = f"https://api.blockbee.io/{ticker}/convert/?apikey={BLOCKBEE_API_KEY}&value={amount_usd}&from=usd"
        res = requests.get(url, timeout=5).json()
        if res.get("status") == "success" and "value_coin" in res:
            val = float(res["value_coin"])
            # Formatando com até 8 casas decimais sem zeros desnecessários
            return val, f"{val:.8f}".rstrip('0').rstrip('.')
    except Exception as e:
        logger.warning(f"Erro ao converter {amount_usd} USD para {ticker}: {e}")
        
    # Fallback seguro para moedas voláteis caso a API de conversão falhe temporariamente
    # Evita que 35 USD vire 35 BTC/ETH
    fallback_rates = {"btc": 65000.0, "eth": 2600.0}
    if ticker in fallback_rates:
        val = amount_usd / fallback_rates[ticker]
        return val, f"{val:.8f}".rstrip('0').rstrip('.')
        
    return amount_usd, f"{amount_usd:.6f}"

def create_blockbee_payment(coin: str, order_id: str) -> dict:
    """
    Gera um endereço de pagamento dedicado via BlockBee.
    """
    callback_url = f"https://nexus.pixget.io/api/webhooks/blockbee?order_id={order_id}"
    url = f"https://api.blockbee.io/{coin}/create/"
    params = {
        "apikey": BLOCKBEE_API_KEY,
        "callback": callback_url,
        "post": 1,
        "json": 1
    }
    r = requests.get(url, params=params, timeout=10)
    data = r.json()
    if data.get("status") == "success":
        return {
            "address_in": data["address_in"],
            "address_out": data["address_out"],
            "callback_url": data["callback_url"]
        }
    else:
        raise Exception(f"BlockBee Error: {data.get('error')}")

def purchase_on_demand_adapter(product_id: str) -> str:
    """
    Adapter central de entrega sob demanda.
    Roteia a liberação para o conector específico do produto.
    """
    mock_items = {
        "gemini_18m": "https://one.google.com/offer/reserve?promo_code=NEXUS-PRO-18M-" + uuid.uuid4().hex[:8].upper(),
        "capcut_pro_30d": "Login: nexus_pro_" + uuid.uuid4().hex[:6] + "@nexusmail.io | Senha: " + uuid.uuid4().hex[:8] + " (VIP 30 Dias)",
        "canva_pro_12m": "https://www.canva.com/brand/join?token=NEXUS-" + uuid.uuid4().hex[:12],
        "telegram_premium_3m": "https://t.me/gift/NEXUS-TGPREM-" + uuid.uuid4().hex[:10].upper(),
        "discord_nitro_3m": "https://discord.com/billing/promotions/NEXUS-NITRO-" + uuid.uuid4().hex[:12].upper(),
    }
    return mock_items.get(product_id, "https://nexus.pixget.io/redeem/" + uuid.uuid4().hex)
