import os
import json
import logging
import uuid
import sqlite3
import io
import qrcode
from datetime import datetime, timedelta
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from db import init_db, DB_PATH
from services import (
    create_pixget_charge,
    convert_usd_to_crypto,
    get_network_fee_estimate,
    create_blockbee_payment,
    generate_iptv_access
)
from notifier import alert_playtv_sale, alert_playtv_trial
from ibo_injector import activate_smart_tv_ibo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nexus_playtv")

BOT_TOKEN = os.getenv("PLAYTV_BOT_TOKEN", "")

with open("/opt/data/nexus_playtv_bot/products_playtv.json") as f:
    PRODUCTS = json.load(f)

AWAITING_CPF = {}
AWAITING_TV_CODES = {} # user_id -> {'order_id': order_id, 'm3u_url': url}

def get_main_keyboard():
    return [
        [InlineKeyboardButton("📺 Planos & Assinaturas", callback_data="view_plans")],
        [InlineKeyboardButton("⚡ Gerar Teste Grátis (4 Horas)", callback_data="free_trial")],
        [
            InlineKeyboardButton("📱 Como Instalar (Apps)", callback_data="how_to_install"),
            InlineKeyboardButton("❓ Dúvidas & Suporte", callback_data="support_faq")
        ],
        [InlineKeyboardButton("📦 Minha Assinatura / Acesso", callback_data="my_access")]
    ]

def get_reply_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📺 Planos"), KeyboardButton("⚡ Teste Grátis (4h)")],
            [KeyboardButton("📱 Como Instalar"), KeyboardButton("❓ Suporte")]
        ],
        resize_keyboard=True
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
              (user.id, user.username or "", user.first_name or ""))
    conn.commit()
    conn.close()

    text = (
        f"⚡ *Olá, {user.first_name}! Bem-vindo ao Nexus PlayTV.*\n\n"
        "Sua central definitiva de entretenimento, esportes ao vivo e streaming em alta definição.\n\n"
        "🛡️ *Diferenciais Exclusivos:*\n"
        "• *+25.000 Canais Ao Vivo:* Futebol (Premiere, Libertadores), Combate, Filmes, Infantis e Internacionais.\n"
        "• *+120.000 Filmes e Séries:* Todos os streamings em um só lugar (atualizações diárias).\n"
        "• *Tecnologia P2P Anti-Travamento:* Servidores com CDN híbrida imune a bloqueios de operadoras.\n"
        "• *Qualidade Máxima:* Transmissões em SD, HD, Full HD e 4K HDR.\n\n"
        "👇 *Escolha uma opção abaixo para começar:*"
    )
    
    banner_path = "/opt/data/nexus_playtv_bot/assets/nexus_playtv_banner.png"
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
    await update.message.reply_text("Navegue pelo menu rápido abaixo:", reply_markup=get_reply_keyboard())

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
        await safe_edit(text, reply_markup=InlineKeyboardMarkup(get_main_keyboard()))
        return

    if data == "view_plans":
        text = (
            "📺 *Planos & Assinaturas Nexus PlayTV*\n\n"
            "Sem contratos, sem fidelidade e com liberação automática 24/7.\n"
            "Todos os planos incluem todos os canais + filmes + séries em 4K.\n\n"
            "Selecione o plano desejado:"
        )
        keyboard = [
            [InlineKeyboardButton("⚽ Pass 3 Jogos (4h cada) - R$ 14,90", callback_data="prod_pack_3_games")],
            [InlineKeyboardButton("📺 Mensal (1 Tela) - R$ 34,90", callback_data="prod_monthly_1screen")],
            [InlineKeyboardButton("🔥 Trimestral (1 Tela) - R$ 89,90", callback_data="prod_quarterly_1screen")],
            [InlineKeyboardButton("⭐ Semestral (1 Tela) - R$ 149,90", callback_data="prod_semiannual_1screen")],
            [InlineKeyboardButton("👑 Anual Família VIP (2 Telas) - R$ 249,90", callback_data="prod_annual_family_2screens")],
            [InlineKeyboardButton("⬅️ Voltar ao Menu", callback_data="main_menu")]
        ]
        await safe_edit(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "redeem_game_pass":
        # Ativar 1 passe de jogo do saldo do usuário
        conn = sqlite3.connect(DB_PATH)
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
        
        # Gerar o acesso de 4 horas
        cred = generate_iptv_access(is_trial=True) # 4 horas ilimitadas
        redemption_id = f"PASS_{user.id}_{int(time.time())}"
        
        c.execute("""
        INSERT INTO pass_redemptions (user_id, pass_id, username, password, m3u_url, expires_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (user.id, pass_id, cred["username"], cred["password"], cred["m3u_url"], cred["expires_at"]))
        
        c.execute("""
        INSERT OR REPLACE INTO orders (order_id, user_id, username, product_id, status, delivered_credentials, m3u_url, expires_at)
        VALUES (?, ?, ?, 'Pass Jogo (4h)', 'paid', ?, ?, ?)
        """, (redemption_id, user.id, user.username or "", f"Usuário: {cred['username']} | Senha: {cred['password']} | Servidor: {cred['server_url']}", cred["m3u_url"], cred["expires_at"]))

        conn.commit()
        conn.close()

        vip_page_url = f"https://nexus.pixget.io/vip/{redemption_id}"
        web_player_url = f"https://player.nexusplay.tv/?user={cred['username']}&pass={cred['password']}"

        text = (
            "🎉 *SEU ACESSO DE JOGO (4 HORAS) FOI ATIVADO!*\n\n"
            f"⚽ *Saldo restante de passes:* {new_remaining} de 3\n"
            f"⏳ *Válido até:* {cred['expires_at']}\n\n"
            "Todos os canais Premiere, TNT Sports, Libertadores e ESPN em 4K já estão liberados.\n\n"
            "📱 *Como assistir:*\n"
            "• Toque no botão abaixo para abrir seu Cartão VIP em 1 clique;\n"
            "• Ou vá em *Passo a Passo Smart TV* para ativar sua TV Samsung/LG sem digitar nada!"
        )
        keyboard = [
            [InlineKeyboardButton("✨ ABRIR CARTÃO VIP INTERATIVO", url=vip_page_url)],
            [InlineKeyboardButton("▶️ Assistir Agora no Navegador", url=web_player_url)],
            [InlineKeyboardButton("📱 Ativar na Smart TV", callback_data="auto_activate_tv")],
            [InlineKeyboardButton("⬅️ Menu Principal", callback_data="main_menu")]
        ]
        await safe_edit(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "free_trial":
        conn = sqlite3.connect(DB_PATH)
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
                [InlineKeyboardButton("📺 Assinar Agora (a partir de R$ 34,90)", callback_data="view_plans")],
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
        web_player_url = f"https://player.nexusplay.tv/?user={cred['username']}&pass={cred['password']}"

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
        pdf_path = "/opt/data/nexus_playtv_bot/assets/manual_vip_exemplo.pdf"
        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f_pdf:
                await query.message.reply_document(
                    document=f_pdf,
                    filename="Guia_VIP_Nexus_PlayTV.pdf",
                    caption="📄 *Guia VIP Nexus PlayTV:* Passo a passo completo para Samsung, LG, Firestick e Celular.",
                    parse_mode="Markdown"
                )
        else:
            await query.answer("Gerando guia...", show_alert=True)
        return

    if data.startswith("inst_"):
        device = data.replace("inst_", "")
        instructions = {
            "samsung": (
                "📺 *Instalação na Smart TV Samsung (Tizen):*\n\n"
                "✨ *Você NÃO precisa digitar senhas ou links na TV!*\n\n"
                "1. Abra a loja de aplicativos da sua TV Samsung;\n"
                "2. Pesquise e baixe o aplicativo **IBO Player**;\n"
                "3. Abra o IBO Player na sua TV;\n"
                "4. Clique no botão abaixo para **tirar uma foto da tela** ou digitar os códigos.\n\n"
                "👇 O robô injeta os canais na sua TV na hora:"
            ),
            "lg": (
                "📺 *Instalação na Smart TV LG (webOS):*\n\n"
                "✨ *Você NÃO precisa digitar senhas ou links na TV!*\n\n"
                "1. Abra a LG Content Store na sua TV;\n"
                "2. Pesquise e baixe o aplicativo **IBO Player**;\n"
                "3. Abra o IBO Player na sua TV;\n"
                "4. Clique no botão abaixo para **tirar uma foto da tela** ou digitar os códigos.\n\n"
                "👇 O robô injeta os canais na sua TV na hora:"
            ),
            "android": (
                "🔥 *Instalação no Fire TV Stick:*\n\n"
                "✨ *Escolha como prefere instalar:*\n\n"
                "1️⃣ *Opção 1 (Aplicativo Oficial New Hybrid - Mais estável):*\n"
                "• Abra o app **Downloader** na sua TV e digite o código: **`1941290`**\n"
                "• Ou se usar o app **NtDown**, use o código: **`73783`**\n\n"
                "2️⃣ *Opção 2 (Central V3 / DreamTV):*\n"
                "• No app Downloader, digite: **`9007131`** (Central V3) ou **`8627648`** (DreamTV)\n\n"
                "3️⃣ *Opção 3 (Ativação Automática via IBO Player):*\n"
                "• Baixe o **IBO Player**, abra e clique no botão abaixo para o robô injetar os canais na sua TV!"
            ),
            "androidtv": (
                "📱 *Instalação no Android TV / TV Box / Google TV:*\n\n"
                "✨ *Aplicativos Oficiais Recomendados:*\n\n"
                "1️⃣ *New Hybrid P2P (Recomendado):*\n"
                "• No app **Downloader**, digite o código: **`1941290`** (ou NtDown: **`73783`**)\n\n"
                "2️⃣ *FiveTV PRO / Central V3:*\n"
                "• Downloader: **`7877135`** (FiveTV) | **`9007131`** (Central V3)\n\n"
                "3️⃣ *Ativação Automática IBO Player:*\n"
                "• Baixe o **IBO Player** na Google Play Store e clique no botão abaixo!"
            ),
            "roku": (
                "🔵 *Instalação na Roku TV (AOC, Philco, TCL Roku, Semp):*\n\n"
                "✨ *Ativação Automática disponível — sem digitar na TV!*\n\n"
                "1. Na tela inicial da Roku, vá em **Streaming Channels**;\n"
                "2. Pesquise e adicione o canal **IBO Player**;\n"
                "3. Abra o app e anote o **Device ID** e o **Device Key** da tela:"
            ),
            "appletv": (
                "🍏 *Instalação no Apple TV:*\n\n"
                "✨ *Ativação Automática disponível — sem digitar na TV!*\n\n"
                "1. Abra a App Store do Apple TV;\n"
                "2. Baixe o **IBO Player**;\n"
                "3. Abra o app e anote o **Device ID** e o **Device Key**:"
            ),
            "mobile": (
                "📲 *Instalação no Celular / Tablet (Android ou iPhone):*\n\n"
                "1️⃣ *Android:* Baixe o app direto em **`abrela.me/ftvpro`** (FiveTV) ou pesquise por **IBO Player** na Google Play Store.\n"
                "2️⃣ *iPhone/iPad:* Baixe o **Smarters Player Lite** ou **Stream Player - ISP** na App Store e use os dados do seu Cartão VIP!\n"
                "3️⃣ *WebPlayer:* Se preferir, assista direto pelo navegador sem instalar nada."
            ),
            "apple": (
                "🍏 *Instalação no iPhone, iPad ou Apple TV:*\n\n"
                "1. Abra a App Store;\n"
                "2. Baixe o **Smarters Player Lite** ou **Stream Player - ISP**;\n"
                "3. Selecione login com API Xtream Codes:\n"
                "   • Servidor: `http://man77.work`\n"
                "   • Use o Usuário e Senha do seu Cartão VIP!"
            ),
            "pc": (
                "💻 *Instalação no Computador (Windows / Mac):*\n\n"
                "1️⃣ *Navegador (Zero Instalação):* Abra o WebPlayer em 1 clique direto no seu Cartão VIP;\n"
                "2️⃣ *App Windows:* Baixe o app oficial pelo código Downloader: **`9351066`** (Smarters 32bits) ou instale o Purple IPTV."
            )
        }
        text = instructions.get(device, "Instruções disponíveis no suporte.")
        
        # Ativação automática via 2Captcha — todos os Apps IBO Player (Device ID + Key)
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
        # Checar se usuário tem acesso ativo (ordem paga ou teste gratis)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
        SELECT delivered_item, m3u_url FROM orders 
        WHERE user_id = ? AND status = 'paid' ORDER BY id DESC LIMIT 1
        """, (user.id,))
        order_row = c.fetchone()
        
        m3u = None
        if order_row and order_row[1]:
            m3u = order_row[1]
        else:
            # Checar trial
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
            "📸 *FORMA 1 (Mais fácil):* Tire uma foto da tela da sua TV mostrando o app IBO Player aberto e envie aqui no chat!\n\n"
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
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT order_id, product_id, delivered_credentials, created_at FROM orders WHERE user_id = ? AND status = 'paid' ORDER BY created_at DESC LIMIT 3", (user.id,))
        orders = c.fetchall()
        conn.close()

        if not orders:
            text = (
                "📦 *Você ainda não possui assinaturas ativas!*\n\n"
                "Adquira um dos nossos planos ou gere um teste grátis de 4 horas para conhecer a qualidade dos canais."
            )
            keyboard = [
                [InlineKeyboardButton("⚡ Gerar Teste Grátis (4h)", callback_data="free_trial")],
                [InlineKeyboardButton("📺 Ver Planos", callback_data="view_plans")],
                [InlineKeyboardButton("⬅️ Voltar ao Menu", callback_data="main_menu")]
            ]
        else:
            text = "📦 *Suas Assinaturas e Acessos Recentes:*\n\n"
            for o in orders:
                pid, cred, date = o[1], o[2], o[3]
                pname = PRODUCTS.get(pid, {}).get("name", pid)
                text += f"📺 *{pname}*\n📅 Ativação: {date}\n🔑 Credenciais: `{cred}`\n\n"
            keyboard = [[InlineKeyboardButton("⬅️ Voltar ao Menu", callback_data="main_menu")]]

        await safe_edit(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("prod_"):
        pid = data.replace("prod_", "")
        p = PRODUCTS.get(pid)
        if not p:
            await query.message.reply_text("Plano indisponível.")
            return

        # Modal de Upsell inteligente para planos de 1 tela
        UPGRADE_MAP = {
            "monthly_1screen": {
                "upgrade_pid": "monthly_2screens",
                "upgrade_price": "49,90",
                "diff": "15,00",
                "period": "mês"
            },
            "quarterly_1screen": {
                "upgrade_pid": "quarterly_2screens",
                "upgrade_price": "129,80",
                "diff": "39,90",
                "period": "trimestre"
            },
            "semiannual_1screen": {
                "upgrade_pid": "semiannual_2screens",
                "upgrade_price": "219,80",
                "diff": "69,90",
                "period": "semestre"
            }
        }

        if pid in UPGRADE_MAP and not data.startswith("prod_direct_"):
            up = UPGRADE_MAP[pid]
            upsell_text = (
                f"📺 *{p['name']}*\n\n"
                "⚠️ *ATENÇÃO: Este plano permite apenas 1 TV ligada por vez.*\n"
                "Se alguém ligar a TV do quarto enquanto você assiste na sala, o sinal vai pausar.\n\n"
                "🔥 *OFERTA VIP DE CHECKOUT (OPCIONAL):*\n"
                f"Adicione uma **2ª Tela Oficial Simultânea** para sua casa (Sala + Quarto ou Celular) por apenas **+R$ {up['diff']}**!\n\n"
                f"• De ~R$ 69,80~ por apenas **R$ {up['upgrade_price']}** por {up['period']}.\n\n"
                "👇 Deseja aproveitar e liberar 2 telas agora?"
            )
            upsell_kb = [
                [InlineKeyboardButton(f"👑 SIM! Quero 2 Telas (R$ {up['upgrade_price']})", callback_data=f"prod_direct_{up['upgrade_pid']}")],
                [InlineKeyboardButton(f"➡️ Não, continuar com 1 Tela (R$ {p['price_brl']:.2f})", callback_data=f"prod_direct_{pid}")],
                [InlineKeyboardButton("⬅️ Voltar aos Planos", callback_data="view_plans")]
            ]
            await safe_edit(upsell_text, reply_markup=InlineKeyboardMarkup(upsell_kb))
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

            conn = sqlite3.connect(DB_PATH)
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
                f"💵 *Total:* `${total_usd:.2f} USD*\n"
                f"🪙 *Moeda/Rede:* `{coin_label}`\n\n"
                f"👇 *Envie exatamente a quantidade abaixo:*\n"
                f"```\n{display_qty}\n```\n\n"
                f"📍 *Endereço da Carteira para Depósito:*\n"
                f"`{address}`\n\n"
                f"⚡ *Aprovação Automática:* O servidor identifica a transação na blockchain e entrega suas credenciais na hora sem necessidade de enviar comprovante.\n"
                f"⏳ *Validade da fatura:* 15 minutos."
            )

            keyboard = [
                [InlineKeyboardButton("📋 Copiar Endereço", callback_data=f"copy_addr_{order_id}")],
                [InlineKeyboardButton("🔄 Já paguei (Checar Status)", callback_data=f"check_order_{order_id}")],
                [InlineKeyboardButton("⬅️ Cancelar e Voltar", callback_data="main_menu")]
            ]

            if qr_url:
                try:
                    await query.message.reply_photo(photo=qr_url, caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
                    return
                except Exception:
                    pass

            await safe_edit(text, reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            logger.error(f"Erro BlockBee: {e}")
            await safe_edit(f"❌ Erro ao gerar pagamento cripto: {e}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Voltar", callback_data="main_menu")]]))
        return

    if data.startswith("copy_"):
        parts = data.split("_")
        action = parts[1]
        order_id = "_".join(parts[2:])

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT delivered_credentials FROM orders WHERE order_id = ?", (order_id,))
        row = c.fetchone()
        conn.close()

        val = ""
        if row and row[0]:
            # formato: Usuário: xxx | Senha: yyy | Servidor: zzz
            cred_str = row[0]
            for part in cred_str.split("|"):
                if action == "dns" and "Servidor:" in part:
                    val = part.split("Servidor:")[1].strip()
                elif action == "user" and "Usuário:" in part:
                    val = part.split("Usuário:")[1].strip()
                elif action == "pass" and "Senha:" in part:
                    val = part.split("Senha:")[1].strip()

        if val:
            await query.answer(f"Copiado: {val}", show_alert=True)
            await query.message.reply_text(f"📋 *{action.upper()}:*\n`{val}`\n*(Toque no texto para copiar)*", parse_mode="Markdown")
        else:
            await query.answer("Código copiado para a área de transferência!", show_alert=True)
        return

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg_text = update.message.text.strip()

    if msg_text == "📺 Planos":
        await update.message.reply_text("Escolha o plano:", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⚽ Pass 3 Jogos (4h cada) - R$ 14,90", callback_data="prod_pack_3_games")],
            [InlineKeyboardButton("📺 Mensal (1 Tela) - R$ 34,90", callback_data="prod_monthly_1screen")],
            [InlineKeyboardButton("🔥 Trimestral (1 Tela) - R$ 89,90", callback_data="prod_quarterly_1screen")],
            [InlineKeyboardButton("⭐ Semestral (1 Tela) - R$ 149,90", callback_data="prod_semiannual_1screen")],
            [InlineKeyboardButton("👑 Anual Família VIP (2 Telas) - R$ 249,90", callback_data="prod_annual_family_2screens")],
            [InlineKeyboardButton("⬅️ Menu", callback_data="main_menu")]
        ]))
        return
    elif msg_text == "⚡ Teste Grátis (4h)":
        update.callback_query = None
        # Dispara logica de teste gratis
        await update.message.reply_text("Gerando teste...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Confirmar Teste Grátis", callback_data="free_trial")]]))
        return
    elif msg_text == "📱 Como Instalar":
        await update.message.reply_text("Selecione o seu aparelho:", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Smart TV Samsung", callback_data="inst_samsung"), InlineKeyboardButton("Smart TV LG", callback_data="inst_lg")],
            [InlineKeyboardButton("TV Box / Firestick", callback_data="inst_android"), InlineKeyboardButton("iPhone / Apple TV", callback_data="inst_apple")],
            [InlineKeyboardButton("Computador", callback_data="inst_pc")]
        ]))
        return
    elif msg_text == "❓ Suporte":
        await update.message.reply_text("Precisa de ajuda com o PlayTV?", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Ver Dúvidas Frequentes", callback_data="support_faq")]]))
        return

    # Tratamento de Ativação Automática de Smart TV Samsung / LG via 2Captcha
    if user.id in AWAITING_TV_CODES:
        session = AWAITING_TV_CODES[user.id]
        parts = [p.strip() for p in msg_text.replace("\n", " ").replace(",", " ").split() if p.strip()]
        if len(parts) < 2:
            await update.message.reply_text(
                "⚠️ *Formato incorreto!*\n\n"
                "Por favor, envie o **Device ID** e o **Device Key** separados por espaço.\n"
                "Exemplo:\n`a1:b2:c3:d4:e5:f6 123456`",
                parse_mode="Markdown"
            )
            return

        mac_in = parts[0]
        key_in = parts[1]
        m3u_url = session.get("m3u_url")

        status_msg = await update.message.reply_text(
            "⏳ *Conectando à sua Smart TV e resolvendo autenticação...*\n"
            "Aguarde cerca de 5 a 8 segundos. Não feche o aplicativo na TV...",
            parse_mode="Markdown"
        )

        res = activate_smart_tv_ibo(
            mac_address=mac_in,
            device_key=key_in,
            playlist_name="Nexus PlayTV Oficial",
            playlist_url=m3u_url
        )

        if res.get("success"):
            AWAITING_TV_CODES.pop(user.id, None)
            await status_msg.edit_text(
                "🎉 *SUA SMART TV FOI ATIVADA COM SUCESSO!*\n\n"
                "✅ A lista completa de canais, filmes e jogos já está sincronizada.\n\n"
                "📺 *Como assistir agora:*\n"
                "1. Vá até a sua TV;\n"
                "2. Pressione a tecla de **Reload / Recarregar** (ou o botão vermelho do controle);\n"
                "3. Pronto! A grade completa do Nexus PlayTV já está na sua tela.\n\n"
                "Bom divertimento! 🍿⚽",
                parse_mode="Markdown"
            )
        else:
            await status_msg.edit_text(
                f"❌ *Não foi possível ativar sua TV:*\n`{res.get('message')}`\n\n"
                "Verifique se digitou o Device ID e Device Key exatamente como aparecem na tela do IBO Player e tente enviar novamente:",
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

            conn = sqlite3.connect(DB_PATH)
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
            await update.message.reply_text(f"❌ Erro ao gerar PIX: {e}")
        return

async def push_trial_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Job periódico (executado a cada 1 minuto) para engajamento e conversão de testes"""
    try:
        conn = sqlite3.connect(DB_PATH)
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
                exp_dt = datetime.strptime(exp_str, "%Y-%m-%d %H:%M:%S")
                # Se faltam menos de 35 minutos para expirar e ainda não expirou
                if timedelta(seconds=0) < (exp_dt - now) <= timedelta(minutes=35):
                    text_alert = (
                        "⚠️ *SEU TESTE GRÁTIS EXPIRA EM MENOS DE 30 MINUTOS!*\n\n"
                        "Não deixe o sinal cortar no meio da programação!\n\n"
                        "💡 *Assine agora mesmo para continuar assistindo sem interrupções:*\n"
                        "• 📺 *Plano Mensal (30 dias):* apenas R$ 34,90\n"
                        "• 🔥 *Trimestral (com desconto):* apenas R$ 89,90\n\n"
                        "⚡ Liberação imediata no PIX ou Cripto:"
                    )
                    kb = [
                        [InlineKeyboardButton("📺 Assinar Plano Mensal (R$ 34,90)", callback_data="prod_monthly_1screen")],
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
                exp_dt = datetime.strptime(exp_str, "%Y-%m-%d %H:%M:%S")
                if now >= exp_dt:
                    text_expired = (
                        "🔒 *SEU SINAL DE TESTE FOI ENCERRADO!*\n\n"
                        "Gostou da estabilidade e qualidade 4K dos nossos canais?\n\n"
                        "Ative agora sua assinatura definitiva em menos de 1 minuto sem contratos nem fidelidade:\n\n"
                        "• 📺 *Plano Mensal (30 dias):* R$ 34,90\n"
                        "• 🔥 *Trimestral (com desconto):* R$ 89,90\n"
                        "• 👑 *Anual Família (2 Telas):* R$ 249,90"
                    )
                    kb = [
                        [InlineKeyboardButton("📺 Assinar Plano Mensal (R$ 34,90)", callback_data="prod_monthly_1screen")],
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

        # 3. Alertas de Vencimento de Assinaturas Pagas (3 dias, 1 dia, corte)
        c.execute("""
            SELECT order_id, user_id, product_id, expires_at, reminded_3d, reminded_1d, reminded_expired
            FROM orders
            WHERE status = 'paid' AND expires_at IS NOT NULL AND reminded_expired = 0
        """)
        paid_orders = c.fetchall()

        for oid, uid, pid, exp_str, r3d, r1d, rexp in paid_orders:
            try:
                exp_dt = datetime.strptime(exp_str, "%Y-%m-%d %H:%M:%S")
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

        conn = sqlite3.connect(DB_PATH)
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
        conn = sqlite3.connect(DB_PATH)
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
    """Lê a foto da tela da Smart TV enviada pelo usuário, extrai Device ID e Key via OCR e ativa automaticamente"""
    user = update.effective_user
    if user.id not in AWAITING_TV_CODES:
        await update.message.reply_text(
            "📸 Recebi sua foto! Se deseja ativar uma Smart TV automaticamente, vá em **📱 Como Instalar** e clique em **🚀 Ativar Minha TV** primeiro."
        )
        return

    session = AWAITING_TV_CODES[user.id]
    m3u_url = session.get("m3u_url")

    status_msg = await update.message.reply_text(
        "🔍 *Analisando a foto da sua TV com Inteligência Artificial...*\n"
        "Lendo o **Device ID** e o **Device Key** na tela. Aguarde alguns segundos...",
        parse_mode="Markdown"
    )

    try:
        # Baixar a foto enviada pelo usuário
        photo = update.message.photo[-1]
        file_obj = await context.bot.get_file(photo.file_id)
        local_img = f"/tmp/tv_screen_{user.id}_{int(time.time())}.jpg"
        await file_obj.download_to_drive(local_img)

        # Usar PyMuPDF / Tesseract ou regex de imagem para extrair MAC e Key
        import re, subprocess
        mac_found = None
        key_found = None

        # Tentar extrair texto via OCR tesseract se disponível, ou regex simples de strings
        try:
            cmd = ["tesseract", local_img, "stdout", "--oem", "1", "-l", "eng"]
            ocr_text = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8")
        except Exception:
            # Fallback usando strings do arquivo ou inspeção rápida
            ocr_text = ""

        # Procurar formato MAC (ex: aa:bb:cc:dd:ee:ff ou aabbccddeeff)
        mac_match = re.search(r'([0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2})', ocr_text)
        if mac_match:
            mac_found = mac_match.group(1).lower()

        # Procurar Device Key (normalmente 4 a 8 dígitos/letras)
        key_match = re.search(r'(?:key|senha|device\s*key)[\s:]*([0-9a-zA-Z]{4,8})', ocr_text, re.I)
        if key_match:
            key_found = key_match.group(1)
        else:
            # Pegar sequências numéricas de 6 dígitos comuns no IBO Player
            digits_matches = re.findall(r'\b([0-9]{5,7})\b', ocr_text)
            if digits_matches:
                key_found = digits_matches[0]

        if not mac_found or not key_found:
            await status_msg.edit_text(
                "⚠️ *Não consegui ler todos os dados com clareza da foto.*\n\n"
                "Por favor, certifique-se de que a foto está nítida ou digite os códigos no chat:\n"
                "Exemplo: `a1:b2:c3:d4:e5:f6 123456`",
                parse_mode="Markdown"
            )
            return

        await status_msg.edit_text(
            f"✅ *Dados Identificados na sua TV:*\n"
            f"• Device ID: `{mac_found}`\n"
            f"• Device Key: `{key_found}`\n\n"
            "⏳ *Injetando canais na sua Smart TV via 2Captcha...*",
            parse_mode="Markdown"
        )

        res = activate_smart_tv_ibo(
            mac_address=mac_found,
            device_key=key_found,
            playlist_name="Nexus PlayTV Oficial",
            playlist_url=m3u_url
        )

        if res.get("success"):
            AWAITING_TV_CODES.pop(user.id, None)
            await status_msg.edit_text(
                "🎉 *SUA SMART TV FOI ATIVADA COM SUCESSO!*\n\n"
                "✅ A lista completa de canais, filmes e jogos já está sincronizada.\n\n"
                "📺 *Como assistir agora:*\n"
                "1. Vá até a sua TV;\n"
                "2. Pressione a tecla de **Reload / Recarregar** (ou o botão vermelho do controle);\n"
                "3. Pronto! A grade completa do Nexus PlayTV já está na sua tela.\n\n"
                "Bom divertimento! 🍿⚽",
                parse_mode="Markdown"
            )
        else:
            await status_msg.edit_text(
                f"❌ *Não foi possível ativar sua TV:*\n`{res.get('message')}`\n\n"
                "Verifique os códigos na tela e tente novamente digitando no formato:\n"
                "`a1:b2:c3:d4:e5:f6 123456`",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Erro photo_handler: {e}")
        await status_msg.edit_text("Erro ao processar a imagem. Por favor, envie os códigos digitados no chat.")

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
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
