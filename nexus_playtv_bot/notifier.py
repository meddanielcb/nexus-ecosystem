"""
Módulo de Telemetria e Alertas do Nexus PlayTV.
Envia notificações diretamente para o Telegram pessoal do Daniel via @Alerta_nexusbot (671901048).
"""

import urllib.request
import json
import logging
import os

logger = logging.getLogger("playtv_notifier")

ALERT_BOT_TOKEN = os.getenv("ALERT_BOT_TOKEN", "")
ADMIN_CHAT_ID = "671901048"

def send_alert(message_markdown: str):
    url = f"https://api.telegram.org/bot{ALERT_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": ADMIN_CHAT_ID,
        "text": message_markdown,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        logger.error(f"Falha ao enviar alerta Telegram: {e}")
        return None

def alert_playtv_sale(plan_name: str, amount_str: str, method: str, customer_info: str, order_id: str):
    clean_customer = customer_info.replace("_", "\\_")
    clean_order_id = order_id.replace("_", "\\_")
    clean_plan = plan_name.replace("_", "\\_")
    
    msg = (
        "💰 *NOVA ASSINATURA NEXUS PLAYTV!*\n\n"
        f"📺 *Plano:* {clean_plan}\n"
        f"💵 *Valor:* {amount_str}\n"
        f"💳 *Método:* {method}\n"
        f"👤 *Cliente:* {clean_customer}\n"
        f"🆔 *Pedido:* `{clean_order_id}`\n\n"
        "✅ *Acesso P2P liberado e entregue automaticamente.*"
    )
    return send_alert(msg)

def alert_playtv_trial(username: str, user_id: int):
    clean_user = (username or f"ID {user_id}").replace("_", "\\_")
    msg = (
        "⚡ *NOVO TESTE GRÁTIS GERADO - PLAYTV*\n\n"
        f"👤 *Usuário:* @{clean_user} (ID: `{user_id}`)\n"
        "⏱️ *Duração:* 4 Horas\n"
        "📡 *Servidor:* P2P Anti-Travamento CDN\n\n"
        "🎯 *Status:* Em degustação. Funil de conversão pós-teste armado."
    )
    return send_alert(msg)

def alert_playtv_system(event_type: str, details: str):
    clean_event = event_type.replace("_", "\\_")
    clean_details = details.replace("_", "\\_")
    
    msg = (
        "⚠️ *ALERTA DE SISTEMA - NEXUS PLAYTV*\n\n"
        f"📌 *Evento:* {clean_event}\n"
        f"📝 *Detalhes:* {clean_details}\n"
        f"🕒 *Horário:* Sistema operacional autônomo."
    )
    return send_alert(msg)
