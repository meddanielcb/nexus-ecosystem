"""
Módulo de Telemetria e Alertas do Nexus Tools.
Envia notificações diretamente para o Telegram pessoal do Daniel via @Alerta_nexusbot.
"""

import urllib.request
import json
import logging
import os

logger = logging.getLogger("notifier")

ALERT_BOT_TOKEN = os.getenv("ALERT_BOT_TOKEN", "")
DANIEL_CHAT_ID = "671901048"

def notify_daniel(message: str) -> bool:
    """Envia mensagem formatada em Markdown para o Telegram privado do Daniel."""
    url = f"https://api.telegram.org/bot{ALERT_BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": DANIEL_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }).encode("utf-8")
    
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception as e:
        logger.error(f"Erro ao enviar alerta para Daniel: {e}")
        return False

def alert_sale(product_name: str, amount_str: str, method: str, customer_info: str, order_id: str):
    """Notifica nova venda confirmada."""
    # Escapar underscores em texto normal; dentro de inline code (crase) não precisa de escape
    safe_customer = customer_info.replace("_", "\\_")
    safe_prod = product_name.replace("_", "\\_").replace("$", "\\$")
    safe_amount = amount_str.replace("$", "\\$")
    safe_method = method.replace("_", "\\_")
    
    msg = (
        f"💰 *NOVA VENDA CONFIRMADA!*\n\n"
        f"📦 *Produto:* {safe_prod}\n"
        f"💵 *Valor:* {safe_amount}\n"
        f"💳 *Método:* {safe_method}\n"
        f"👤 *Cliente:* {safe_customer}\n"
        f"🆔 *Pedido:* `{order_id}`\n\n"
        f"✅ _Entrega sob demanda processada com sucesso._"
    )
    return notify_daniel(msg)

def alert_system(event_type: str, details: str):
    """Notifica incidentes, reinícios de serviços ou alertas de VPS."""
    safe_type = event_type.replace("_", "\\_")
    safe_details = details.replace("_", "\\_")
    
    msg = (
        f"⚠️ *ALERTA DE INFRAESTRUTURA / VPS*\n\n"
        f"📌 *Evento:* {safe_type}\n"
        f"📝 *Detalhes:* {safe_details}\n"
        f"🕒 *Status:* Ação de auto-recuperação acionada."
    )
    return notify_daniel(msg)
