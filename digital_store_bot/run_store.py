import os
import json
import logging
import uuid
import sqlite3
import requests
import io
import qrcode
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
from services import create_cryptobot_invoice, create_pixget_invoice, create_blockbee_payment, get_network_fee_estimate, convert_usd_to_crypto
from i18n import t

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

with open("/opt/data/digital_store_bot/products.json") as f:
    products = json.load(f)

USER_LANG = {}
AWAITING_CPF = {}

def get_user_lang(user_id: int, user_obj=None) -> str:
    if user_id in USER_LANG:
        return USER_LANG[user_id]
    if user_obj and user_obj.language_code:
        code = user_obj.language_code.lower()
        if code.startswith("es"):
            USER_LANG[user_id] = "es"
            return "es"
        elif code.startswith("en"):
            USER_LANG[user_id] = "en"
            return "en"
    USER_LANG[user_id] = "pt"
    return "pt"

def get_persistent_keyboard(lang: str):
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(t(lang, "btn_catalog")), KeyboardButton(t(lang, "btn_help"))],
            [KeyboardButton(t(lang, "btn_lang"))]
        ],
        resize_keyboard=True,
        is_persistent=True
    )

def get_main_menu_keyboard(lang: str):
    return [
        [InlineKeyboardButton(t(lang, "btn_prod_gemini"), callback_data="prod_gemini_18m")],
        [
            InlineKeyboardButton(t(lang, "btn_prod_capcut"), callback_data="prod_capcut_pro_30d"),
            InlineKeyboardButton(t(lang, "btn_prod_canva"), callback_data="prod_canva_pro_12m")
        ],
        [
            InlineKeyboardButton(t(lang, "btn_prod_tg_premium"), callback_data="prod_telegram_premium_3m"),
            InlineKeyboardButton(t(lang, "btn_prod_discord"), callback_data="prod_discord_nitro_3m")
        ],
        [
            InlineKeyboardButton(t(lang, "btn_faq"), callback_data="faq"),
            InlineKeyboardButton("🌐 Idioma / Language", callback_data="choose_lang")
        ]
    ]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = get_user_lang(user.id, user)
    text = t(lang, "welcome", name=user.first_name)
    
    await update.message.reply_text(
        "⚡ Nexus Tools Menu:",
        reply_markup=get_persistent_keyboard(lang)
    )
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(get_main_menu_keyboard(lang)),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user
    lang = get_user_lang(user.id, user)

    async def safe_edit(text, reply_markup=None, parse_mode="Markdown"):
        try:
            if query.message.photo:
                await query.message.edit_caption(caption=text, reply_markup=reply_markup, parse_mode=parse_mode)
            else:
                await query.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception:
            await query.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)

    if data == "choose_lang":
        text = "🌐 *Escolha o seu idioma / Select your language / Elige tu idioma:*"
        keyboard = [
            [InlineKeyboardButton("🇧🇷 Português", callback_data="set_lang_pt")],
            [InlineKeyboardButton("🇺🇸 English", callback_data="set_lang_en")],
            [InlineKeyboardButton("🇪🇸 Español", callback_data="set_lang_es")],
            [InlineKeyboardButton(t(lang, "btn_back"), callback_data="menu_principal")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    if data.startswith("set_lang_"):
        new_lang = data.replace("set_lang_", "")
        USER_LANG[user.id] = new_lang
        lang = new_lang
        text = t(lang, "welcome", name=user.first_name)
        await query.message.reply_text(
            f"✅ Idioma definido!",
            reply_markup=get_persistent_keyboard(lang)
        )
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(get_main_menu_keyboard(lang)), parse_mode="Markdown")
        return

    if data == "menu_principal":
        AWAITING_CPF.pop(user.id, None)
        text = t(lang, "welcome", name=user.first_name)
        await safe_edit(text, reply_markup=InlineKeyboardMarkup(get_main_menu_keyboard(lang)), parse_mode="Markdown")
        return

    if data == "faq":
        text = t(lang, "faq")
        keyboard = [[InlineKeyboardButton(t(lang, "btn_back_catalog"), callback_data="menu_principal")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    if data.startswith("prod_"):
        pid = data.replace("prod_", "")
        p = products.get(pid)
        if not p:
            await query.message.reply_text("Produto indisponível.")
            return

        text = (
            f"{p['name']}\n\n"
            f"{p['description']}\n\n"
            f"💰 *Investimento:*\n"
            f"• *PIX:* R$ {p['price_brl']:.2f}\n"
            f"• *Cripto:* ${p['price_usd']:.2f} USDT\n\n"
            f"Escolha a forma de pagamento abaixo:"
        )

        keyboard = [
            [InlineKeyboardButton(t(lang, "btn_pay_pix", price=p['price_brl']), callback_data=f"ask_cpf_{pid}")],
            [InlineKeyboardButton(t(lang, "btn_pay_crypto", price=p['price_usd']), callback_data=f"crypto_hub_{pid}")],
            [InlineKeyboardButton(t(lang, "btn_back"), callback_data="menu_principal")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    if data.startswith("crypto_hub_"):
        pid = data.replace("crypto_hub_", "")
        p = products.get(pid)
        base_price = p["price_usd"]
        text = t(lang, "crypto_menu_title", name=p['name'], price=base_price)

        keyboard = [
            [InlineKeyboardButton(t(lang, "btn_fast_crypto"), callback_data=f"fast_net_{pid}")],
            [InlineKeyboardButton(t(lang, "btn_other_crypto"), callback_data=f"other_net_{pid}")],
            [InlineKeyboardButton(t(lang, "btn_back"), callback_data=f"prod_{pid}")]
        ]
        await safe_edit(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    if data.startswith("ask_cpf_"):
        pid = data.replace("ask_cpf_", "")
        p = products.get(pid)
        AWAITING_CPF[user.id] = pid
        text = t(lang, "ask_cpf", name=p['name'], price=p['price_brl'])
        keyboard = [[InlineKeyboardButton(t(lang, "btn_cancel"), callback_data="menu_principal")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    if data.startswith("fast_net_"):
        pid = data.replace("fast_net_", "")
        p = products.get(pid)
        base_price = p["price_usd"]
        fee_base = get_network_fee_estimate("base/usdc")
        price_base = base_price if fee_base <= 0.60 else base_price + fee_base

        text = t(lang, "title_fast_crypto", name=p['name'], price=base_price)

        keyboard = [
            [InlineKeyboardButton(f"⚡ BSC (BEP-20 USDT) • ${base_price:.2f} (~1 min)", callback_data=f"bbpay_bep20_usdt_{pid}")],
            [InlineKeyboardButton(f"⚡ Base (USDC) • ${price_base:.2f} (~20 seg)", callback_data=f"bbpay_base_usdc_{pid}")],
            [InlineKeyboardButton(f"⚡ Polygon (USDT) • ${base_price:.2f} (~30 seg)", callback_data=f"bbpay_polygon_usdt_{pid}")],
            [InlineKeyboardButton(f"⚡ Solana (USDT) • ${base_price:.2f} (~20 seg)", callback_data=f"bbpay_sol_usdt_{pid}")],
            [InlineKeyboardButton(f"⚡ Arbitrum (USDC) • ${base_price:.2f} (~20 seg)", callback_data=f"bbpay_arbitrum_usdc_{pid}")],
            [InlineKeyboardButton(t(lang, "btn_back"), callback_data=f"crypto_hub_{pid}")]
        ]
        await safe_edit(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    if data.startswith("other_net_"):
        pid = data.replace("other_net_", "")
        p = products.get(pid)
        base_price = p["price_usd"]

        fee_erc = get_network_fee_estimate("erc20/usdt")
        fee_btc = get_network_fee_estimate("btc")
        fee_eth = get_network_fee_estimate("eth")

        # Regra de repasse: <= 0.60 absorve, > 0.60 repassa
        price_btc = base_price if fee_btc <= 0.60 else base_price + fee_btc
        price_eth = base_price if fee_eth <= 0.60 else base_price + fee_eth
        price_erc = base_price if fee_erc <= 0.60 else base_price + fee_erc

        label_btc_fee = f" (+$0.00)" if fee_btc <= 0.60 else f" (+${fee_btc:.2f})"
        label_eth_fee = f" (+$0.00)" if fee_eth <= 0.60 else f" (+${fee_eth:.2f})"
        label_erc_fee = f" (+$0.00)" if fee_erc <= 0.60 else f" (+${fee_erc:.2f})"

        text = t(lang, "title_other_crypto", name=p['name'], price=base_price)

        keyboard = [
            [InlineKeyboardButton(f"🟠 Bitcoin (BTC) • ${price_btc:.2f}{label_btc_fee} (~20 min)", callback_data=f"bbpay_btc_{pid}")],
            [InlineKeyboardButton(f"🔷 Ethereum (ETH) • ${price_eth:.2f}{label_eth_fee} (~5 min)", callback_data=f"bbpay_eth_{pid}")],
            [InlineKeyboardButton(f"🐢 Ethereum (ERC-20 USDT) • ${price_erc:.2f}{label_erc_fee} (~10 min)", callback_data=f"bbpay_erc20_usdt_{pid}")],
            [InlineKeyboardButton(t(lang, "btn_back"), callback_data=f"crypto_hub_{pid}")]
        ]
        await safe_edit(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    if data.startswith("bbpay_"):
        # Formato: bbpay_{ticker}_{pid} (ex: bbpay_bep20_usdt_gemini_pro ou bbpay_btc_gemini_pro)
        raw_info = data.replace("bbpay_", "")
        parts = raw_info.split("_")
        
        # Reconhecimento do ticker (composta ex: bep20/usdt, base/usdc ou simples btc, eth)
        if parts[0] in ["bep20", "polygon", "sol", "arbitrum", "base", "erc20"]:
            ticker = f"{parts[0]}/{parts[1]}"
            pid = "_".join(parts[2:])
        else:
            ticker = parts[0]
            pid = "_".join(parts[1:])

        p = products.get(pid)
        order_id = f"ord_{uuid.uuid4().hex[:8]}"

        try:
            # Regra de negócio estrita:
            # Se a taxa for até $0.60, nós absorvemos (net_fee = 0.0)
            # Se for maior que $0.60, a taxa é repassada integralmente ao cliente
            raw_fee = get_network_fee_estimate(ticker)
            if raw_fee <= 0.60:
                net_fee = 0.0
                final_amount = round(p["price_usd"], 2)
            else:
                net_fee = raw_fee
                final_amount = round(p["price_usd"] + net_fee, 2)
            
            bb_res = create_blockbee_payment(ticker, order_id)
            address_in = bb_res["address_in"]

            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute(
                "INSERT INTO orders (order_id, user_id, username, product_id, payment_method, amount, status, payment_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (order_id, user.id, user.username or "", pid, f"blockbee_{ticker.replace('/', '_')}", final_amount, "pending", address_in)
            )
            conn.commit()
            conn.close()

            # Mapeamento amigável de nomes de redes
            net_names = {
                "bep20/usdt": ("BNB Smart Chain (BEP-20)", "USDT", "1 a 2 minutos"),
                "polygon/usdt": ("Polygon (PoS)", "USDT", "30 a 60 segundos"),
                "sol/usdt": ("Solana", "USDT", "15 a 30 segundos"),
                "arbitrum/usdc": ("Arbitrum One", "USDC", "15 a 30 segundos"),
                "base/usdc": ("Base Network", "USDC", "15 a 30 segundos"),
                "btc": ("Bitcoin (BTC)", "BTC", "10 a 30 minutos"),
                "eth": ("Ethereum (ETH Nativo)", "ETH", "3 a 8 minutos"),
                "erc20/usdt": ("Ethereum (ERC-20)", "USDT", "5 a 15 minutos")
            }
            net_name, coin_symbol, time_est = net_names.get(ticker, (ticker.upper(), "USDT", "1 a 5 minutos"))

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=2,
            )
            qr.add_data(address_in)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            bio = io.BytesIO()
            bio.name = 'qrcode_bb.png'
            img.save(bio, 'PNG')
            bio.seek(0)

            # Converter valor de USD para a moeda de envio (ex: calcular fração de BTC/ETH se não for stablecoin)
            final_crypto_amount, final_crypto_str = convert_usd_to_crypto(ticker, final_amount)

            # Montar detalhes de cobrança de forma transparente
            if net_fee > 0:
                fee_detail = (
                    f"💰 *Detalhamento do Valor:*\n"
                    f"• Valor do Produto: *${p['price_usd']:.2f} USD*\n"
                    f"• Taxa de Rede (Gas Blockchain): *+${net_fee:.2f} USD*\n"
                    f"• Total em Dólar: *${final_amount:.2f} USD*\n"
                    f"• 👉 *Total a Enviar: `{final_crypto_str}` {coin_symbol}*\n\n"
                )
            else:
                fee_detail = (
                    f"💰 *Valor Total: ${final_amount:.2f} USD*\n"
                    f"• Taxa de rede: *Grátis / Inclusa*\n"
                    f"• 👉 *Total a Enviar: `{final_crypto_str}` {coin_symbol}*\n\n"
                )

            caption = (
                f"🌐 *Cobrança Cripto*\n\n"
                f"Produto: *{p['name']}*\n"
                f"Rede: *{net_name}*\n"
                f"Moeda: *{coin_symbol}*\n\n"
                f"{fee_detail}"
                f"📋 *Endereço de Pagamento:*\n"
                f"`{address_in}`\n\n"
                f"⚡ *Tempo Médio de Confirmação:* {time_est}\n\n"
                f"ℹ️ _Envie exatamente `{final_crypto_str}` {coin_symbol} pela rede {net_name}. A liberação é 100% automática assim que a rede confirmar!_"
            )

            keyboard = [
                [InlineKeyboardButton(t(lang, "btn_check_status"), callback_data=f"check_{order_id}")],
                [InlineKeyboardButton(t(lang, "btn_cancel"), callback_data="menu_principal")]
            ]

            await query.message.reply_photo(
                photo=bio,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except Exception as e:
            logger.error(f"Erro BlockBee: {e}")
            await query.message.reply_text(f"Erro ao gerar cobrança BlockBee: {e}")
        return

    if data.startswith("pay_crypto_"):
        pid = data.replace("pay_crypto_", "")
        p = products.get(pid)
        order_id = f"ord_{uuid.uuid4().hex[:8]}"

        try:
            invoice = create_cryptobot_invoice(p["price_usd"], f"Nexus Tools - {p['name']}", order_id)
            pay_url = invoice["pay_url"]

            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute(
                "INSERT INTO orders (order_id, user_id, username, product_id, payment_method, amount, status, payment_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (order_id, user.id, user.username or "", pid, "cryptobot", p["price_usd"], "pending", invoice.get("invoice_id"))
            )
            conn.commit()
            conn.close()

            text = t(lang, "crypto_caption", name=p['name'], price=p['price_usd'])

            keyboard = [
                [InlineKeyboardButton(t(lang, "btn_pay_cryptobot"), url=pay_url)],
                [InlineKeyboardButton(t(lang, "btn_check_status"), callback_data=f"check_{order_id}")],
                [InlineKeyboardButton(t(lang, "btn_cancel"), callback_data="menu_principal")]
            ]
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Erro CryptoBot: {e}")
            await query.message.reply_text("Erro ao gerar fatura cripto. Tente novamente.")
        return

    if data.startswith("check_"):
        order_id = data.replace("check_", "")
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT status, delivered_item, product_id, payment_method, payment_id FROM orders WHERE order_id = ?", (order_id,))
        row = c.fetchone()
        conn.close()

        if row and row[0] == "paid":
            p = products.get(row[2], {})
            item = row[1]
            instructions = p.get("instructions", "Seu acesso: {item}").format(item=item)
            text = t(lang, "paid_success", instructions=instructions)
            keyboard = [
                [InlineKeyboardButton(t(lang, "btn_back_catalog"), callback_data="menu_principal")],
                [InlineKeyboardButton(t(lang, "btn_help"), callback_data="faq")]
            ]
            await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            # Além do pop-up, envia mensagem explicativa no chat para o cliente nunca ficar perdido
            method = row[3] if row else "pix"
            if method == "cryptobot":
                msg_status = (
                    "⏳ *Status do Pagamento Cripto (CryptoBot):* Aguardando Confirmação.\n\n"
                    "• Se você depositou via rede *Ethereum (ERC-20)*, o CryptoBot aguarda cerca de *10 a 15 minutos* (12 a 32 blocos de segurança da rede Ethereum) para liberar o saldo na sua carteira do Telegram.\n"
                    "• Assim que o saldo creditar, abra o @CryptoBot e clique em **Pagar Fatura**.\n"
                    "• Nosso robô monitora 24/7 e entregará o produto automaticamente assim que a fatura for paga!"
                )
            elif "blockbee" in method:
                msg_status = (
                    "⏳ *Status do Pagamento Cripto Direto (BlockBee):* Aguardando Confirmação na Blockchain.\n\n"
                    "• *Tempo Médio:* 1 a 2 minutos na rede BNB Smart Chain (BEP-20).\n"
                    "• Assim que os blocos confirmarem, os fundos são encaminhados e o seu produto será liberado na hora!"
                )
            else:
                msg_status = (
                    "⏳ *Status do Pagamento PIX:* Aguardando Confirmação do Banco Central.\n\n"
                    "Geralmente é aprovado em até 10 a 30 segundos. Assim que o banco confirmar, seu produto será liberado na hora!"
                )
            await query.answer("Status: Aguardando confirmação do pagamento...", show_alert=True)
            await query.message.reply_text(msg_status, parse_mode="Markdown")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = get_user_lang(user.id, user)
    text_msg = update.message.text.strip() if update.message.text else ""

    # Botões do Teclado Fixo Inferior
    if any(text_msg == t(l, "btn_catalog") for l in ("pt", "en", "es")) or "cardápio" in text_msg.lower() or "cardapio" in text_msg.lower() or "ferramentas" in text_msg.lower() or "opções" in text_msg.lower() or "opcoes" in text_msg.lower():
        text = t(lang, "welcome", name=user.first_name)
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(get_main_menu_keyboard(lang)), parse_mode="Markdown")
        return

    if any(text_msg == t(l, "btn_help") for l in ("pt", "en", "es")) or "ajuda" in text_msg.lower() or "suporte" in text_msg.lower() or "garantia" in text_msg.lower():
        text = t(lang, "faq")
        keyboard = [[InlineKeyboardButton(t(lang, "btn_back_catalog"), callback_data="menu_principal")]]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    if any(text_msg == t(l, "btn_lang") for l in ("pt", "en", "es")) or "idioma" in text_msg.lower() or "language" in text_msg.lower():
        text = "🌐 *Escolha o seu idioma / Select your language / Elige tu idioma:*"
        keyboard = [
            [InlineKeyboardButton("🇧🇷 Português", callback_data="set_lang_pt")],
            [InlineKeyboardButton("🇺🇸 English", callback_data="set_lang_en")],
            [InlineKeyboardButton("🇪🇸 Español", callback_data="set_lang_es")],
            [InlineKeyboardButton(t(lang, "btn_back"), callback_data="menu_principal")]
        ]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    pid = AWAITING_CPF.pop(user.id, None)
    if not pid:
        return

    p = products.get(pid)
    if not p:
        await update.message.reply_text("Produto não encontrado.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_back"), callback_data="menu_principal")]]))
        return

    cleaned_cpf = "".join(c for c in text_msg if c.isdigit())
    
    try:
        await update.message.delete()
    except Exception:
        pass

    if len(cleaned_cpf) != 11:
        await update.message.reply_text(
            t(lang, "cpf_invalid"),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_back"), callback_data="menu_principal")]])
        )
        return

    order_id = f"ord_{uuid.uuid4().hex[:8]}"
    loading_msg = await update.message.reply_text(t(lang, "generating_pix"))
    
    try:
        pix_res = create_pixget_invoice(p["price_brl"], cleaned_cpf, f"Nexus Tools - {p['name']}", order_id)
        qr_code_str = pix_res["qr_code"]
        pix_id = pix_res["id"]

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT INTO orders (order_id, user_id, username, product_id, payment_method, amount, status, payment_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (order_id, user.id, user.username or "", pid, "pix", p["price_brl"], "pending", pix_id)
        )
        conn.commit()
        conn.close()

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(qr_code_str)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        bio = io.BytesIO()
        bio.name = 'qrcode.png'
        img.save(bio, 'PNG')
        bio.seek(0)

        caption = t(lang, "pix_caption", name=p['name'], price=p['price_brl'], qr_code=qr_code_str)

        keyboard = [
            [InlineKeyboardButton(t(lang, "btn_check_status"), callback_data=f"check_{order_id}")],
            [InlineKeyboardButton(t(lang, "btn_cancel"), callback_data="menu_principal")]
        ]

        await loading_msg.delete()
        await context.bot.send_photo(
            chat_id=user.id,
            photo=bio,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Erro ao gerar PixGet: {e}")
        await loading_msg.edit_text(
            f"⚠️ Erro ao emitir o PIX:\n`{e}`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_back"), callback_data="menu_principal")]])
        )

def main():
    import socket
    # Trava de instância única para impedir processos duplicados / 409 Conflict
    try:
        lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        lock_socket.bind('\0nexus_store_bot_lock')
    except Exception:
        print("Outra instância do run_store.py já está em execução. Encerrando.")
        sys.exit(0)

    init_db()
    token = os.getenv("STORE_BOT_TOKEN", "")
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Bot Nexus Tools Store v3.0 (i18n PT/EN/ES + UX Otimizada) rodando...")
    app.run_polling()

if __name__ == "__main__":
    main()
