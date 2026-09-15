import json
import sqlite3
import requests
import hmac
import hashlib
import os
import threading
import base64
from urllib.parse import urlparse, parse_qs
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from http.server import HTTPServer, BaseHTTPRequestHandler
from db import DB_PATH
from services import purchase_on_demand_adapter
from notifier import alert_sale, alert_system

# Carregar Chave Pública do BlockBee para validação RSA
BLOCKBEE_PUBKEY = None
try:
    with open("/opt/data/digital_store_bot/blockbee_pubkey.pem") as f:
        pub_json = json.load(f)
        BLOCKBEE_PUBKEY = load_pem_public_key(pub_json["pubkey"].encode("utf-8"))
except Exception as e:
    print("Aviso: Chave BlockBee não carregada:", e)

with open("/opt/data/digital_store_bot/products.json") as f:
    PRODUCTS = json.load(f)

PROCESSED_DELIVERIES = set()
DELIVERY_LOCK = threading.Lock()

PLAYTV_DB_PATH = "/opt/data/nexus_playtv_bot/data/playtv.db"
PLAYTV_BOT_TOKEN = "8979028734:AAFvHUW2ML8XmUnRXtY8f5j6l-pOeKxwj5s"

# ---------------------------------------------------------------------------
# P0-4 - Dominios oficiais de entrega.
# Os dominios legados player.nexusplay.tv / cdn.nexusplay.tv / cdn-nexus.playtv.live
# sao NXDOMAIN (verificado 2026-09-15) e nao podem ser entregues ao cliente.
#   Servidor oficial:  http://atmt.space
#   WebPlayer oficial: http://painelmaster.app/portal
# ---------------------------------------------------------------------------
OFFICIAL_SERVER_URL = "http://atmt.space"
OFFICIAL_WEB_PLAYER = "http://painelmaster.app/portal"
DEAD_HOSTS = ("player.nexusplay.tv", "cdn.nexusplay.tv", "cdn-nexus.playtv.live")


def sanitize_server_url(url: str) -> str:
    """Substitui dominios mortos (NXDOMAIN) pelo servidor oficial."""
    if not url or any(host in url for host in DEAD_HOSTS):
        return OFFICIAL_SERVER_URL
    return url.rstrip("/")


def sanitize_m3u_url(m3u_url, server_url, username, password) -> str:
    """Garante que a lista M3U aponte para um host que resolve."""
    if not m3u_url or any(host in m3u_url for host in DEAD_HOSTS):
        return f"{server_url}/get.php?username={username}&password={password}&type=m3u_plus&output=ts"
    return m3u_url


# ---------------------------------------------------------------------------
# P2 - Idempotencia persistente de deliveries (sobrevive a restart do processo).
# ---------------------------------------------------------------------------
def _ensure_delivery_schema():
    for path in (DB_PATH, PLAYTV_DB_PATH):
        try:
            conn = sqlite3.connect(path, timeout=10)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS processed_deliveries ("
                "delivery_id TEXT PRIMARY KEY, source TEXT, "
                "processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Aviso: nao foi possivel preparar idempotencia em {path}: {e}")


def claim_delivery(delivery_id: str, source: str = "pixget") -> bool:
    """Persiste o delivery em SQLite.

    Retorna True apenas se o delivery for inedito (deve ser processado).
    Retorna False em replay (mesmo X-Pixget-Delivery apos restart, por exemplo).
    """
    if not delivery_id:
        return True
    for path in (DB_PATH, PLAYTV_DB_PATH):
        try:
            conn = sqlite3.connect(path, timeout=10)
            cur = conn.execute(
                "INSERT OR IGNORE INTO processed_deliveries (delivery_id, source) VALUES (?, ?)",
                (delivery_id, source)
            )
            conn.commit()
            inserted = cur.rowcount
            conn.close()
            return inserted == 1
        except Exception as e:
            print(f"Aviso: idempotencia indisponivel em {path}: {e}")
    # Sem persistencia disponivel nao bloqueamos a entrega (fail-open, igual ao comportamento antigo)
    return True


_ensure_delivery_schema()


def deliver_order_async(order_id: str):
    """Executa a entrega do produto e salva no banco de dados de forma idempotente"""
    # 1. Roteamento Inteligente: Verificar se é pedido do Nexus PlayTV ou do Nexus Tools
    if order_id.startswith("PLAYTV_"):
        deliver_playtv_order_async(order_id)
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, product_id, status, payment_method, amount FROM orders WHERE order_id = ?", (order_id,))
    row = c.fetchone()
    
    if not row or row[2] == "paid":
        conn.close()
        return
        
    user_id, product_id, status, method, amount = row[0], row[1], row[2], row[3] or "pix", row[4] or 0.0
    
    try:
        delivered_item = purchase_on_demand_adapter(product_id)
    except Exception as e:
        delivered_item = f"Erro na liberação automática ({e}). Contate o suporte com ID {order_id}"
        
    c.execute("UPDATE orders SET status = 'paid', delivered_item = ?, updated_at = CURRENT_TIMESTAMP WHERE order_id = ?", (delivered_item, order_id))
    conn.commit()
    conn.close()
    
    bot_token = os.getenv("STORE_BOT_TOKEN") or "8861845885:AAFlofn8dVAcpzn9ewj6Wjss6TcacZ5d1ko"
    if bot_token and user_id:
        p = PRODUCTS.get(product_id, {})
        instructions = p.get("instructions", "Seu acesso: {item}").format(item=delivered_item)
        msg = (
            f"🎉 *Pagamento Confirmado com Sucesso!*\n\n"
            f"{instructions}\n\n"
            f"🛡️ *Garantia Ativa:* Seu pedido foi registrado sob ID `{order_id}`.\n"
            f"Precisa de mais alguma ferramenta ou suporte? Use os botões abaixo:"
        )
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        keyboard = {
            "inline_keyboard": [
                [{"text": "⚡ Opções & Ferramentas", "callback_data": "menu_principal"}],
                [{"text": "❓ Dúvidas & Suporte", "callback_data": "faq"}]
            ]
        }
        try:
            requests.post(url, json={
                "chat_id": user_id,
                "text": msg,
                "parse_mode": "Markdown",
                "reply_markup": keyboard
            }, timeout=10)
        except Exception as err:
            print("Erro ao enviar mensagem Telegram:", err)

    # Disparar notificação privada para o Telegram do Daniel (@Alerta_nexusbot)
    try:
        prod_title = PRODUCTS.get(product_id, {}).get("name", product_id)
        val_str = f"R$ {amount:.2f}" if method == "pix" else f"${amount:.2f} USDT"
        alert_sale(
            product_name=prod_title,
            amount_str=val_str,
            method=method.upper(),
            customer_info=f"Telegram ID {user_id}",
            order_id=order_id
        )
    except Exception as e:
        print("Erro ao disparar alert_sale:", e)

def deliver_playtv_order_async(order_id: str):
    """Executa a entrega e ativação da assinatura Nexus PlayTV"""
    import sys
    # Importar diretamente do módulo do playtv sem colidir com digital_store_bot/services.py
    import importlib.util
    spec = importlib.util.spec_from_file_location("playtv_services", "/opt/data/nexus_playtv_bot/services.py")
    playtv_services = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(playtv_services)
    generate_iptv_access = playtv_services.generate_iptv_access

    spec_notif = importlib.util.spec_from_file_location("playtv_notifier", "/opt/data/nexus_playtv_bot/notifier.py")
    playtv_notifier = importlib.util.module_from_spec(spec_notif)
    spec_notif.loader.exec_module(playtv_notifier)
    alert_playtv_sale = playtv_notifier.alert_playtv_sale

    conn = sqlite3.connect(PLAYTV_DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, product_id, status, payment_method, amount FROM orders WHERE order_id = ?", (order_id,))
    row = c.fetchone()
    if not row or row[2] == "paid":
        conn.close()
        return

    user_id, product_id, status, method, amount = row[0], row[1], row[2], row[3] or "pix", row[4] or 0.0

    # Determinar duração
    if product_id == "pack_3_games":
        import datetime
        expires_pass = (datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("""
        INSERT INTO game_passes (user_id, order_id, total_passes, remaining_passes, expires_at)
        VALUES (?, ?, 3, 3, ?)
        """, (user_id, order_id, expires_pass))
        c.execute("""
        UPDATE orders 
        SET status = 'paid', 
            delivered_credentials = 'Pack 3 Jogos (Saldo: 3)', 
            expires_at = ?,
            updated_at = CURRENT_TIMESTAMP 
        WHERE order_id = ?
        """, (expires_pass, order_id))
        conn.commit()
        conn.close()

        # Enviar mensagem personalizada de crédito de passes
        msg = (
            "🎉 *PAGAMENTO APROVADO! SEU PACK 3 JOGOS ESTÁ DISPONÍVEL!*\n\n"
            "⚽ *Saldo liberado:* 3 Acessos de 4 Horas cada\n"
            f"⏳ *Validade do saldo:* 30 dias (Até {expires_pass})\n\n"
            "✨ *Como usar:*\n"
            "Sempre que quiser assistir a um jogo ou luta, basta clicar no botão abaixo para ativar 1 acesso de 4 horas imediatamente!"
        )
        url_msg = f"https://api.telegram.org/bot{PLAYTV_BOT_TOKEN}/sendMessage"
        keyboard = {
            "inline_keyboard": [
                [{"text": "⚽ ATIVAR 1º JOGO AGORA (4 HORAS)", "callback_data": "redeem_game_pass"}],
                [{"text": "📱 Passo a Passo Smart TV", "callback_data": "how_to_install"}]
            ]
        }
        try:
            requests.post(url_msg, json={
                "chat_id": user_id,
                "text": msg,
                "parse_mode": "Markdown",
                "reply_markup": keyboard
            }, timeout=10)
        except Exception as err:
            print("Erro ao enviar confirmação de pass PlayTV:", err)

        # Disparar alerta no @Alerta_nexusbot do Daniel para Passes
        try:
            val_str = f"R$ {amount:.2f}" if method == "pix" else f"${amount:.2f} USDT"
            alert_playtv_sale(
                plan_name="Pack 3 Jogos (Futebol/UFC)",
                amount_str=val_str,
                method=method.upper(),
                customer_info=f"Telegram ID {user_id}",
                order_id=order_id
            )
        except Exception as alert_err:
            print("Erro ao disparar alert_playtv_sale para pack_3_games:", alert_err)
        return

    days_map = {
        "iptv_mensal_1": 30,
        "iptv_mensal_2": 30,
        "iptv_mensal_3": 30,
        "iptv_trimestral_1": 90,
        "iptv_trimestral_2": 90,
        "iptv_trimestral_3": 90,
        "iptv_semestral_1": 180,
        "iptv_semestral_2": 180,
        "iptv_semestral_3": 180,
        "iptv_anual_1": 365,
        "iptv_anual_2": 365,
        "iptv_anual_3": 365,
        # Legados para compatibilidade
        "monthly_1screen": 30,
        "monthly_2screens": 30,
        "quarterly_1screen": 90,
        "quarterly_2screens": 90,
        "semiannual_1screen": 180,
        "semiannual_2screens": 180,
        "annual_family_2screens": 365
    }
    conns_map = {
        "iptv_mensal_1": 1, "iptv_mensal_2": 2, "iptv_mensal_3": 3,
        "iptv_trimestral_1": 1, "iptv_trimestral_2": 2, "iptv_trimestral_3": 3,
        "iptv_semestral_1": 1, "iptv_semestral_2": 2, "iptv_semestral_3": 3,
        "iptv_anual_1": 1, "iptv_anual_2": 2, "iptv_anual_3": 3,
        "monthly_1screen": 1, "monthly_2screens": 2,
        "quarterly_1screen": 1, "quarterly_2screens": 2,
        "semiannual_1screen": 1, "semiannual_2screens": 2,
        "annual_family_2screens": 2
    }
    days = days_map.get(product_id, 30)
    conns = conns_map.get(product_id, 1)
    access = generate_iptv_access(duration_days=days)
    cred_str = f"Usuário: {access['username']} | Senha: {access['password']} | Servidor: {access['server_url']}"

    c.execute("""
    UPDATE orders 
    SET status = 'paid', 
        delivered_credentials = ?, 
        m3u_url = ?, 
        expires_at = ?,
        updated_at = CURRENT_TIMESTAMP 
    WHERE order_id = ?
    """, (cred_str, access['m3u_url'], access['expires_at'], order_id))
    conn.commit()
    conn.close()

    # Enviar credenciais diretamente no chat do cliente no Nexus PlayTV com botões de 1 clique
    vip_web_url = f"https://nexus.pixget.io/vip/{order_id}"
    web_player_url = f"{OFFICIAL_WEB_PLAYER}/?user={access['username']}&pass={access['password']}"

    msg = (
        "🎉 *PAGAMENTO APROVADO! SEU ACESSO NEXUS PLAYTV ESTÁ ATIVO!*\n\n"
        f"📺 *Plano:* {product_id}\n"
        f"⏳ *Validade:* {access['duration']} (Até: {access['expires_at']})\n\n"
        "📱 *Toque no botão abaixo para abrir seu Cartão VIP Interativo:*\n"
        "Nele você assiste em 1 clique sem senha e copia tudo direto com 1 toque!"
    )
    
    url_msg = f"https://api.telegram.org/bot{PLAYTV_BOT_TOKEN}/sendMessage"
    keyboard = {
        "inline_keyboard": [
            [{"text": "✨ ABRIR CARTÃO VIP INTERATIVO", "url": vip_web_url}],
            [{"text": "▶️ Assistir Agora no Navegador (Sem Senha)", "url": web_player_url}],
            [
                {"text": "📱 Passo a Passo Smart TV", "callback_data": "how_to_install"},
                {"text": "💬 Suporte VIP 24h", "callback_data": "support_faq"}
            ]
        ]
    }
    try:
        requests.post(url_msg, json={
            "chat_id": user_id,
            "text": msg,
            "parse_mode": "Markdown",
            "reply_markup": keyboard
        }, timeout=10)
    except Exception as err:
        print("Erro ao enviar credenciais PlayTV ao cliente:", err)

    # Gerar e Enviar o VIP Onboarding Card em Alta Resolução (com QR Code auto-login)
    try:
        import sys
        sys.path.append("/opt/data/nexus_playtv_bot")
        from make_vip_card import create_vip_onboarding_card
        user_card = f"/tmp/Nexus_VIP_Card_{order_id}.png"
        create_vip_onboarding_card(
            output_path=user_card,
            username=access['username'],
            password=access['password'],
            server_url=access['server_url'],
            m3u_url=access['m3u_url'],
            plan_name=product_id,
            valid_until=f"{access['expires_at']}"
        )

        url_photo = f"https://api.telegram.org/bot{PLAYTV_BOT_TOKEN}/sendPhoto"
        with open(user_card, "rb") as f_card:
            files = {"photo": ("VIP_Pass_Nexus_PlayTV.png", f_card, "image/png")}
            data = {
                "chat_id": user_id,
                "caption": "📲 *Seu Cartão VIP de Acesso Imediato:*\n\n1️⃣ Aponte a câmera para o QR Code para abrir o WebPlayer sem digitar nada.\n2️⃣ No controle da TV Box ou Firestick, use o código de 5 dígitos do Downloader.",
                "parse_mode": "Markdown"
            }
            requests.post(url_photo, data=data, files=files, timeout=20)
        
        if os.path.exists(user_card):
            os.remove(user_card)
    except Exception as card_err:
        print("Erro ao gerar/enviar Card VIP Onboarding:", card_err)

    # Disparar alerta no @Alerta_nexusbot do Daniel
    try:
        val_str = f"R$ {amount:.2f}" if method == "pix" else f"${amount:.2f} USDT"
        alert_playtv_sale(
            plan_name=product_id,
            amount_str=val_str,
            method=method.upper(),
            customer_info=f"Telegram ID {user_id}",
            order_id=order_id
        )
    except Exception as e:
        print("Erro ao alertar venda PlayTV:", e)

class WebhookHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        # Servir página VIP interativa móvel: /vip/<order_id>
        if path.startswith("/vip/"):
            order_id = path.replace("/vip/", "").strip()
            conn = sqlite3.connect("/opt/data/nexus_playtv_bot/data/playtv.db")
            c = conn.cursor()
            c.execute("SELECT delivered_credentials, product_id, created_at, expires_at FROM orders WHERE order_id = ? AND status = 'paid'", (order_id,))
            row = c.fetchone()
            conn.close()

            if not row or not row[0]:
                self.send_response(404)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(b"404 - Acesso ou Pedido VIP nao encontrado.")
                return

            dns, user, pw, m3u = "http://atmt.space", "", "", ""
            plan_name = row[1] or "Nexus PlayTV"
            valid_until = row[3] or "Ativo"

            cred_str = row[0]
            for part in cred_str.split("|"):
                if "Servidor:" in part: dns = part.split("Servidor:")[1].strip()
                elif "Usuário:" in part: user = part.split("Usuário:")[1].strip()
                elif "Senha:" in part: pw = part.split("Senha:")[1].strip()

            import sys
            sys.path.append("/opt/data/nexus_playtv_bot")
            from make_vip_html import generate_interactive_html
            tmp_html = f"/tmp/vip_{order_id}.html"
            generate_interactive_html(tmp_html, user, pw, dns, f"{dns}/get.php?username={user}&password={pw}&type=m3u_plus", plan_name, valid_until)
            
            with open(tmp_html, "rb") as f:
                content = f.read()

            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        elif path == "/static/nexus_playtv_banner.png":
            b_path = "/opt/data/nexus_playtv_bot/assets/nexus_playtv_banner.png"
            if os.path.exists(b_path):
                with open(b_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

        self.send_response(404)
        self.end_headers()
        self.wfile.write(b'Not Found')
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        raw_body = self.rfile.read(length)
        parsed_path = urlparse(self.path).path
        
        if parsed_path == "/api/webhooks/pixget":
            delivery_id = self.headers.get("X-Pixget-Delivery")
            
            # Idempotência por X-Pixget-Delivery
            if delivery_id:
                with DELIVERY_LOCK:
                    if delivery_id in PROCESSED_DELIVERIES:
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(b'{"received": true, "status": "already_processed"}')
                        return
                    PROCESSED_DELIVERIES.add(delivery_id)

            # Validação oficial HMAC-SHA256 com suporte a 'sha256=...'
            secret = os.getenv("PIXGET_WEBHOOK_SECRET", "3b28f474f5092bd536f342490078f8f69f3a026a5bc9d0c6448f04049bb8635c")
            received_sig = self.headers.get("X-Pixget-Signature", "")
            
            computed_hash = hmac.new(secret.encode('utf-8'), raw_body, hashlib.sha256).hexdigest()
            expected_sig = f"sha256={computed_hash}"
            
            # Se vier sem o prefixo sha256=, aceita também
            valid = hmac.compare_digest(expected_sig, received_sig) or hmac.compare_digest(computed_hash, received_sig)
            
            if not valid:
                self.send_response(401)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"error": "Invalid HMAC signature"}')
                return

            # Resposta imediata HTTP 200 OK (< 30ms)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"received": true}')
            
            try:
                data = json.loads(raw_body.decode('utf-8'))
            except Exception:
                data = {}

            event = data.get("event") or self.headers.get("X-Pixget-Event")
            
            if event == "payment.completed":
                order_id = (
                    data.get("externalId") or 
                    data.get("data", {}).get("externalId") or
                    data.get("order_id")
                )
                pix_id = data.get("id") or data.get("data", {}).get("id")
                
                if not order_id and pix_id:
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    c.execute("SELECT order_id FROM orders WHERE payment_id = ?", (pix_id,))
                    r = c.fetchone()
                    conn.close()
                    if r:
                        order_id = r[0]
                        
                if order_id:
                    threading.Thread(target=deliver_order_async, args=(order_id,), daemon=True).start()
                    
            elif event in ("payment.expired", "payment.refunded"):
                order_id = data.get("externalId") or data.get("data", {}).get("externalId")
                if order_id:
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    new_status = "expired" if event == "payment.expired" else "refunded"
                    c.execute("UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE order_id = ?", (new_status, order_id))
                    conn.commit()
                    conn.close()
            return



        if parsed_path == "/api/webhooks/blockbee":
            # 1. Validação Obrigatória de Assinatura RSA do BlockBee
            sig_b64 = self.headers.get("x-ca-signature")
            if not sig_b64 or not BLOCKBEE_PUBKEY:
                print("BlockBee Rejeitado: header x-ca-signature ausente ou chave pública não carregada")
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b"unauthorized")
                return

            try:
                sig_bytes = base64.b64decode(sig_b64)
                BLOCKBEE_PUBKEY.verify(
                    sig_bytes,
                    raw_body,
                    padding.PKCS1v15(),
                    hashes.SHA256()
                )
            except Exception as e:
                print(f"BlockBee Assinatura Inválida: {e}")
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b"invalid_signature")
                return

            try:
                data = json.loads(raw_body.decode('utf-8'))
            except Exception:
                data = {}

            # Extrair order_id da query string ou do payload
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            order_id = query_params.get("order_id", [None])[0] or data.get("order_id")

            # BlockBee envia pending=0 quando a transação foi confirmada e encaminhada
            pending = data.get("pending")
            # Se pending for 0 ou None (ou string "0"), consideramos pago
            if str(pending) == "0" and order_id:
                threading.Thread(target=deliver_order_async, args=(order_id,), daemon=True).start()
                
                # Monitorar volume acumulado BlockBee em USD (limite $1,000 / 30 dias sem KYC)
                try:
                    # Se convert=1 ou data tem price/value_coin, usamos o valor em USD registrado no pedido
                    conn_vol = sqlite3.connect(DB_PATH)
                    c_vol = conn_vol.cursor()
                    c_vol.execute("SELECT SUM(amount) FROM orders WHERE payment_method LIKE '%blockbee%' AND status = 'paid' AND created_at >= datetime('now', '-30 days')")
                    vol_row = c_vol.fetchone()
                    total_vol = vol_row[0] or 0.0
                    conn_vol.close()
                    
                    if total_vol >= 800.0:
                        bot_tok = os.getenv("STORE_BOT_TOKEN") or "8861845885:AAFlofn8dVAcpzn9ewj6Wjss6TcacZ5d1ko"
                        admin_chat = "671901048"
                        alerta_msg = (
                            f"⚠️ *ALERTA DE LIMITE BLOCKBEE (SEM KYC)*\n\n"
                            f"Volume nos últimos 30 dias: *${total_vol:.2f} / $1,000.00*\n"
                            f"Você atingiu mais de 80% do teto sem KYC da conta atual.\n"
                            f"Gere uma nova API Key em outra conta ou faça o KYC Parcial para evitar interrupção de pagamentos!"
                        )
                        requests.post(f"https://api.telegram.org/bot{bot_tok}/sendMessage", json={
                            "chat_id": admin_chat,
                            "text": alerta_msg,
                            "parse_mode": "Markdown"
                        }, timeout=5)
                except Exception as vol_err:
                    print("Erro ao calcular volume BlockBee:", vol_err)

            # BlockBee exige resposta 200 com corpo "*ok*"
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"*ok*")
            return

        self.send_response(404)
        self.end_headers()

def run_server(port=8099):
    server = HTTPServer(('', port), WebhookHandler)
    print(f"Servidor Webhook Oficial rodando na porta {port}...")
    server.serve_forever()

if __name__ == "__main__":
    run_server()
