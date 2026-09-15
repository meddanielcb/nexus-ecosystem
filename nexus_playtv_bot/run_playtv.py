import os
import sys
import json
import logging
import uuid
import sqlite3
import io
import time
import qrcode
from datetime import datetime, timedelta, timezone

# Fuso horário oficial do ecossistema: BRT (UTC-3)
TZ_BRT = timezone(timedelta(hours=-3))

def to_brt_str(dt_str, fmt="%d/%m/%Y às %H:%M"):
    """Converte string UTC (do SQLite) para horário de Brasília (BRT) formatado"""
    if not dt_str:
        return "N/A"
    try:
        # Se contiver 'T', padronizar
        clean_str = dt_str.replace("T", " ")
        if "." in clean_str:
            clean_str = clean_str.split(".")[0]
        dt = datetime.strptime(clean_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        return dt.astimezone(TZ_BRT).strftime(fmt)
    except Exception:
        return dt_str
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from db import init_db, DB_PATH, db_connect
from services import (
    create_pixget_charge,
    convert_usd_to_crypto,
    get_network_fee_estimate,
    create_blockbee_payment,
    generate_iptv_access
)
from notifier import alert_playtv_sale, alert_playtv_trial
from ibo_injector import activate_smart_tv_ibo
from partner_apps import (
    PARTNER_APPS,
    PARTNER_APPS_CODE,
    PARTNER_CODE_HINT,
    PLAYSTORE_APPS,
    MASTERX_DOWNLOADER_CODE,
    MASTERX_APK_URL,
    WINDOWS_SMARTERS_URL,
    IPHONE_APP,
    PORTAL_URL,
    SERVER_DNS_PRIMARY,
    SERVER_DNS_ALT,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nexus_playtv")

def parse_iso_or_br(exp_str):
    """Parser tolerante de datas: aceita ISO 8601 (YYYY-MM-DD HH:MM:SS) e o formato
    BR legado (DD/MM/YYYY às HH:MM) que circulava nos registros antigos."""
    if not exp_str:
        return None
    s = str(exp_str).strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y às %H:%M",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
    ):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s)
    except Exception:
        raise ValueError(f"Formato de data não reconhecido: {exp_str!r}")

BOT_TOKEN = "8979028734:AAFvHUW2ML8XmUnRXtY8f5j6l-pOeKxwj5s"

with open("/opt/data/nexus_playtv_bot/products_playtv.json") as f:
    PRODUCTS = json.load(f)

AWAITING_CPF = {}
AWAITING_TV_CODES = {} # user_id -> {'order_id': order_id, 'm3u_url': url}

def get_main_keyboard():
    return [
        [InlineKeyboardButton("📺 Planos", callback_data="view_plans"), InlineKeyboardButton("📦 Minha Conta", callback_data="my_access")],
        [
            InlineKeyboardButton("📱 Instalação", callback_data="how_to_install"),
            InlineKeyboardButton("🚀 Ativar TV", callback_data="auto_activate_tv")
        ],
        [
            InlineKeyboardButton("🎁 Indicação", callback_data="referral_program"),
            InlineKeyboardButton("❓ Suporte", callback_data="support_faq")
        ]
    ]

# Menu persistente inferior (barra de digitação): Planos, Instalação, Minha Conta, Menu Inicial
def get_persistent_reply_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📺 Planos"), KeyboardButton("📱 Instalação")],
            [KeyboardButton("📦 Minha Conta"), KeyboardButton("🏠 Menu Inicial")]
        ],
        resize_keyboard=True
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args if context and context.args else []
    
    conn = db_connect()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
              (user.id, user.username or "", user.first_name or ""))
    
    # Se entrou via link de indicação (ex: /start ref_123456)
    if args and len(args) > 0 and args[0].startswith("ref_"):
        referrer_id = args[0].replace("ref_", "").strip()
        try:
            c.execute("CREATE TABLE IF NOT EXISTS referrals (id INTEGER PRIMARY KEY AUTOINCREMENT, referrer_id INTEGER, referred_user_id INTEGER UNIQUE, status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            c.execute("INSERT OR IGNORE INTO referrals (referrer_id, referred_user_id) VALUES (?, ?)", (int(referrer_id), user.id))
        except Exception as ref_e:
            logger.error(f"Erro ao salvar referral: {ref_e}")

    conn.commit()
    conn.close()

    text = (
        f"⚡ *Olá, {user.first_name}! Bem-vindo ao Nexus PlayTV.*\n\n"
        "Sua central definitiva de entretenimento, esportes ao vivo e streaming de elite.\n\n"
        "🛡️ *Tecnologia e Diferenciais Exclusivos:*\n"
        "• *StreamCore™ Ultra-P2P:* Arquitetura de rede em malha (mesh) imune ao *traffic shaping* e bloqueios de operadoras.\n"
        "• *Engine Go™ Anti-Delay:* Transmissão esportiva em tempo real (assista aos clássicos e lutas antes do vizinho gritar o gol).\n"
        "• *Estabilidade Anti-Queda & Baixo Consumo:* Transmissão fluida em 4K HDR mesmo em conexões modestas a partir de 15 Mbps (zero travamentos).\n"
        "• *Ativação Smart TV por Foto:* Envie uma foto da tela da sua TV e nossa IA ativa seu aplicativo em segundos, sem digitação chata.\n"
        "• *Entrega Atômica 24/7:* Liberação instantânea no PIX ou Cripto (USDT) sem intervenção humana.\n"
        "• *+25.000 Canais + 120.000 Filmes & Séries:* Todos os streamings, esportes e canais premium unificados.\n\n"
        "👇 *Escolha uma opção abaixo para começar:*"
    )
    
    banner_path = "/opt/data/nexus_playtv_bot/assets/nexus_playtv_banner.png"
    persistent_kb = get_persistent_reply_keyboard()
    if os.path.exists(banner_path):
        try:
            with open(banner_path, "rb") as photo_file:
                await update.message.reply_photo(
                    photo=photo_file,
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(get_main_keyboard()),
                    parse_mode="Markdown"
                )
        except Exception:
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(get_main_keyboard()),
                parse_mode="Markdown"
            )
    else:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(get_main_keyboard()),
            parse_mode="Markdown"
        )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user

    async def safe_edit(text, reply_markup=None, parse_mode="Markdown"):
        try:
            await query.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception:
            await query.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)

    if data == "main_menu":
        text = (
            f"⚡ *Nexus PlayTV - Menu Principal*\n\n"
            "Escolha o que deseja acessar:"
        )
        banner_path = "/opt/data/nexus_playtv_bot/assets/nexus_playtv_banner.png"
        if os.path.exists(banner_path):
            try:
                with open(banner_path, "rb") as photo_file:
                    await query.message.reply_photo(
                        photo=photo_file,
                        caption=text,
                        reply_markup=InlineKeyboardMarkup(get_main_keyboard()),
                        parse_mode="Markdown"
                    )
                    return
            except Exception:
                pass
        await safe_edit(text, reply_markup=InlineKeyboardMarkup(get_main_keyboard()))
        return

    if data == "view_plans":
        text = (
            "📺 *Planos & Assinaturas Nexus PlayTV*\n\n"
            "Tecnologia *StreamCore™ Ultra-P2P* e *Engine Go™ Anti-Delay*.\n"
            "Sem contratos, sem fidelidade e com *Entrega Atômica 24/7*.\n"
            "Todos os planos liberam +25.000 canais + filmes + séries em 4K HDR.\n\n"
            "👇 *Selecione o plano ideal para você:*"
        )
        keyboard = [
            [InlineKeyboardButton("⚽ Pass 3 Jogos (4h cada) - R$ 14,90", callback_data="prod_pack_3_games")],
            [InlineKeyboardButton("📺 Mensal (30 Dias) - a partir de R$ 31,90", callback_data="tier_monthly")],
            [InlineKeyboardButton("🔥 Trimestral (90 Dias) - a partir de R$ 79,90", callback_data="tier_quarterly")],
            [InlineKeyboardButton("⭐ Semestral (180 Dias) - a partir de R$ 149,90", callback_data="tier_semiannual")],
            [InlineKeyboardButton("👑 Anual VIP (365 Dias) - a partir de R$ 249,90", callback_data="tier_annual")],
            [InlineKeyboardButton("⬅️ Voltar ao Menu", callback_data="main_menu")]
        ]
        await safe_edit(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Seletor de Telas por Categoria de Plano
    if data == "tier_monthly":
        text = (
            "📺 *Nexus PlayTV — Plano Mensal (30 Dias)*\n\n"
            "💡 *O substituto definitivo da TV a cabo tradicional.*\n"
            "Assista a todos os canais fechados, pay-per-view e streamings sem fidelidade nem multas.\n\n"
            "👇 *Selecione a quantidade de telas simultâneas:*"
        )
        kb = [
            [InlineKeyboardButton("📺 1 Tela (Principal) - R$ 31,90", callback_data="prod_iptv_mensal_1")],
            [InlineKeyboardButton("📺+📺 2 Telas (Sala + Quarto) - R$ 42,80", callback_data="prod_iptv_mensal_2")],
            [InlineKeyboardButton("📺+📺+📱 3 Telas (Residência) - R$ 53,70", callback_data="prod_iptv_mensal_3")],
            [InlineKeyboardButton("⬅️ Voltar aos Planos", callback_data="view_plans")]
        ]
        await safe_edit(text, reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "tier_quarterly":
        text = (
            "🔥 *Nexus PlayTV — Plano Trimestral (90 Dias)*\n\n"
            "⭐ *A Escolha Mais Inteligente:* Economize R$ 15,80 garantindo 3 meses de acesso ininterrupto por apenas **R$ 26,63/mês**!\n"
            "Garante a temporada do futebol e grandes finais sem reajuste.\n\n"
            "👇 *Selecione a quantidade de telas:*"
        )
        kb = [
            [InlineKeyboardButton("🔥 1 Tela - R$ 79,90", callback_data="prod_iptv_trimestral_1")],
            [InlineKeyboardButton("🔥+📺 2 Telas (Família) - R$ 109,90", callback_data="prod_iptv_trimestral_2")],
            [InlineKeyboardButton("🔥+📱 3 Telas (Residência) - R$ 139,90", callback_data="prod_iptv_trimestral_3")],
            [InlineKeyboardButton("⬅️ Voltar aos Planos", callback_data="view_plans")]
        ]
        await safe_edit(text, reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "tier_semiannual":
        text = (
            "⭐ *Nexus PlayTV — Plano Semestral (180 Dias)*\n\n"
            "🏆 *Temporada Completa Garantida:* 6 meses inteiros de sinal ultra-estável por apenas **R$ 24,98/mês**.\n"
            "Ideal para quem quer tranquilidade total o ano quase todo sem boletos mensais.\n\n"
            "👇 *Selecione a quantidade de telas:*"
        )
        kb = [
            [InlineKeyboardButton("⭐ 1 Tela - R$ 149,90", callback_data="prod_iptv_semestral_1")],
            [InlineKeyboardButton("⭐+📺 2 Telas (Família) - R$ 204,90", callback_data="prod_iptv_semestral_2")],
            [InlineKeyboardButton("⭐+📱 3 Telas (Residência) - R$ 259,90", callback_data="prod_iptv_semestral_3")],
            [InlineKeyboardButton("⬅️ Voltar aos Planos", callback_data="view_plans")]
        ]
        await safe_edit(text, reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "tier_annual":
        text = (
            "👑 *Nexus PlayTV — Plano Anual VIP (365 Dias)*\n\n"
            "💎 *Máxima Categoria & Menor Custo:* 1 ano de entretenimento premium por apenas **R$ 20,82/mês**!\n"
            "Zero preocupação com renovações. Suporte concierge prioritário 24/7.\n\n"
            "👇 *Selecione o plano anual:*"
        )
        kb = [
            [InlineKeyboardButton("👑 1 Tela - R$ 249,90", callback_data="prod_iptv_anual_1")],
            [InlineKeyboardButton("👑 2 Telas VIP (Mais Vendido) - R$ 329,90", callback_data="prod_iptv_anual_2")],
            [InlineKeyboardButton("👑 3 Telas VIP (Residência) - R$ 399,90", callback_data="prod_iptv_anual_3")],
            [InlineKeyboardButton("⬅️ Voltar aos Planos", callback_data="view_plans")]
        ]
        await safe_edit(text, reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "referral_program":
        ref_link = f"https://t.me/Nexus_playtvbot?start=ref_{user.id}"
        text = (
            "🎁 *Programa de Indicação VIP — Nexus PlayTV*\n\n"
            "Compartilhe a melhor experiência de streaming com seus amigos e seja recompensado!\n\n"
            "🔥 *Como Funciona:*\n"
            "1. Envie seu link exclusivo abaixo para um amigo ou grupo.\n"
            "2. Quando ele assinar qualquer plano no Nexus PlayTV...\n"
            "3. Você ganha **1 MÊS INTEIRO DE ACESSO GRÁTIS** adicionado à sua assinatura!\n\n"
            f"🔗 *Seu Link Exclusivo de Indicação:*\n`{ref_link}`\n\n"
            "💡 *Dica:* Não há limites! Se 3 amigos assinarem pelo seu link, você ganha 3 meses inteiramente grátis."
        )
        share_tg = f"https://t.me/share/url?url={ref_link}&text=Assista%20todos%20os%20canais%2C%20futebol%20e%20filmes%20em%204K%20sem%20travar%20com%20o%20Nexus%20PlayTV!"
        share_wa = f"https://api.whatsapp.com/send?text=Assista%20todos%20os%20canais%2C%20futebol%20ao%20vivo%20e%20filmes%20em%204K%20sem%20travar%3A%20{ref_link}"
        kb = [
            [InlineKeyboardButton("📋 Copiar Link de Indicação", callback_data=f"copy_ref_{user.id}")],
            [InlineKeyboardButton("🟢 Enviar no WhatsApp", url=share_wa)],
            [InlineKeyboardButton("✈️ Enviar no Telegram", url=share_tg)],
            [InlineKeyboardButton("⬅️ Voltar ao Menu", callback_data="main_menu")]
        ]
        await safe_edit(text, reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "redeem_game_pass":
        # Ativar 1 passe de jogo do saldo do usuário
        conn = db_connect()
        c = conn.cursor()
        c.execute("""
        SELECT id, remaining_passes FROM game_passes 
        WHERE user_id = ? AND remaining_passes > 0 
        ORDER BY id ASC LIMIT 1
        """, (user.id,))
        pass_row = c.fetchone()

        if not pass_row:
            conn.close()
            await query.answer("Você não tem Passes de Jogo disponíveis no momento!", show_alert=True)
            await query.message.reply_text(
                "⚠️ *Você não possui saldo de Passes de Jogo!*\n\n"
                "Garanta agora o seu **Pack 3 Jogos por R$ 14,90** e use quando quiser nos próximos 30 dias:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⚽ Comprar Pack 3 Jogos (R$ 14,90)", callback_data="prod_pack_3_games")],
                    [InlineKeyboardButton("📺 Ver Planos Mensais", callback_data="view_plans")]
                ]),
                parse_mode="Markdown"
            )
            return

        pass_id, remaining = pass_row[0], pass_row[1]
        
        # Debitar 1 passe
        new_remaining = remaining - 1
        c.execute("UPDATE game_passes SET remaining_passes = ? WHERE id = ?", (new_remaining, pass_id))

        # Atualizar texto de saldo no pedido correspondente
        c.execute("""
        UPDATE orders
        SET delivered_credentials = ?
        WHERE order_id = (SELECT order_id FROM game_passes WHERE id = ?)
        """, (f"Pack 3 Jogos (Restantes: {new_remaining})", pass_id))
        
        # Gerar o acesso de 4 horas
        cred = generate_iptv_access(is_trial=True) # 4 horas ilimitadas
        redemption_id = f"PASS_{user.id}_{int(time.time())}"
        
        # Inserir apenas no pass_redemptions com expiração
        c.execute("""
        INSERT INTO pass_redemptions (user_id, pass_id, username, password, m3u_url, expires_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (user.id, pass_id, cred["username"], cred["password"], cred["m3u_url"], cred["expires_at"]))

        conn.commit()
        conn.close()

        # Disparar notificação no @Alerta_nexusbot do Daniel
        try:
            alert_playtv_sale(
                plan_name="Resgate de Passe de Jogo (4h)",
                amount_str="Débito de Saldo (1/3)",
                method="PASSE RESGATADO",
                customer_info=f"@{user.username or 'SemUser'} (ID {user.id})",
                order_id=redemption_id
            )
        except Exception as e_alert:
            logger.error(f"Erro ao disparar alerta de resgate: {e_alert}")

        # 3. Gerar URL do WebPlayer MasterX
        web_player_url = f"http://painelmaster.app/portal/?user={cred['username']}&pass={cred['password']}"

        text = (
            "🎉 *SEU ACESSO DE JOGO (4 HORAS) FOI ATIVADO!*\n\n"
            f"⚽ *Saldo restante de passes:* {new_remaining} de 3\n"
            f"⏳ *Válido até:* {to_brt_str(cred['expires_at'])} (4 horas)\n\n"
            f"📋 *DADOS DE ACESSO:*\n"
            f"• Servidor: `{cred['server_url']}`\n"
            f"• Usuário: `{cred['username']}`\n"
            f"• Senha: `{cred['password']}`\n\n"
            f"🔗 *Lista M3U:*\n`{cred['m3u_url']}`\n\n"
            "✨ *COMO ASSISTIR AGORA:*\n"
            "1️⃣ *No Computador/Celular:* Clique no botão **Assistir no Navegador** abaixo para abrir sem digitar senha!\n"
            "2️⃣ *Na Smart TV:* Clique em **Ativar na Smart TV** e mande a foto da tela do seu app!"
            " (funciona com FunPlays, Magic PLAY, Power Play, EPIC PLAY, IBO Player e Smart IPTV)"
        )
        keyboard = [
            [InlineKeyboardButton("▶️ Assistir no Navegador (WebPlayer)", url=web_player_url)],
            [InlineKeyboardButton("🚀 Ativar na Smart TV", callback_data="auto_activate_tv")],
            [InlineKeyboardButton("⬅️ Menu Principal", callback_data="main_menu")]
        ]
        await safe_edit(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "redeem_bonus_reward":
        # Ativar 1 recompensa de 30 dias de indicação da carteira
        conn = db_connect()
        c = conn.cursor()
        c.execute("""
            SELECT id, days FROM bonus_rewards
            WHERE user_id = ? AND status = 'available'
            ORDER BY id ASC LIMIT 1
        """, (user.id,))
        bonus_row = c.fetchone()

        if not bonus_row:
            conn.close()
            await query.answer("Você não tem bônus de indicação disponíveis para ativar!", show_alert=True)
            return

        b_id, b_days = bonus_row[0], bonus_row[1]

        # Gerar linha de 30 dias no MasterX
        cred = generate_iptv_access(duration_days=b_days)
        bonus_order_id = f"BONUS_{user.id}_{int(time.time())}"
        cred_str = f"Usuário: {cred['username']} | Senha: {cred['password']} | Servidor: {cred['server_url']}"

        # Gravar ordem paga de bônus para histórico
        c.execute("""
            INSERT INTO orders (order_id, user_id, username, product_id, status, payment_method, amount, delivered_credentials, m3u_url, expires_at)
            VALUES (?, ?, ?, 'bônus_indicação_30d', 'paid', 'referral_bonus', 0.0, ?, ?, ?)
        """, (bonus_order_id, user.id, user.username or "", cred_str, cred["m3u_url"], cred["expires_at"]))

        # Marcar bônus como resgatado
        c.execute("UPDATE bonus_rewards SET status = 'redeemed', activated_at = CURRENT_TIMESTAMP WHERE id = ?", (b_id,))
        conn.commit()

        # Checar se ainda sobraram outros bônus
        c.execute("SELECT COUNT(*) FROM bonus_rewards WHERE user_id = ? AND status = 'available'", (user.id,))
        rem_bonus = c.fetchone()[0]
        conn.close()

        web_player_url = f"http://painelmaster.app/portal/?user={cred['username']}&pass={cred['password']}"

        text = (
            "🎉 *PARABÉNS! SEU MÊS DE BÔNUS ESTÁ ATIVO!*\n\n"
            f"🎁 *Recompensa de Indicação Ativada com Sucesso!*\n\n"
            f"📋 *DADOS DE ACESSO (30 DIAS):*\n"
            f"• Servidor: `{cred['server_url']}`\n"
            f"• Usuário: `{cred['username']}`\n"
            f"• Senha: `{cred['password']}`\n\n"
            f"🔗 *Lista M3U:*\n`{cred['m3u_url']}`\n\n"
            f"⏳ *Validade:* 30 Dias (Até {cred['expires_at']})\n"
            f"🎟️ *Meses de bônus ainda na sua carteira:* {rem_bonus}\n\n"
            "📺 *Como Assistir:*\n"
            "• Clique abaixo para assistir no navegador sem senha;\n"
            "• Ou use na sua Smart TV Samsung, LG ou TV Box."
        )

        kb = [
            [InlineKeyboardButton("▶️ Assistir no Navegador (WebPlayer)", url=web_player_url)],
            [InlineKeyboardButton("📱 Ativar na Smart TV", callback_data="auto_activate_tv")],
            [InlineKeyboardButton("💼 Minha Conta / Carteira", callback_data="my_access")]
        ]
        await safe_edit(text, reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "free_trial":
        conn = db_connect()
        c = conn.cursor()
        c.execute("SELECT iptv_username, iptv_password, server_url, m3u_url, expires_at FROM free_trials WHERE user_id = ?", (user.id,))
        existing = c.fetchone()
        
        if existing:
            conn.close()
            text = (
                "⚠️ *Você já gerou um teste grátis anteriormente!*\n\n"
                "Para garantir a estabilidade dos nossos servidores, permitimos apenas 1 teste por usuário.\n\n"
                f"👤 *Seu Usuário de Teste:* `{existing[0]}`\n"
                f"🔑 *Senha:* `{existing[1]}`\n"
                f"🌐 *Servidor:* `{existing[2]}`\n\n"
                "Gostou da qualidade e quer acesso ilimitado com todos os canais e filmes em 4K? Assine agora mesmo!"
            )
            keyboard = [
                [InlineKeyboardButton("📺 Assinar Agora (a partir de R$ 31,90)", callback_data="view_plans")],
                [InlineKeyboardButton("⬅️ Voltar ao Menu", callback_data="main_menu")]
            ]
            await safe_edit(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        cred = generate_iptv_access(is_trial=True)
        trial_id = f"TRIAL_{user.id}"
        c.execute("""
        INSERT INTO free_trials (user_id, username, iptv_username, iptv_password, server_url, m3u_url, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user.id, user.username or "", cred["username"], cred["password"], cred["server_url"], cred["m3u_url"], cred["expires_at"]))
        
        # Também registrar na tabela orders para gerar a página VIP interativa instantânea
        c.execute("""
        INSERT OR REPLACE INTO orders (order_id, user_id, username, product_id, status, delivered_credentials)
        VALUES (?, ?, ?, 'Teste Grátis (4h)', 'paid', ?)
        """, (trial_id, user.id, user.username or "", f"Usuário: {cred['username']} | Senha: {cred['password']} | Servidor: {cred['server_url']}"))

        conn.commit()
        conn.close()

        try:
            alert_playtv_trial(user.username, user.id)
        except Exception:
            pass

        vip_page_url = f"https://nexus.pixget.io/vip/{trial_id}"
        web_player_url = f"http://painelmaster.app/portal/?user={cred['username']}&pass={cred['password']}"

        text = (
            "🎉 *SEU TESTE GRÁTIS DE 4 HORAS FOI LIBERADO!*\n\n"
            "Todos os canais Premiere, Champions, UFC, Filmes e Séries em 4K estão ativos.\n\n"
            "📱 *Toque no botão abaixo para abrir seu Cartão VIP Interativo:*\n"
            "Lá você tem o botão direto para assistir no celular sem digitar nada e botões de cópia rápida para sua Smart TV."
        )
        keyboard = [
            [InlineKeyboardButton("✨ ABRIR CARTÃO VIP INTERATIVO", url=vip_page_url)],
            [InlineKeyboardButton("▶️ Assistir Agora no Navegador", url=web_player_url)],
            [InlineKeyboardButton("📱 Passo a Passo Smart TV", callback_data="how_to_install")],
            [InlineKeyboardButton("📺 Gostei, quero Assinar!", callback_data="view_plans")]
        ]
        await safe_edit(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "how_to_install":
        text = (
            "📱 *Como Instalar o Nexus PlayTV no seu Aparelho*\n\n"
            "Selecione o seu dispositivo para ver as instruções rápidas na tela ou baixe o **Guia Completo em PDF**:"
        )
        keyboard = [
            [InlineKeyboardButton("📄 Baixar Guia VIP em PDF Completo", callback_data="download_guide_pdf")],
            [
                InlineKeyboardButton("📺 Smart TV Samsung", callback_data="inst_samsung"),
                InlineKeyboardButton("📺 Smart TV LG", callback_data="inst_lg")
            ],
            [
                InlineKeyboardButton("🔵 Roku TV", callback_data="inst_roku"),
                InlineKeyboardButton("🍏 Apple TV", callback_data="inst_appletv")
            ],
            [
                InlineKeyboardButton("🔥 Fire Stick", callback_data="inst_android"),
                InlineKeyboardButton("📱 Android TV / TV Box", callback_data="inst_androidtv")
            ],
            [
                InlineKeyboardButton("📲 Celular (Android / iPhone)", callback_data="inst_mobile"),
                InlineKeyboardButton("💻 Computador / Web", callback_data="inst_pc")
            ],
            [
                InlineKeyboardButton("⬅️ Voltar", callback_data="main_menu")
            ]
        ]
        await safe_edit(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "download_guide_pdf":
        conn = db_connect()
        c = conn.cursor()
        c.execute("SELECT product_id, delivered_credentials, m3u_url, expires_at FROM orders WHERE user_id = ? AND status = 'paid' ORDER BY created_at DESC LIMIT 1", (user.id,))
        last_order = c.fetchone()
        conn.close()

        pdf_path = f"/tmp/Guia_VIP_{user.id}.pdf"
        
        # Extrair dados reais se o usuário tiver assinatura paga
        pname = "Nexus PlayTV VIP"
        iptv_user = "nexus_cliente"
        iptv_pass = "********"
        server_dns = "http://atmt.space"
        m3u_url = "http://atmt.space"
        exp_str = "Consulte seu bot"

        if last_order:
            pid, cred_str, m3u, exp = last_order
            pname = PRODUCTS.get(pid, {}).get("name", pid)
            exp_str = exp or "Ativo"
            if m3u:
                m3u_url = m3u
            if cred_str and "Usuário:" in cred_str:
                try:
                    parts = cred_str.split("|")
                    for p in parts:
                        if "Usuário:" in p:
                            iptv_user = p.split("Usuário:")[1].strip()
                        elif "Senha:" in p:
                            iptv_pass = p.split("Senha:")[1].strip()
                        elif "Servidor:" in p:
                            server_dns = p.split("Servidor:")[1].strip()
                except Exception:
                    pass

        try:
            from pdf_generator import generate_playtv_vip_dossier
            generate_playtv_vip_dossier(
                pdf_path=pdf_path,
                username=iptv_user,
                password=iptv_pass,
                server_url=server_dns,
                m3u_url=m3u_url,
                plan_name=pname,
                valid_until=exp_str
            )
            with open(pdf_path, "rb") as f_pdf:
                await query.message.reply_document(
                    document=f_pdf,
                    filename="Guia_VIP_Nexus_PlayTV.pdf",
                    caption=f"📄 *Seu Guia VIP Personalizado:* Instruções e dados oficiais de configuração ({server_dns}).",
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.error(f"Erro ao gerar PDF: {e}")
            await query.answer("Erro ao gerar o PDF. Tente novamente em instantes.", show_alert=True)
        return

    if data.startswith("inst_"):
        device = data.replace("inst_", "")
        instructions = {
            "samsung": (
                "📺 *Instalação na Smart TV Samsung*\n\n"
                "✨ *Você NÃO precisa digitar senhas nem links na TV!*\n\n"
                "1️⃣ Abra a loja de aplicativos da sua Samsung;\n"
                f"2️⃣ Baixe um destes parceiros: *{PARTNER_APPS[0]}*, *{PARTNER_APPS[3]}* ou *EPIC PLAY*;\n"
                "3️⃣ Abra o aplicativo. Ele abre já pedindo para ativar;\n"
                f"4️⃣ {PARTNER_CODE_HINT}\n\n"
                "🤖 *Ou deixe o robô configurar pra você:* clique no botão abaixo e envie uma foto da tela do aplicativo."
            ),
            "lg": (
                "📺 *Instalação na Smart TV LG (webOS)*\n\n"
                "✨ *Você NÃO precisa digitar senhas nem links na TV!*\n\n"
                "1️⃣ Abra a LG Content Store;\n"
                f"2️⃣ Baixe um destes parceiros: *{PARTNER_APPS[0]}*, *{PARTNER_APPS[3]}* ou *Super Play*;\n"
                "3️⃣ Abra o aplicativo;\n"
                f"4️⃣ {PARTNER_CODE_HINT}\n\n"
                "🤖 *Ou deixe o robô configurar pra você:* clique no botão abaixo e envie uma foto da tela do aplicativo."
            ),
            "android": (
                "🔥 *Instalação no Fire TV Stick*\n\n"
                "1️⃣ Abra o aplicativo *Downloader* na sua TV;\n"
                f"2️⃣ Na barra de endereço digite o código: *`{MASTERX_DOWNLOADER_CODE}`*\n"
                f"   (ou o endereço completo: `{MASTERX_APK_URL}`)\n"
                f"3️⃣ Instale o aplicativo *MASTERX* e abra;\n"
                f"4️⃣ Se pedir o *Código Parceiro*, digite: `{PARTNER_APPS_CODE}` (código do app MASTERX)\n\n"
                "🤖 *Ativação automática:* abra o app na TV e clique no botão abaixo para o robô gravar a lista via foto!"
            ),
            "androidtv": (
                "📱 *Instalação no Android TV / TV Box / Google TV*\n\n"
                f"1️⃣ Na *Play Store*, instale: *{PLAYSTORE_APPS[0]}* (oficial) ou *{PLAYSTORE_APPS[1]}*;\n"
                "2️⃣ Alternativa via *Downloader* (APK oficial):\n"
                f"   • Código: *`{MASTERX_DOWNLOADER_CODE}`*  →  `{MASTERX_APK_URL}`\n"
                "3️⃣ Abra o aplicativo e conecte com o seu Usuário e Senha Nexus;\n"
                f"4️⃣ Se pedir o *Código Parceiro*, digite: `{PARTNER_APPS_CODE}` (código do app MASTERX)\n\n"
                "🤖 *Ativação automática:* abra o app na TV e clique no botão abaixo para o robô gravar a lista via foto!"
            ),
            "roku": (
                "🔵 *Instalação na Roku TV (AOC, Philco, TCL Roku, Semp)*\n\n"
                "1. Na tela inicial da Roku, vá em *Streaming Channels*;\n"
                f"2. Pesquise e adicione o canal *{PLAYSTORE_APPS[2]}* ou *Smarters Player*;\n"
                "3. Abra o app e conecte com o seu Usuário e Senha Nexus:"
            ),
            "appletv": (
                "🍏 *Instalação no Apple TV*\n\n"
                f"1. Abra a App Store do Apple TV;\n"
                f"2. Baixe o *{IPHONE_APP}* ou *Smarters Player*;\n"
                "3. Abra o app e conecte com o seu Usuário e Senha Nexus:"
            ),
            "mobile": (
                " *Instalação no Celular / Tablet*\n\n"
                f"1️⃣ *Android:* instale o *{PLAYSTORE_APPS[0]}* na Play Store "
                f"(ou *{PLAYSTORE_APPS[1]}*);\n"
                f"2️⃣ *iPhone / iPad:* baixe o *{IPHONE_APP}* na App Store;\n"
                f"3️⃣ *No navegador:* acesse o WebPlayer em *{PORTAL_URL}* com o seu usuário e senha."
            ),
            "apple": (
                " *Instalação no iPhone / iPad*\n\n"
                f"1. Abra a App Store;\n"
                f"2. Baixe o *{IPHONE_APP}* ou *Smarters Player Lite*;\n"
                "3. Escolha a opção *API Xtream Codes* e preencha:\n"
                f"   • Servidor: `{SERVER_DNS_PRIMARY}`\n"
                "   • Usuário e Senha da sua conta Nexus."
            ),
            "pc": (
                "💻 *Instalação no Computador (Windows / Mac)*\n\n"
                "✨ *Opção 1 — Instalador oficial (recomendado no Windows):*\n"
                f"• Baixe e abra: `{WINDOWS_SMARTERS_URL}`\n"
                "• Selecione *Xtream Codes API* e preencha:\n"
                f"  - Servidor: `{SERVER_DNS_PRIMARY}`\n"
                "  - Usuário e Senha da sua conta Nexus.\n\n"
                "✨ *Opção 2 — WebPlayer no navegador (Chrome / Safari / Edge):*\n"
                f"• Acesse: *{PORTAL_URL}*\n"
                "• Entre com o seu Usuário e Senha. Roda na hora, sem instalar nada.\n\n"
                "✨ *Opção 3 — Mac:* baixe *IPTV Smarters Pro* na App Store, ou abra a sua "
                "*Lista M3U* no VLC (Cmd+N → Abrir Rede)."
            )
        }
        text = instructions.get(device, "Instruções disponíveis no suporte.")
        
        # Ativação automática (multi-app: FunPlays / IBO Player / Smart IPTV / SmartOne)
        AUTO_ACTIVATE_DEVICES = ["samsung", "lg", "roku", "appletv", "android", "androidtv", "mobile"]
        keyboard = []
        if device in AUTO_ACTIVATE_DEVICES:
            keyboard.append([InlineKeyboardButton("🚀 Ativar Minha TV Automaticamente", callback_data="auto_activate_tv")])
        keyboard.extend([
            [InlineKeyboardButton("⚡ Gerar Teste Grátis (4h)", callback_data="free_trial")],
            [InlineKeyboardButton("📺 Ver Planos", callback_data="view_plans")],
            [InlineKeyboardButton("⬅️ Voltar aos Apps", callback_data="how_to_install")]
        ])
        await safe_edit(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "auto_activate_tv":
        # Checar se usuário tem acesso ativo (ordem paga, teste grátis ou passe resgatado)
        conn = db_connect()
        c = conn.cursor()
        
        m3u = None
        
        # 1. Checar se tem passe resgatado recente
        c.execute("SELECT m3u_url FROM pass_redemptions WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user.id,))
        p_row = c.fetchone()
        if p_row and p_row[0]:
            m3u = p_row[0]

        # 2. Checar ordem paga com m3u
        if not m3u:
            c.execute("SELECT m3u_url FROM orders WHERE user_id = ? AND status = 'paid' AND m3u_url IS NOT NULL ORDER BY created_at DESC LIMIT 1", (user.id,))
            order_row = c.fetchone()
            if order_row and order_row[0]:
                m3u = order_row[0]
        
        # 3. Checar teste grátis
        if not m3u:
            c.execute("SELECT m3u_url FROM free_trials WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user.id,))
            trial_row = c.fetchone()
            if trial_row and trial_row[0]:
                m3u = trial_row[0]
                
        conn.close()
        
        if not m3u:
            await query.answer("Você ainda não possui um plano ou teste ativo!", show_alert=True)
            await query.message.reply_text(
                "⚠️ *Nenhum acesso ativo encontrado!*\n\n"
                "Para ativar a sua Smart TV, você precisa ter um plano ou gerar um teste grátis primeiro:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⚡ Gerar Teste Grátis (4h)", callback_data="free_trial")],
                    [InlineKeyboardButton("📺 Assinar um Plano", callback_data="view_plans")]
                ]),
                parse_mode="Markdown"
            )
            return

        AWAITING_TV_CODES[user.id] = {"m3u_url": m3u}
        await query.message.reply_text(
            "📺 *CONFIGURAÇÃO AUTOMÁTICA DE SMART TV*\n\n"
            "✨ *Você tem duas formas super fáceis:*\n\n"
            "📸 *FORMA 1 (Mais fácil):* Tire uma foto (ou print) da tela da sua TV com o aplicativo aberto e envie aqui no chat!\n\n"
            "⌨️ *FORMA 2:* Digite o seu **Device ID** e **Device Key** separados por espaço.\n"
            "Exemplo: `a1:b2:c3:d4:e5:f6 123456`\n\n"
            "*(Nosso sistema lê sua foto ou código e injeta os canais na sua TV em 8 segundos)*",
            parse_mode="Markdown"
        )
        return

    if data == "support_faq":
        text = (
            "❓ *Dúvidas Frequentes & Suporte Nexus PlayTV*\n\n"
            "• *O serviço trava nos jogos?*\n"
            "Não! Utilizamos tecnologia P2P e servidores CDN dedicados com proteção contra bloqueios de operadoras.\n\n"
            "• *Quantos aparelhos posso usar?*\n"
            "Os planos individuais funcionam em 1 aparelho por vez. O Plano Anual Família permite 2 telas simultâneas.\n\n"
            "• *Como é feita a entrega?*\n"
            "100% imediata! Assim que o pagamento (PIX ou Cripto) é confirmado, o bot envia o usuário, senha e link na hora aqui no chat.\n\n"
            "Precisa de ajuda com configuração ou dúvidas? Nosso suporte está disponível 24 horas!"
        )
        keyboard = [
            [InlineKeyboardButton("📺 Assinar um Plano", callback_data="view_plans")],
            [InlineKeyboardButton("⬅️ Voltar ao Menu", callback_data="main_menu")]
        ]
        await safe_edit(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "my_access":
        conn = db_connect()
        c = conn.cursor()
        
        # 1. Checar saldo de passes de jogo
        c.execute("""
            SELECT SUM(remaining_passes) FROM game_passes 
            WHERE user_id = ? AND remaining_passes > 0 AND expires_at > datetime('now')
        """, (user.id,))
        pass_res = c.fetchone()
        remaining_passes = pass_res[0] if pass_res and pass_res[0] else 0

        # 2. Checar recompensas de indicação acumuladas na carteira
        c.execute("""
            SELECT COUNT(*), SUM(days) FROM bonus_rewards
            WHERE user_id = ? AND status = 'available'
        """, (user.id,))
        bonus_res = c.fetchone()
        bonus_count = bonus_res[0] if bonus_res and bonus_res[0] else 0
        bonus_days = bonus_res[1] if bonus_res and bonus_res[1] else 0

        # 3. Checar pedidos pagos
        c.execute("SELECT order_id, product_id, delivered_credentials, created_at, m3u_url, expires_at FROM orders WHERE user_id = ? AND status = 'paid' ORDER BY created_at DESC LIMIT 3", (user.id,))
        orders = c.fetchall()

        # 4. Mapa de saldo restante por pacote (antecipa a query antes de fechar a conexao)
        c.execute("SELECT order_id, remaining_passes FROM game_passes WHERE user_id = ?", (user.id,))
        pass_map = {row[0]: row[1] for row in c.fetchall()}

        # 5. Buscar últimos resgates de passes de jogo
        c.execute("""
            SELECT username, redeemed_at, expires_at, password, 'http://atmt.space', m3u_url 
            FROM pass_redemptions 
            WHERE user_id = ? 
            ORDER BY id DESC LIMIT 3
        """, (user.id,))
        redemptions = c.fetchall()
        conn.close()

        keyboard = []

        if not orders and remaining_passes == 0 and bonus_count == 0:
            text = (
                "📦 *Central da Sua Conta & Carteira*\n\n"
                "Você ainda não possui assinaturas nem passes ativos no momento.\n\n"
                "Adquira um dos nossos planos, indique amigos para ganhar meses grátis ou gere um teste de 4 horas para conhecer a qualidade dos canais."
            )
            keyboard.append([InlineKeyboardButton("⚡ Gerar Teste Grátis (4h)", callback_data="free_trial")])
            keyboard.append([InlineKeyboardButton("📺 Ver Planos", callback_data="view_plans")])
        else:
            text = "💼 *Central da Sua Conta & Carteira:*\n\n"

            if bonus_count > 0:
                text += (
                    f"🎁 *Recompensas de Indicação (Acumuladas)*\n"
                    f"🎟️ *Saldo Disponível:* `{bonus_count} meses grátis` ({bonus_days} dias de acesso)\n"
                    f"💡 *Status:* Guardados na sua carteira. Ative quando quiser!\n\n"
                )
                keyboard.append([InlineKeyboardButton(f"🎁 ATIVAR 1 MÊS DE BÔNUS ({bonus_count} DISPONÍVEL)", callback_data="redeem_bonus_reward")])
            
            if remaining_passes > 0:
                text += (
                    f"⚽ *Passes Avulsos de Jogo / Futebol / Lutas*\n"
                    f"🎟️ *Saldo Disponível na sua Carteira:* `{remaining_passes} acessos` (4 horas cada)\n"
                    f"💡 *Como usar:* Quando começar a partida ou evento que deseja assistir, clique no botão abaixo para liberar suas 4 horas na hora!\n\n"
                )
                keyboard.append([InlineKeyboardButton("⚽ ATIVAR 1 ACESSO DE JOGO AGORA (4H)", callback_data="redeem_game_pass")])

            if orders:
                text += "📋 *Histórico de Compras & Assinaturas:*\n"
                for o in orders:
                    oid, pid, cred, date, m3u, exp = o[0], o[1], o[2], o[3], o[4], o[5]
                    pname = PRODUCTS.get(pid, {}).get("name", pid)
                    date_brt = to_brt_str(date)
                    exp_brt = to_brt_str(exp)
                    text += f"• *{pname}*\n  📅 Compra: {date_brt}\n"
                    if pid == "pack_3_games":
                        # Buscar saldo atual desse pacote (ja carregado antes do close)
                        rem = pass_map.get(oid, 0)
                        text += f"  🎟️ Saldo deste pacote: `{rem} de 3 passes`\n"
                    elif cred:
                        text += f"  🔑 Credenciais: `{cred}`\n"
                    if exp:
                        text += f"  ⏳ Validade do Pacote: {exp_brt}\n"
                    text += "\n"

            if redemptions:
                text += "⚡ *Últimas Ativações de Jogos (4h cada):*\n"
                for r in redemptions:
                    u_pass, r_at, exp_at, pw_pass, srv_pass, m3u_pass = r[0], r[1], r[2], r[3], r[4], r[5]
                    r_at_brt = to_brt_str(r_at)
                    exp_at_brt = to_brt_str(exp_at)
                    srv_clean = srv_pass or "http://atmt.space"
                    text += (
                        f"• *Ativado em:* `{r_at_brt}`\n"
                        f"  👤 *Usuário:* `{u_pass}`\n"
                        f"  🔑 *Senha:* `{pw_pass}`\n"
                        f"  🌐 *Servidor:* `{srv_clean}`\n"
                        f"  ⏳ *Válido até:* `{exp_at_brt}`\n\n"
                    )

            keyboard.append([InlineKeyboardButton("📱 Ativar na Smart TV", callback_data="auto_activate_tv")])

        keyboard.append([InlineKeyboardButton("⬅️ Voltar ao Menu", callback_data="main_menu")])

        await safe_edit(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("prod_direct_"):
        pid = data.replace("prod_direct_", "")
        p = PRODUCTS.get(pid)
        if not p:
            await query.message.reply_text("Plano indisponível.")
            return

        text = (
            f"*{p['name']}*\n\n"
            f"{p['description']}\n\n"
            f"💰 *Investimento:*\n"
            f"• *PIX:* R$ {p['price_brl']:.2f}\n"
            f"• *Cripto:* ${p['price_usd']:.2f} USDT\n\n"
            f"⚡ *Entrega Instantânea das credenciais no chat.*\n\n"
            f"👇 *Escolha como deseja pagar:*"
        )

        keyboard = [
            [InlineKeyboardButton(f"🟢 Pagar via PIX (R$ {p['price_brl']:.2f})", callback_data=f"ask_cpf_{pid}")],
            [InlineKeyboardButton(f"💎 Pagar com Cripto (${p['price_usd']:.2f} USDT)", callback_data=f"crypto_hub_{pid}")],
            [InlineKeyboardButton("⬅️ Voltar aos Planos", callback_data="view_plans")]
        ]
        await safe_edit(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("prod_"):
        pid = data.replace("prod_", "")
        p = PRODUCTS.get(pid)
        if not p:
            await query.message.reply_text("Plano indisponível.")
            return

        text = (
            f"*{p['name']}*\n\n"
            f"{p['description']}\n\n"
            f"💰 *Investimento:*\n"
            f"• *PIX:* R$ {p['price_brl']:.2f}\n"
            f"• *Cripto:* ${p['price_usd']:.2f} USDT\n\n"
            f"⚡ *Entrega Instantânea das credenciais no chat.*\n\n"
            f"👇 *Escolha como deseja pagar:*"
        )

        keyboard = [
            [InlineKeyboardButton(f"🟢 Pagar via PIX (R$ {p['price_brl']:.2f})", callback_data=f"ask_cpf_{pid}")],
            [InlineKeyboardButton(f"💎 Pagar com Cripto (${p['price_usd']:.2f} USDT)", callback_data=f"crypto_hub_{pid}")],
            [InlineKeyboardButton("⬅️ Voltar aos Planos", callback_data="view_plans")]
        ]
        await safe_edit(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("crypto_hub_"):
        pid = data.replace("crypto_hub_", "")
        p = PRODUCTS.get(pid)
        text = (
            f"💎 *Pagamento Cripto — {p['name']}*\n\n"
            f"Valor Base: *${p['price_usd']:.2f} USDT*\n\n"
            "Escolha a categoria de rede:"
        )
        keyboard = [
            [InlineKeyboardButton("⚡ Redes Recomendadas (Instantâneas)", callback_data=f"fast_net_{pid}")],
            [InlineKeyboardButton("🌐 Outras Redes (BTC | ETH)", callback_data=f"other_net_{pid}")],
            [InlineKeyboardButton("⬅️ Voltar ao Plano", callback_data=f"prod_{pid}")]
        ]
        await safe_edit(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("fast_net_"):
        pid = data.replace("fast_net_", "")
        p = PRODUCTS.get(pid)
        base = p["price_usd"]
        
        fee_base = get_network_fee_estimate("base/usdc")
        total_base = base if fee_base <= 0.60 else base + fee_base

        text = (
            f"⚡ *Redes Recomendadas — {p['name']}*\n\n"
            "Redes rápidas com liquidação imediata.\n"
            "Selecione a blockchain desejada:"
        )
        keyboard = [
            [InlineKeyboardButton(f"🟡 BSC (BNB Chain) - ${base:.2f} USDT (~1-2m)", callback_data=f"bbpay_bep20/usdt_{pid}")],
            [InlineKeyboardButton(f"🔵 Base (Coinbase) - ${total_base:.2f} USDC (~1-2m)", callback_data=f"bbpay_base/usdc_{pid}")],
            [InlineKeyboardButton(f"🟣 Polygon - ${base:.2f} USDT (~2-3m)", callback_data=f"bbpay_polygon/usdt_{pid}")],
            [InlineKeyboardButton(f"🟣 Solana - ${base:.2f} USDT (~1m)", callback_data=f"bbpay_sol/usdt_{pid}")],
            [InlineKeyboardButton(f"🔵 Arbitrum - ${base:.2f} USDC (~1-2m)", callback_data=f"bbpay_arbitrum/usdc_{pid}")],
            [InlineKeyboardButton("⬅️ Voltar", callback_data=f"crypto_hub_{pid}")]
        ]
        await safe_edit(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("other_net_"):
        pid = data.replace("other_net_", "")
        p = PRODUCTS.get(pid)
        base = p["price_usd"]

        fee_btc = get_network_fee_estimate("btc")
        total_btc = base if fee_btc <= 0.60 else base + fee_btc

        fee_eth = get_network_fee_estimate("eth")
        total_eth = base if fee_eth <= 0.60 else base + fee_eth

        fee_erc20 = get_network_fee_estimate("erc20/usdt")
        total_erc20 = base if fee_erc20 <= 0.60 else base + fee_erc20

        text = (
            f"🌐 *Outras Redes — {p['name']}*\n\n"
            "Redes tradicionais sujeitas a confirmações e taxas de minerador.\n"
            "Selecione a opção desejada:"
        )
        keyboard = [
            [InlineKeyboardButton(f"🟠 Bitcoin (BTC) - ${total_btc:.2f} (~10-30m)", callback_data=f"bbpay_btc_{pid}")],
            [InlineKeyboardButton(f"🔷 Ethereum (ETH) - ${total_eth:.2f} (~3-8m)", callback_data=f"bbpay_eth_{pid}")],
            [InlineKeyboardButton(f"💎 Ethereum ERC-20 - ${total_erc20:.2f} USDT (~3-8m)", callback_data=f"bbpay_erc20/usdt_{pid}")],
            [InlineKeyboardButton("⬅️ Voltar", callback_data=f"crypto_hub_{pid}")]
        ]
        await safe_edit(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("ask_cpf_"):
        pid = data.replace("ask_cpf_", "")
        p = PRODUCTS.get(pid)
        AWAITING_CPF[user.id] = {"pid": pid, "price": p["price_brl"]}
        text = (
            f"🟢 *Pagamento via PIX — {p['name']}*\n\n"
            f"Valor: *R$ {p['price_brl']:.2f}*\n\n"
            "Por gentileza, informe o seu **CPF** (apenas números) para emissão do PIX Oficial do Banco Central:\n\n"
            "ℹ️ *Aviso importante:* O pagamento deve ser feito a partir da conta bancária vinculada a este mesmo CPF. "
            "PIX de contas de terceiros não serão aprovados pelo sistema."
        )
        keyboard = [[InlineKeyboardButton("⬅️ Cancelar", callback_data="main_menu")]]
        await safe_edit(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("bbpay_"):
        parts = data.split("_")
        coin = parts[1]
        pid = "_".join(parts[2:])
        p = PRODUCTS.get(pid)
        base_usd = p["price_usd"]
        fee = get_network_fee_estimate(coin)
        total_usd = base_usd if fee <= 0.60 else base_usd + fee
        crypto_qty, display_qty = convert_usd_to_crypto(coin, total_usd)

        order_id = f"PLAYTV_{uuid.uuid4().hex[:8].upper()}"

        try:
            bb = create_blockbee_payment(coin, order_id)
            address = bb.get("address_in")
            qr_url = bb.get("qr_code")

            conn = db_connect()
            c = conn.cursor()
            c.execute("""
            INSERT INTO orders (order_id, user_id, username, product_id, payment_method, amount, status, payment_id)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            """, (order_id, user.id, user.username or "", pid, f"crypto_{coin}", total_usd, address))
            conn.commit()
            conn.close()

            coin_label = coin.upper()
            text = (
                f"💎 *Pagamento Cripto — Nexus PlayTV*\n\n"
                f"📺 *Plano:* {p['name']}\n"
                f"💵 *Total:* `{total_usd:.2f} USD`\n"
                f"🪙 *Moeda/Rede:* `{coin_label}`\n\n"
                f"👇 *Envie exatamente a quantidade abaixo:*\n"
                f"```\n{display_qty}\n```\n\n"
                f"📍 *Endereço da Carteira para Depósito:*\n"
                f"`{address}`\n\n"
                f"⚡ *Aprovação Automática:* O servidor identifica sua transação diretamente na blockchain sem precisar enviar comprovante.\n"
                f"⏱️ *Tempo Médio de Confirmação:* 2 a 5 minutos (aguarda validação de blocos pela rede).\n"
                f"⏳ *Validade da fatura:* 30 minutos."
            )

            keyboard = [
                [InlineKeyboardButton("📋 Copiar Endereço", callback_data=f"copy_addr_{order_id}")],
                [InlineKeyboardButton("🔄 Já paguei (Checar Status)", callback_data=f"check_order_{order_id}")],
                [InlineKeyboardButton("⬅️ Cancelar e Voltar", callback_data="main_menu")]
            ]

            # Gerar QR Code localmente com alta nitidez para pagamento cripto
            qr_bytes = io.BytesIO()
            qr_img = qrcode.make(address)
            qr_img.save(qr_bytes, format="PNG")
            qr_bytes.seek(0)

            # Excluir mensagem de texto anterior para evitar duplicidade e enviar a foto com o QR Code
            try:
                await query.message.delete()
            except Exception:
                pass

            try:
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=qr_bytes,
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
                return
            except Exception as e_qr:
                logger.error(f"Erro ao enviar QR code cripto: {e_qr}")

            await safe_edit(text, reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            logger.error(f"Erro BlockBee: {e}")
            await safe_edit(f"❌ Erro ao gerar pagamento cripto: {e}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Voltar", callback_data="main_menu")]]))
        return

    if data.startswith("copy_addr_"):
        order_id = data.replace("copy_addr_", "")
        conn = db_connect()
        c = conn.cursor()
        c.execute("SELECT payment_id FROM orders WHERE order_id = ?", (order_id,))
        row = c.fetchone()
        conn.close()
        if row and row[0]:
            await query.answer("Endereço enviado abaixo para cópia!", show_alert=False)
            await query.message.reply_text(f"`{row[0]}`", parse_mode="Markdown")
        else:
            await query.answer("Endereço não encontrado.", show_alert=True)
        return

    if data.startswith("check_order_"):
        order_id = data.replace("check_order_", "")
        conn = db_connect()
        c = conn.cursor()
        c.execute("SELECT status, delivered_credentials, m3u_url, expires_at, payment_id, product_id FROM orders WHERE order_id = ?", (order_id,))
        row = c.fetchone()
        conn.close()

        if not row:
            await query.answer("Pedido não encontrado.", show_alert=True)
            return

        status, creds, m3u, exp, payment_id, pid = row
        
        # Fallback de Polling em tempo real se o webhook ainda não tiver chegado
        if status != "paid" and payment_id:
            try:
                # 1. Checagem se for PIX
                if not payment_id.startswith("0x"):
                    from services import get_pixget_headers, PIXGET_BASE_URL
                    import requests
                    chk_url = f"{PIXGET_BASE_URL.rstrip('/')}/api/v1/payments/{payment_id}/status"
                    r = requests.get(chk_url, headers=get_pixget_headers(), timeout=5)
                    if r.status_code == 200:
                        st_data = r.json().get("data", {})
                        if st_data.get("status") == "completed":
                            import importlib.util
                            spec = importlib.util.spec_from_file_location("wh_server", "/opt/data/digital_store_bot/webhook_server.py")
                            wh_mod = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(wh_mod)
                            wh_mod.deliver_playtv_order_async(order_id)
                # 2. Checagem se for Cripto (BlockBee)
                else:
                    import requests
                    from services import BLOCKBEE_API_KEY
                    # Consultar logs da BlockBee para verificar se recebeu o depósito
                    # A moeda pode ser inferida pelo método de pagamento ou testar bep20/usdt
                    for coin_check in ["bep20/usdt", "polygon/usdt", "trc20/usdt"]:
                        chk_url = f"https://api.blockbee.io/{coin_check}/logs/"
                        r = requests.get(chk_url, params={"apikey": BLOCKBEE_API_KEY, "address": payment_id}, timeout=5)
                        if r.status_code == 200:
                            logs_data = r.json()
                            # Se houver callback executado ou pagamento detectado com pending=0
                            callbacks = logs_data.get("callbacks", [])
                            for cb in callbacks:
                                if cb.get("result") in ["success", "pending_zero"] or cb.get("response_status") in [200, 502] or cb.get("pending") == 0:
                                    import importlib.util
                                    spec = importlib.util.spec_from_file_location("wh_server", "/opt/data/digital_store_bot/webhook_server.py")
                                    wh_mod = importlib.util.module_from_spec(spec)
                                    spec.loader.exec_module(wh_mod)
                                    wh_mod.deliver_playtv_order_async(order_id)
                                    break
                
                # Reconsultar banco após polling
                conn2 = db_connect()
                c2 = conn2.cursor()
                c2.execute("SELECT status, delivered_credentials, m3u_url, expires_at FROM orders WHERE order_id = ?", (order_id,))
                row2 = c2.fetchone()
                conn2.close()
                if row2:
                    status, creds, m3u, exp = row2
            except Exception as e:
                logger.error(f"Erro no polling de status: {e}")

        if status == "paid":
            await query.answer("✅ Pagamento confirmado!", show_alert=True)
            await query.message.reply_text(
                f"🎉 *PAGAMENTO APROVADO COM SUCESSO!*\n\n"
                f"🆔 *Pedido:* `{order_id}`\n\n"
                f"📋 *Acesso Liberado:*\n`{creds}`\n\n"
                f"🔗 *Lista M3U:*\n`{m3u or 'N/A'}`\n\n"
                f"⏳ *Validade:* {exp}",
                parse_mode="Markdown"
            )
        else:
            await query.answer("🔍 Checando transação na blockchain... Ainda aguardando blocos da rede.", show_alert=True)
            try:
                await query.message.reply_text(
                    "⏳ *Status do Pagamento Cripto:*\n\n"
                    "• A sua transferência já foi enviada ou está em processo de mineração.\n"
                    "• *Tempo Médio:* Leva de 2 a 5 minutos para os nós da rede (Base/BSC/Polygon) confirmarem e liquidarem.\n"
                    "• *Fique tranquilo:* O robô está monitorando a cada 60 segundos. Assim que os blocos confirmarem, seu acesso e credenciais serão entregues automaticamente aqui!",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
            return

    if data.startswith("copy_"):
        parts = data.split("_")
        action = parts[1]
        order_id = "_".join(parts[2:])

        if action == "ref":
            uid = order_id
            link = f"https://t.me/Nexus_playtvbot?start=ref_{uid}"
            await query.answer("Link copiado!", show_alert=False)
            await query.message.reply_text(
                f"📋 *Seu link de indicação:* (toque para copiar)\n\n`{link}`",
                parse_mode="Markdown"
            )
            return

        conn = db_connect()
        c = conn.cursor()
        c.execute("SELECT delivered_credentials, payment_id, m3u_url FROM orders WHERE order_id = ?", (order_id,))
        row = c.fetchone()
        conn.close()

        labels = {"addr": "Endereço", "dns": "Servidor", "user": "Usuário", "pass": "Senha", "m3u": "Lista M3U"}

        val = ""
        if row:
            cred_str = row[0] or ""
            pay_id = row[1] or ""
            m3u = row[2] or ""

            if action == "addr":
                # Endereço da carteira cripto (gravado em payment_id no fluxo BlockBee)
                val = pay_id
            elif action == "m3u":
                val = m3u
            else:
                # formato: Usuário: xxx | Senha: yyy | Servidor: zzz
                for part in cred_str.split("|"):
                    if action == "dns" and "Servidor:" in part:
                        val = part.split("Servidor:")[1].strip()
                    elif action == "user" and "Usuário:" in part:
                        val = part.split("Usuário:")[1].strip()
                    elif action == "pass" and "Senha:" in part:
                        val = part.split("Senha:")[1].strip()

        if val:
            label = labels.get(action, action.upper())
            await query.answer(f"Copiado: {val}", show_alert=True)
            await query.message.reply_text(
                f"📋 *{label}:*\n`{val}`\n\n_(Toque no texto acima para copiar)_",
                parse_mode="Markdown"
            )
        else:
            await query.answer("Não há dados para copiar neste pedido.", show_alert=True)
            await query.message.reply_text(
                "⚠️ Não encontrei o dado solicitado para este pedido. Se o pagamento ainda não foi confirmado, aguarde a liberação e tente novamente."
            )
        return

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg_text = update.message.text.strip()

    if msg_text == "📺 Planos":
        await update.message.reply_text(
            "📺 *Planos & Assinaturas Nexus PlayTV*\n\n"
            "Tecnologia *StreamCore™ Ultra-P2P* e *Engine Go™ Anti-Delay*.\n"
            "Sem contratos, sem fidelidade e com *Entrega Atômica 24/7*.\n\n"
            "👇 *Selecione o plano desejado:*",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚽ Pass 3 Jogos (4h cada) - R$ 14,90", callback_data="prod_pack_3_games")],
                [InlineKeyboardButton("📺 Mensal (30 Dias) - a partir de R$ 31,90", callback_data="tier_monthly")],
                [InlineKeyboardButton("🔥 Trimestral (90 Dias) - a partir de R$ 79,90", callback_data="tier_quarterly")],
                [InlineKeyboardButton("⭐ Semestral (180 Dias) - a partir de R$ 149,90", callback_data="tier_semiannual")],
                [InlineKeyboardButton("👑 Anual VIP (365 Dias) - a partir de R$ 249,90", callback_data="tier_annual")],
                [InlineKeyboardButton("⬅️ Menu", callback_data="main_menu")]
            ]),
            parse_mode="Markdown"
        )
        return
    elif msg_text == "⚡ Teste Grátis (4h)":
        await update.message.reply_text(
            "⚡ *Teste Degustação Grátis (4 Horas)*\n\n"
            "Assista a todos os canais Premiere, UFC, Filmes e Séries em 4K sem pagar nada e comprove a estabilidade StreamCore™.\n\n"
            "Clique no botão abaixo para gerar instantaneamente seu acesso:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚡ Confirmar e Liberar Teste (4 Horas)", callback_data="free_trial")]]),
            parse_mode="Markdown"
        )
        return
    elif msg_text in ("📱 Instalação", "📱 Como Instalar"):
        await update.message.reply_text("Selecione o seu aparelho:", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Smart TV Samsung", callback_data="inst_samsung"), InlineKeyboardButton("Smart TV LG", callback_data="inst_lg")],
            [InlineKeyboardButton("TV Box / Firestick", callback_data="inst_android"), InlineKeyboardButton("iPhone / Apple TV", callback_data="inst_apple")],
            [InlineKeyboardButton("Computador / Mac", callback_data="inst_pc")]
        ]))
        return
    elif msg_text in ("📦 Minha Conta", "💼 Minha Conta"):
        # Chamar a rotina de minha conta
        class DummyQuery:
            def __init__(self, msg, usr):
                self.message = msg
                self.from_user = usr
                self.data = "my_access"
            async def answer(self, *a, **k): pass
        
        dummy_update = Update(update.update_id, callback_query=DummyQuery(update.message, user))
        await callback_handler(dummy_update, context)
        return
    elif msg_text in ("🏠 Menu Inicial", "🏠 Menu"):
        await start_command(update, context)
        return
    elif msg_text in ("❓ Suporte", "❓ Dúvidas & Suporte"):
        await update.message.reply_text("Precisa de ajuda com o PlayTV?", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Ver Dúvidas Frequentes", callback_data="support_faq")]]))
        return

    # Tratamento de Ativação Automática de Smart TV Samsung / LG via 2Captcha
    if user.id in AWAITING_TV_CODES:
        session = AWAITING_TV_CODES[user.id]
        parts = [p.strip() for p in msg_text.replace("\n", " ").replace(",", " ").split() if p.strip()]
        m3u_url = session.get("m3u_url")

        mac_in = None
        key_in = None
        if len(parts) >= 2:
            mac_in, key_in = parts[0], parts[1]
        elif len(parts) == 1 and session.get("mac_pending"):
            # Usuario ja teve o MAC lido pela IA e agora mandou apenas o Device Key
            mac_in, key_in = session.get("mac_pending"), parts[0]

        if not mac_in or not key_in:
            await update.message.reply_text(
                "⚠️ *Formato incorreto!*\n\n"
                "Por favor, envie o **Device ID** e o **Device Key** separados por espaço.\n"
                "Exemplo:\n`a1:b2:c3:d4:e5:f6 123456`",
                parse_mode="Markdown"
            )
            return

        # Normaliza o MAC (aceita com ou sem dois-pontos)
        mac_clean = "".join(ch for ch in mac_in if ch.isalnum())
        if len(mac_clean) == 12:
            mac_fmt = ":".join(mac_clean[i:i + 2] for i in range(0, 12, 2)).lower()
        else:
            await update.message.reply_text(
                "⚠️ *Esse Device ID não parece válido.*\n\n"
                f"Recebi: `{mac_in}`\n"
                "O formato correto tem 12 caracteres, como: `a1:b2:c3:d4:e5:f6`",
                parse_mode="Markdown"
            )
            return

        key_clean = "".join(ch for ch in key_in if ch.isalnum())
        if not key_clean:
            await update.message.reply_text("⚠️ O Device Key deve conter números. Tente novamente.")
            return

        status_msg = await update.message.reply_text(
            "⏳ *Conectando à sua Smart TV e autenticando...*\n"
            "Aguarde de 10 a 40 segundos. Não feche o aplicativo na TV...",
            parse_mode="Markdown"
        )

        from tv_activator import activate_tv

        res = activate_tv(
            mac=mac_fmt,
            key=key_clean,
            playlist_url=m3u_url,
            site=session.get("site", "") or "",
            app_name=session.get("app", "") or "",
            playlist_name="Nexus PlayTV VIP",
        )

        if res.get("success"):
            AWAITING_TV_CODES.pop(user.id, None)
            app_label = res.get("app_label") or "Smart TV"

            try:
                alert_playtv_sale(
                    plan_name=f"Ativação Smart TV ({app_label})",
                    amount_str="Automática (digitação)",
                    method=app_label.upper(),
                    customer_info=f"@{user.username or 'SemUser'} (MAC {mac_fmt})",
                    order_id=f"TV_{int(time.time())}"
                )
            except Exception as e_tv:
                logger.error(f"Erro alerta TV: {e_tv}")

            await status_msg.edit_text(
                "🎉 *SUA SMART TV FOI ATIVADA COM SUCESSO!*\n\n"
                f"✅ Aplicativo: *{app_label}*\n"
                "✅ A lista completa de canais, filmes e séries já está gravada.\n\n"
                "📺 *Como assistir agora:*\n"
                "1. Saia da tela de configurações na TV;\n"
                "2. Selecione a lista *Nexus PlayTV VIP*;\n"
                "3. Se não aparecer, pressione **Reload / Recarregar**.\n\n"
                "Bom divertimento! 🍿⚽",
                parse_mode="Markdown"
            )
        else:
            err_msg = res.get("message") or "Erro desconhecido"
            await status_msg.edit_text(
                f"❌ *Não foi possível ativar sua TV:*\n`{err_msg}`\n\n"
                "Confira se o **Device ID** e o **Device Key** estão exatamente como aparecem na tela "
                "do aplicativo e envie novamente no formato:\n"
                "`a1:b2:c3:d4:e5:f6 123456`",
                parse_mode="Markdown"
            )
        return

    if user.id in AWAITING_CPF:
        stored = AWAITING_CPF.pop(user.id)
        pid = stored["pid"] if isinstance(stored, dict) else stored
        cpf_clean = "".join(filter(str.isdigit, msg_text))

        if len(cpf_clean) != 11:
            AWAITING_CPF[user.id] = stored
            await update.message.reply_text("⚠️ CPF inválido. Por favor, envie um CPF válido com 11 dígitos:")
            return

        p = PRODUCTS.get(pid)
        order_id = f"PLAYTV_{uuid.uuid4().hex[:8].upper()}"

        try:
            charge = create_pixget_charge(
                amount_brl=p["price_brl"],
                order_id=order_id,
                description=f"Nexus PlayTV - {p['name']}",
                cpf=cpf_clean
            )

            conn = db_connect()
            c = conn.cursor()
            c.execute("""
            INSERT INTO orders (order_id, user_id, username, product_id, payment_method, amount, status, payment_id)
            VALUES (?, ?, ?, ?, 'pix', ?, 'pending', ?)
            """, (order_id, user.id, user.username or "", pid, p["price_brl"], charge.get("payment_id")))
            conn.commit()
            conn.close()

            qr_code = charge.get("qr_code")
            text = (
                f"🟢 *Pagamento PIX Gerado com Sucesso!*\n\n"
                f"📺 *Plano:* {p['name']}\n"
                f"💵 *Valor:* R$ {p['price_brl']:.2f}\n"
                f"🆔 *Pedido:* `{order_id}`\n\n"
                f"📋 *PIX Copia e Cola:*\n"
                f"```\n{qr_code}\n```\n\n"
                f"⚡ *Liberação Automática:* Assim que o pagamento for concluído, o bot enviará as credenciais de acesso diretamente neste chat.\n"
                f"⏳ *Validade:* 15 minutos."
            )

            keyboard = [
                [InlineKeyboardButton("🔄 Já paguei (Checar Status)", callback_data=f"check_order_{order_id}")],
                [InlineKeyboardButton("⬅️ Cancelar", callback_data="main_menu")]
            ]

            qr = qrcode.QRCode(box_size=10, border=2)
            qr.add_data(qr_code)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            bio = io.BytesIO()
            img.save(bio, "PNG")
            bio.seek(0)

            await update.message.reply_photo(photo=bio, caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Erro PIX: {e}")
            err_str = str(e)
            if "RECEITA FEDERAL" in err_str.upper() or "CPF IRREGULAR" in err_str.upper():
                msg_err = "⚠️ *CPF não encontrado ou irregular na Receita Federal.*\nPor favor, digite um CPF válido para que o Banco Central aprove a cobrança PIX:"
                AWAITING_CPF[user.id] = stored
            else:
                msg_err = f"❌ *Erro ao gerar PIX:* {err_str}"
            await update.message.reply_text(msg_err, parse_mode="Markdown")
        return

async def push_trial_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Job periódico (executado a cada 1 minuto) para engajamento e conversão de testes"""
    try:
        conn = db_connect()
        c = conn.cursor()
        now = datetime.now()

        # 1. Alerta de 30 minutos restantes (Momento 3h30 após o teste)
        # expires_at - 35min <= now <= expires_at
        c.execute("""
            SELECT id, user_id, username, expires_at 
            FROM free_trials 
            WHERE reminded_30m = 0
        """)
        trials_to_check = c.fetchall()

        for tid, uid, uname, exp_str in trials_to_check:
            try:
                exp_dt = parse_iso_or_br(exp_str)
                # Se faltam menos de 35 minutos para expirar e ainda não expirou
                if timedelta(seconds=0) < (exp_dt - now) <= timedelta(minutes=35):
                    text_alert = (
                        "⚠️ *SEU TESTE GRÁTIS EXPIRA EM MENOS DE 30 MINUTOS!*\n\n"
                        "Não deixe o sinal cortar no meio da programação!\n\n"
                        "💡 *Assine agora com Entrega Atômica e assista sem interrupções:*\n"
                        "• 📺 *Plano Mensal:* a partir de R$ 31,90\n"
                        "• 🔥 *Trimestral (Economia VIP):* a partir de R$ 79,90\n\n"
                        "⚡ Liberação imediata no PIX ou Cripto:"
                    )
                    kb = [
                        [InlineKeyboardButton("📺 Assinar Plano Mensal (R$ 31,90)", callback_data="prod_iptv_mensal_1")],
                        [InlineKeyboardButton("🔥 Ver Todos os Planos", callback_data="view_plans")]
                    ]
                    try:
                        await context.bot.send_message(chat_id=uid, text=text_alert, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
                        c.execute("UPDATE free_trials SET reminded_30m = 1 WHERE id = ?", (tid,))
                        conn.commit()
                    except Exception as e:
                        logger.error(f"Erro ao enviar reminder 30m para {uid}: {e}")
            except Exception as pe:
                logger.error(f"Erro parse date reminder: {pe}")

        # 2. Alerta de Teste Expirado (Momento 4h05 - 5 minutos após o corte)
        c.execute("""
            SELECT id, user_id, username, expires_at 
            FROM free_trials 
            WHERE reminded_30m = 1 AND reminded_expired = 0
        """)
        expired_to_check = c.fetchall()

        for tid, uid, uname, exp_str in expired_to_check:
            try:
                exp_dt = parse_iso_or_br(exp_str)
                if now >= exp_dt:
                    text_expired = (
                        "🔒 *SEU SINAL DE TESTE FOI ENCERRADO!*\n\n"
                        "Gostou da tecnologia StreamCore™ e da qualidade 4K dos nossos canais?\n\n"
                        "Ative agora sua assinatura definitiva em menos de 1 minuto sem contratos nem fidelidade:\n\n"
                        "• 📺 *Plano Mensal (1 Tela):* R$ 31,90\n"
                        "• 🔥 *Trimestral (1 Tela):* R$ 79,90\n"
                        "• 👑 *Anual Família VIP (2 Telas):* R$ 329,90"
                    )
                    kb = [
                        [InlineKeyboardButton("📺 Assinar Plano Mensal (R$ 31,90)", callback_data="prod_iptv_mensal_1")],
                        [InlineKeyboardButton("⭐ Ver Todos os Planos", callback_data="view_plans")]
                    ]
                    try:
                        await context.bot.send_message(chat_id=uid, text=text_expired, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
                        c.execute("UPDATE free_trials SET reminded_expired = 1 WHERE id = ?", (tid,))
                        conn.commit()
                    except Exception as e:
                        logger.error(f"Erro ao enviar alerta expirado para {uid}: {e}")
            except Exception as pe:
                logger.error(f"Erro parse date expired: {pe}")

        # 3. Alertas de Vencimento de Assinaturas Mensais/Periódicas (3 dias, 1 dia, corte)
        # Ignora passes avulsos de horas (Pass Jogo / pack_3_games), que têm ciclo em minutos/horas, não em dias!
        c.execute("""
            SELECT order_id, user_id, product_id, expires_at, reminded_3d, reminded_1d, reminded_expired
            FROM orders
            WHERE status = 'paid' 
              AND expires_at IS NOT NULL 
              AND reminded_expired = 0
              AND product_id NOT LIKE '%Pass%' 
              AND product_id NOT LIKE '%pack_3_games%'
        """)
        paid_orders = c.fetchall()

        for oid, uid, pid, exp_str, r3d, r1d, rexp in paid_orders:
            try:
                exp_dt = parse_iso_or_br(exp_str)
                diff = exp_dt - now

                # 3.1 Aviso de 3 Dias Antes
                if timedelta(days=0) < diff <= timedelta(days=3) and r3d == 0:
                    text_3d = (
                        "🔔 *LEMBRETE VIP: SUA ASSINATURA VENCE EM BREVE!*\n\n"
                        f"Faltam menos de **3 dias** para o encerramento do seu acesso.\n\n"
                        "Evite o corte no meio do jogo ou da sua série favorita!\n"
                        "Renove agora com liberação automática imediata:"
                    )
                    kb_renov = [
                        [InlineKeyboardButton("🔄 Renovar Assinatura Agora", callback_data="view_plans")],
                        [InlineKeyboardButton("💬 Falar com Suporte", callback_data="support_faq")]
                    ]
                    try:
                        await context.bot.send_message(chat_id=uid, text=text_3d, reply_markup=InlineKeyboardMarkup(kb_renov), parse_mode="Markdown")
                        c.execute("UPDATE orders SET reminded_3d = 1 WHERE order_id = ?", (oid,))
                        conn.commit()
                    except Exception as e:
                        logger.error(f"Erro ao enviar reminder 3d para {uid}: {e}")

                # 3.2 Aviso de 24 Horas Antes
                elif timedelta(seconds=0) < diff <= timedelta(days=1) and r1d == 0:
                    text_1d = (
                        "⚠️ *ÚLTIMO DIA DE ACESSO — VENCE AMANHÃ!*\n\n"
                        "Seu sinal de TV e streaming será pausado em menos de 24 horas.\n\n"
                        "👇 Clique abaixo para renovar via PIX ou Cripto:"
                    )
                    kb_renov = [
                        [InlineKeyboardButton("⚡ Renovar Imediatamente", callback_data="view_plans")]
                    ]
                    try:
                        await context.bot.send_message(chat_id=uid, text=text_1d, reply_markup=InlineKeyboardMarkup(kb_renov), parse_mode="Markdown")
                        c.execute("UPDATE orders SET reminded_1d = 1 WHERE order_id = ?", (oid,))
                        conn.commit()
                    except Exception as e:
                        logger.error(f"Erro ao enviar reminder 1d para {uid}: {e}")

                # 3.3 Aviso de Corte no Vencimento
                elif now >= exp_dt and rexp == 0:
                    text_corte = (
                        "🔒 *SUA ASSINATURA NEXUS PLAYTV EXPIROU!*\n\n"
                        "O seu sinal foi temporariamente desativado.\n"
                        "Para reativar a grade completa na sua Smart TV agora mesmo, selecione a renovação abaixo:"
                    )
                    kb_renov = [
                        [InlineKeyboardButton("🔄 Reativar Sinal Agora", callback_data="view_plans")]
                    ]
                    try:
                        await context.bot.send_message(chat_id=uid, text=text_corte, reply_markup=InlineKeyboardMarkup(kb_renov), parse_mode="Markdown")
                        c.execute("UPDATE orders SET reminded_expired = 1 WHERE order_id = ?", (oid,))
                        conn.commit()
                    except Exception as e:
                        logger.error(f"Erro ao enviar aviso corte para {uid}: {e}")

            except Exception as pe:
                logger.error(f"Erro parse date order reminder: {pe}")

        # Marcar passes antigos resgatados para não poluir a tabela de ordens
        conn.close()
    except Exception as ge:
        logger.error(f"Erro geral push_trial_reminders: {ge}")

ADMIN_CHAT_ID = "671901048"

async def coupon_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gerenciamento de cupons exclusivo para o Daniel"""
    user = update.effective_user
    if str(user.id) != ADMIN_CHAT_ID:
        return

    text = update.message.text.strip().split()
    # /cupom CRIAR NOME DISCOUNT USOS
    if len(text) >= 2 and text[1].upper() == "CRIAR":
        if len(text) < 5:
            await update.message.reply_text("Uso: `/cupom CRIAR <CODIGO> <DESCONTO_PCT> <MAX_USOS>`\nEx: `/cupom CRIAR VIP100 100 1`", parse_mode="Markdown")
            return
        code = text[2].upper()
        try:
            disc = int(text[3])
            max_u = int(text[4])
        except ValueError:
            await update.message.reply_text("Desconto e Usos devem ser números inteiros.")
            return

        conn = db_connect()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO coupons (code, discount_pct, max_uses, created_by) VALUES (?, ?, ?, ?)",
                      (code, disc, max_u, "Daniel"))
            conn.commit()
            await update.message.reply_text(f"✅ *Cupom Criado!*\nCódigo: `{code}`\nDesconto: *{disc}%*\nUsos: *{max_u}*", parse_mode="Markdown")
        except sqlite3.IntegrityError:
            await update.message.reply_text("⚠️ Esse cupom já existe no sistema.")
        finally:
            conn.close()
        return

    elif len(text) >= 2 and text[1].upper() == "LISTAR":
        conn = db_connect()
        c = conn.cursor()
        c.execute("SELECT code, discount_pct, max_uses, used_count FROM coupons ORDER BY id DESC LIMIT 15")
        rows = c.fetchall()
        conn.close()
        if not rows:
            await update.message.reply_text("Nenhum cupom cadastrado.")
            return
        res = ["🎟️ *Cupons Cadastrados:*"]
        for r in rows:
            res.append(f"• `{r[0]}`: {r[1]}% OFF | Usados: {r[3]}/{r[2]}")
        await update.message.reply_text("\n".join(res), parse_mode="Markdown")
        return

    await update.message.reply_text(
        "🛠️ *Comandos de Cupons:* \n"
        "• `/cupom CRIAR <CODIGO> <PCT> <USOS>`\n"
        "• `/cupom LISTAR`",
        parse_mode="Markdown"
    )

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Le a foto da tela da Smart TV, extrai os codigos via OCR (Gemini Vision)
    e ativa a lista automaticamente no backend correto do aplicativo detectado."""
    user = update.effective_user

    # Auto-recuperar m3u se o usuario nao clicou antes no botao
    m3u_url = None
    if user.id in AWAITING_TV_CODES:
        m3u_url = AWAITING_TV_CODES[user.id].get("m3u_url")

    if not m3u_url:
        conn = db_connect()
        c = conn.cursor()
        c.execute("SELECT m3u_url FROM pass_redemptions WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user.id,))
        p_row = c.fetchone()
        if p_row and p_row[0]:
            m3u_url = p_row[0]
        if not m3u_url:
            c.execute("SELECT m3u_url FROM orders WHERE user_id = ? AND status = 'paid' AND m3u_url IS NOT NULL ORDER BY created_at DESC LIMIT 1", (user.id,))
            o_row = c.fetchone()
            if o_row and o_row[0]:
                m3u_url = o_row[0]
        if not m3u_url:
            c.execute("SELECT m3u_url FROM free_trials WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user.id,))
            t_row = c.fetchone()
            if t_row and t_row[0]:
                m3u_url = t_row[0]
        conn.close()

    if not m3u_url:
        await update.message.reply_text(
            "📸 Recebi sua foto! Para ativar a sua Smart TV, você precisa ter uma assinatura ou teste ativo primeiro.\n\n"
            "Gere um teste grátis ou assine um plano no menu:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚡ Gerar Teste Grátis (4h)", callback_data="free_trial")],
                [InlineKeyboardButton("📺 Assinar Plano", callback_data="view_plans")]
            ]),
            parse_mode="Markdown"
        )
        return

    status_msg = await update.message.reply_text(
        "🔍 *Analisando a foto da sua TV com Inteligência Artificial...*\n"
        "Lendo o **Device ID** e o **Device Key** na tela. Aguarde alguns segundos...",
        parse_mode="Markdown"
    )

    try:
        # Baixar a foto enviada pelo usuario
        photo = update.message.photo[-1]
        file_obj = await context.bot.get_file(photo.file_id)
        local_img = f"/tmp/tv_screen_{user.id}_{int(time.time())}.jpg"
        await file_obj.download_to_drive(local_img)

        # Visao computacional (Gemini Flash)
        from tv_vision_ocr import extract_tv_codes_from_image
        ocr_result = extract_tv_codes_from_image(local_img)

        from tv_activator import activate_tv, detect_app, APP_NAMES

        mac_found = ocr_result.get("mac")
        key_found = ocr_result.get("key")
        site_p = (ocr_result.get("site") or "").lower()
        app_p = (ocr_result.get("app_name") or "").strip()
        detected = detect_app(site_p, app_p)

        logger.info(f"[PHOTO] OCR mac={mac_found} key={key_found} site={site_p} app={app_p} -> backend={detected}")

        # ------------------------------------------------------------------
        # Nada legivel na foto
        # ------------------------------------------------------------------
        if not mac_found:
            await status_msg.edit_text(
                "⚠️ *Não consegui identificar os códigos nessa foto.*\n\n"
                "Para a leitura automática funcionar:\n"
                "• Tire o **print direto da tela da TV** (ou uma foto bem reta e nítida);\n"
                "• Evite fotografar a tela do celular;\n"
                "• Ou simplesmente *digite* os códigos aqui no chat no formato:\n"
                "`a1:b2:c3:d4:e5:f6 123456`",
                parse_mode="Markdown"
            )
            return

        # ------------------------------------------------------------------
        # App de credito pre-pago: sem injecao possivel
        # ------------------------------------------------------------------
        if detected == "ibopro":
            AWAITING_TV_CODES[user.id] = {"m3u_url": m3u_url, "mode": "ibo_pro"}
            await status_msg.edit_text(
                "📺 *Identifiquei a tela do aplicativo IBO PRO TV.*\n\n"
                f"• MAC da sua TV: `{mac_found}`\n\n"
                "⚠️ *Atenção:* esse aplicativo (IBO PRO TV) *não* usa o sistema de "
                "Device ID + Device Key. Ele exige que você crie um *código de ativação* "
                "no site `ibotv.pro` antes de aceitar qualquer lista de canais.\n\n"
                "✅ *Solução mais rápida (funciona agora, sem custo):* use um player que aceita "
                "a lista direto. Vou te mandar o passo a passo do app correto.\n\n"
                "Escolha abaixo:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📱 Ver app correto + link da lista", callback_data="how_to_install")],
                    [InlineKeyboardButton("🎬 Tentar outro aplicativo", callback_data="auto_activate_tv")]
                ]),
                parse_mode="Markdown"
            )
            return

        # ------------------------------------------------------------------
        # Apps que exigem Device Key: se a foto nao mostrou, pede o numero
        # ------------------------------------------------------------------
        if detected in ("funplays", "ibo") and not key_found:
            AWAITING_TV_CODES[user.id] = {"m3u_url": m3u_url, "mode": "manual", "mac_pending": mac_found,
                                          "app": detected, "site": detected}
            label = APP_NAMES.get(detected, "seu aplicativo")
            await status_msg.edit_text(
                f"🔍 *Encontrei o MAC da sua TV ({label}), mas falta a Chave.*\n\n"
                f"• MAC: `{mac_found}`\n\n"
                "Envie a *Chave do dispositivo* (o código que aparece perto do MAC, "
                "ex: \"Chave do dispositivo: 668267\") apenas com os números.\n\n"
                "💡 *Dica:* tire o print direto da tela da TV (não fotografe a tela do celular), "
                "que a leitura fica perfeita.",
                parse_mode="Markdown"
            )
            return

        # ------------------------------------------------------------------
        # Ativacao automatica
        # ------------------------------------------------------------------
        if detected in ("funplays", "ibo"):
            resumo = (f"✅ *Dados Identificados na sua TV:*\n"
                      f"• Device ID: `{mac_found}`\n"
                      f"• Device Key: `{key_found}`\n\n")
        else:
            resumo = (f"✅ *Dados Identificados na sua TV:*\n"
                      f"• Device ID: `{mac_found}`\n\n")

        await status_msg.edit_text(
            resumo + "⏳ *Injetando os canais na sua Smart TV...* aguarde de 10 a 40 segundos.",
            parse_mode="Markdown"
        )

        res = activate_tv(
            mac=mac_found,
            key=key_found,
            playlist_url=m3u_url,
            site=site_p,
            app_name=app_p,
            playlist_name="Nexus PlayTV VIP",
        )

        if res.get("success"):
            AWAITING_TV_CODES.pop(user.id, None)
            app_label = res.get("app_label") or "Smart TV"
            try:
                alert_playtv_sale(
                    plan_name=f"Ativação Smart TV ({app_label})",
                    amount_str="Automática (Visão IA)",
                    method=app_label.upper(),
                    customer_info=f"@{user.username or 'SemUser'} (MAC {mac_found})",
                    order_id=f"TV_{int(time.time())}"
                )
            except Exception as e_tv:
                logger.error(f"Erro alerta TV: {e_tv}")

            await status_msg.edit_text(
                "🎉 *SUA SMART TV FOI ATIVADA COM SUCESSO!*\n\n"
                f"✅ Aplicativo: *{app_label}*\n"
                "✅ A lista completa de canais, filmes e séries já está gravada na TV.\n\n"
                "📺 *Como assistir agora:*\n"
                "1. Saia da tela de configurações do aplicativo na TV;\n"
                "2. Selecione a lista *Nexus PlayTV VIP*;\n"
                "3. Se não aparecer, pressione *Reload / Recarregar* no app.\n\n"
                "Bom divertimento! 🍿⚽",
                parse_mode="Markdown"
            )
        else:
            err = res.get("message") or "Erro desconhecido"
            await status_msg.edit_text(
                f"❌ *Não foi possível ativar sua TV automaticamente:*\n`{err}`\n\n"
                "Confira se os códigos na tela estão corretos e envie novamente no formato:\n"
                "`a1:b2:c3:d4:e5:f6 123456`\n\n"
                "Se preferir, nosso suporte finaliza a ativação manualmente em segundos.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 Falar com o Suporte", callback_data="support_faq")],
                    [InlineKeyboardButton("⬅️ Menu Inicial", callback_data="main_menu")]
                ]),
                parse_mode="Markdown"
            )

    except Exception as e:
        logger.error(f"Erro photo_handler: {e}", exc_info=True)
        try:
            await status_msg.edit_text(
                "⚠️ *Não consegui concluir a ativação automática agora.*\n\n"
                "Envie os códigos digitados aqui no chat no formato:\n"
                "`a1:b2:c3:d4:e5:f6 123456`\n\n"
                "Ou acione o suporte que resolvemos na hora.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 Suporte", callback_data="support_faq")]
                ]),
                parse_mode="Markdown"
            )
        except Exception:
            pass


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Error handler global: registra a exceção e avisa o usuário sem deixá-lo no vácuo."""
    logger.error("Exceção não tratada no PlayTV bot:", exc_info=context.error)
    try:
        if isinstance(update, Update) and getattr(update, "effective_chat", None):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=(
                    "⚠️ Ocorreu um erro inesperado ao processar sua solicitação.\n"
                    "Nossa equipe foi notificada — tente novamente em instantes ou acione o suporte."
                ),
            )
    except Exception as e:
        logger.error(f"Falha ao notificar usuário sobre erro: {e}")

def main():
    import socket
    # Trava de instância única para impedir processos duplicados / 409 Conflict
    try:
        lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        lock_socket.bind('\0nexus_playtv_bot_lock')
    except Exception:
        print("Outra instância do run_playtv.py já está em execução. Encerrando.")
        sys.exit(0)

    init_db()
    print("Bot Nexus PlayTV Store inicializado...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Configurar JobQueue periódico para follow-up de conversão
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(push_trial_reminders, interval=60, first=10)

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("cupom", coupon_admin_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_error_handler(error_handler)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
