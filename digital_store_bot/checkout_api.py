"""
checkout_api.py — API real de checkout (PIX / Cripto) para o Nexus PlayTV
(e compatível com os produtos legados do Nexus Tools / digital_store_bot).

Reutiliza as integracoes reais ja existentes em services.py:
  - create_pixget_invoice(...)      -> PixGet (PIX Banco Central)
  - create_blockbee_payment(...)    -> BlockBee (endereco cripto dedicado)
  - convert_usd_to_crypto(...)      -> conversao USD -> quantidade da moeda
  - get_network_fee_estimate(...)   -> taxa de rede estimada em USD

Rotas expostas (chamadas de dentro de webhook_server.py):
  POST /api/checkout/create         -> cria cobranca PIX ou cripto real
  GET  /api/checkout/status/<id>    -> consulta status do pedido no SQLite

Nao ha nenhuma chave/segredo hardcoded aqui: tudo vem de services.py / os.environ.
"""
import io
import json
import re
import sqlite3
import uuid
import base64

import qrcode
import qrcode.image.pure

from services import (
    create_pixget_invoice,
    create_blockbee_payment,
    convert_usd_to_crypto,
    get_network_fee_estimate,
)

# ---------------------------------------------------------------------------
# Catalogos de produtos.
#   - digital_store_bot (Nexus Tools): products.json  -> price_usd (raramente PIX)
#   - Nexus PlayTV (IPTV):             products_playtv.json -> price_brl / price_usd
# ---------------------------------------------------------------------------
STORE_PRODUCTS_PATH = "/opt/data/digital_store_bot/products.json"
PLAYTV_PRODUCTS_PATH = "/opt/data/nexus_playtv_bot/products_playtv.json"

with open(STORE_PRODUCTS_PATH, encoding="utf-8") as f:
    STORE_PRODUCTS = json.load(f)

with open(PLAYTV_PRODUCTS_PATH, encoding="utf-8") as f:
    PLAYTV_PRODUCTS = json.load(f)

STORE_DB_PATH = "/opt/data/digital_store_bot/data/store.db"
PLAYTV_DB_PATH = "/opt/data/nexus_playtv_bot/data/playtv.db"

ALLOWED_COINS = ("bep20/usdt", "erc20/usdt", "sol/usdt", "btc")

CPF_RE = re.compile(r"^\d{11}$")


class CheckoutError(Exception):
    """Erro de validacao/negocio -> devolvido ao cliente como 400."""
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _resolve_product(product_id: str):
    """Retorna (catalog_name, product_dict) procurando primeiro no catalogo
    do Nexus PlayTV (prioritario neste servidor) e depois no legado."""
    if product_id in PLAYTV_PRODUCTS:
        return "playtv", PLAYTV_PRODUCTS[product_id]
    if product_id in STORE_PRODUCTS:
        return "store", STORE_PRODUCTS[product_id]
    raise CheckoutError(f"product_id desconhecido: {product_id}", status=404)


def _valid_cpf(cpf: str) -> bool:
    """Validacao completa dos digitos verificadores do CPF (Modulo 11)."""
    digits = re.sub(r"\D", "", cpf or "")
    if not CPF_RE.match(digits) or digits == digits[0] * 11:
        return False

    def _dv(base):
        s = sum(int(d) * w for d, w in zip(base, range(len(base) + 1, 1, -1)))
        r = s % 11
        return "0" if r < 2 else str(11 - r)

    d1 = _dv(digits[:9])
    d2 = _dv(digits[:9] + d1)
    return digits[9:] == d1 + d2


def generate_qr_base64(data: str) -> str:
    """Gera um PNG de QR Code 100% em Python puro (qrcode + pypng, sem Pillow)
    e devolve como string base64 (sem o prefixo data:image/...)."""
    img = qrcode.make(data, image_factory=qrcode.image.pure.PyPNGImage)
    buf = io.BytesIO()
    img.save(buf)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _db_for_order(order_id: str) -> str:
    return PLAYTV_DB_PATH if order_id.startswith("PLAYTV_") else STORE_DB_PATH


def _insert_pending_order(order_id, user_id, username, product_id, payment_method, amount, payment_id):
    db_path = _db_for_order(order_id)
    conn = sqlite3.connect(db_path, timeout=10)
    try:
        conn.execute(
            """
            INSERT INTO orders (order_id, user_id, username, product_id, payment_method, amount, status, payment_id)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (order_id, user_id, username or "", product_id, payment_method, amount, payment_id),
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


# ---------------------------------------------------------------------------
# POST /api/checkout/create
# ---------------------------------------------------------------------------
def create_checkout(payload: dict) -> dict:
    """
    Aceita tanto payload do Bot (product_id, user_id) quanto do Frontend Web (plan, screens, bump_screen, bump_adult).
    """
    method = (payload.get("method") or "").strip().lower()
    if method not in ("pix", "crypto"):
        raise CheckoutError("method deve ser 'pix' ou 'crypto'")

    product_id = (payload.get("product_id") or "").strip()
    # Se veio do Frontend Web (plan, screens, bumps):
    if not product_id and "plan" in payload:
        plan = str(payload.get("plan")).lower()
        screens = int(payload.get("screens") or 1)
        if payload.get("bump_screen"):
            screens += 1
        screens = max(1, min(3, screens))
        
        if plan == "pass":
            product_id = "pack_3_games"
        elif plan == "mensal":
            product_id = f"iptv_mensal_{screens}"
        elif plan == "trimestral":
            product_id = f"iptv_trimestral_{screens}"
        elif plan == "semestral":
            product_id = f"iptv_semestral_{screens}"
        elif plan == "anual":
            product_id = f"iptv_anual_{screens}"
        else:
            product_id = f"iptv_mensal_{screens}"

    if not product_id:
        raise CheckoutError("product_id ou plan e obrigatorio")

    user_id = payload.get("user_id") or 999999999
    username = payload.get("username") or "web_client"

    # Mapeamento de coin web -> api BlockBee
    coin = (payload.get("coin") or "").lower().strip()
    if coin in ("usdt-bep20", "bep20", "bep20/usdt"):
        payload["coin"] = "bep20/usdt"
    elif coin in ("usdt-trc20", "trc20", "erc20", "erc20/usdt"):
        payload["coin"] = "erc20/usdt"
    elif coin in ("sol", "solana", "sol/usdt"):
        payload["coin"] = "sol/usdt"
    elif coin in ("btc", "bitcoin"):
        payload["coin"] = "btc"
    elif method == "crypto" and not coin:
        payload["coin"] = "bep20/usdt"

    catalog, product = _resolve_product(product_id)
    is_playtv = catalog == "playtv"
    order_prefix = "PLAYTV_" if is_playtv else "STORE_"
    order_id = f"{order_prefix}{uuid.uuid4().hex[:8].upper()}"

    if method == "pix":
        cpf = payload.get("cpf") or ""
        if not _valid_cpf(cpf):
            raise CheckoutError("cpf invalido (informe 11 digitos com DV valido)")

        price_brl = product.get("price_brl")
        if not price_brl or price_brl <= 0:
            raise CheckoutError("Este produto nao possui preco em BRL / PIX", status=422)

        description = f"Nexus PlayTV - {product.get('name', product_id)}"
        try:
            invoice = create_pixget_invoice(
                amount_brl=price_brl,
                customer_cpf=cpf,
                description=description,
                external_id=order_id,
            )
        except Exception as e:
            raise CheckoutError(f"Falha ao gerar cobranca PIX (PixGet): {e}", status=502)

        _insert_pending_order(
            order_id=order_id,
            user_id=user_id,
            username=username,
            product_id=product_id,
            payment_method="pix",
            amount=price_brl,
            payment_id=invoice.get("id"),
        )

        qr_image_b64 = generate_qr_base64(invoice.get("qr_code", ""))

        copia_e_cola = invoice.get("qr_code") or ""
        expires_at = invoice.get("expires_at")
        return {
            "ok": True,
            "order_id": order_id,
            "product_id": product_id,
            "product_name": product.get("name", product_id),
            "method": "pix",
            "amount_brl": price_brl,
            "pixget_id": invoice.get("id"),
            "status": invoice.get("status", "pending"),
            "expires_at": expires_at,
            "copia_e_cola": copia_e_cola,
            "qr_image_base64": qr_image_b64,
            "qr_image_mime": "image/png",
            "pix": {
                "copy_paste": copia_e_cola,
                "qr_image": f"data:image/png;base64,{qr_image_b64}",
                "expires_at": expires_at
            }
        }

    # method == "crypto"
    coin = (payload.get("coin") or "").strip().lower()
    if coin not in ALLOWED_COINS:
        raise CheckoutError(f"coin invalida. Use uma de: {', '.join(ALLOWED_COINS)}")

    base_usd = product.get("price_usd")
    if not base_usd or base_usd <= 0:
        raise CheckoutError("Este produto nao possui preco em USD / cripto", status=422)

    fee_usd = get_network_fee_estimate(coin)
    total_usd = base_usd if fee_usd <= 0.60 else round(base_usd + fee_usd, 2)
    crypto_qty, crypto_qty_display = convert_usd_to_crypto(coin, total_usd)

    try:
        bb = create_blockbee_payment(coin, order_id)
    except Exception as e:
        raise CheckoutError(f"Falha ao gerar endereco cripto (BlockBee): {e}", status=502)

    address_in = bb.get("address_in")

    _insert_pending_order(
        order_id=order_id,
        user_id=user_id,
        username=username,
        product_id=product_id,
        payment_method=f"crypto_{coin}",
        amount=total_usd,
        payment_id=address_in,
    )

    qr_image_b64 = generate_qr_base64(address_in or "")

    return {
        "ok": True,
        "order_id": order_id,
        "product_id": product_id,
        "product_name": product.get("name", product_id),
        "method": "crypto",
        "coin": coin,
        "amount_usd": total_usd,
        "network_fee_usd": fee_usd,
        "crypto_amount": crypto_qty_display,
        "address_in": address_in,
        "callback_url": bb.get("callback_url"),
        "status": "pending",
        "qr_image_base64": qr_image_b64,
        "qr_image_mime": "image/png",
        "crypto": {
            "coin": coin,
            "address": address_in,
            "amount": crypto_qty_display,
            "qr_image": f"data:image/png;base64,{qr_image_b64}"
        }
    }


# ---------------------------------------------------------------------------
# GET /api/checkout/status/<order_id>
# ---------------------------------------------------------------------------
def get_checkout_status(order_id: str) -> dict:
    order_id = (order_id or "").strip()
    if not order_id:
        raise CheckoutError("order_id ausente", status=400)

    db_path = _db_for_order(order_id)
    conn = sqlite3.connect(db_path, timeout=10)
    try:
        cur = conn.execute(
            "SELECT order_id, product_id, payment_method, amount, status, payment_id, created_at, updated_at "
            "FROM orders WHERE order_id = ?",
            (order_id,),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        raise CheckoutError("pedido nao encontrado", status=404)

    (o_id, product_id, payment_method, amount, status, payment_id, created_at, updated_at) = row
    return {
        "order_id": o_id,
        "product_id": product_id,
        "method": payment_method,
        "amount": amount,
        "status": status,
        "paid": status == "paid",
        "payment_id": payment_id,
        "created_at": created_at,
        "updated_at": updated_at,
    }
