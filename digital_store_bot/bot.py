import os
import json
import logging
import uuid
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from services import create_crypto_bot_invoice, create_pixget_invoice, purchase_on_demand_digiseller
from db import DB_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carregar catálogo
with open("/opt/data/digital_store_bot/products.json") as f:
    PRODUCTS = json.load(f)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu Principal amigável, visual e 100% por botões"""
    text = (
        "👋 *Bem-vindo à nossa Store Digital!*\n\n"
        "Aqui você adquire assinaturas e acessos premium oficiais com entrega automática imediata via PIX ou Cripto (USDT).\n\n"
        "Selecione uma ferramenta abaixo para ver detalhes e valores:"
    )
    
    keyboard = []
    for pid, pdata in PRODUCTS.items():
        keyboard.append([InlineKeyboardButton(f"{pdata['name']} - R$ {pdata['price_brl']:.2f}", callback_data=f"prod_{pid}")])
        
    keyboard.append([InlineKeyboardButton("❓ Como Funciona & Suporte", callback_data="help_info")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "menu_principal":
        await start(update, context)
        return
        
    if data == "help_info":
        text = (
            "ℹ️ *Como funciona o nosso serviço:*\n\n"
            "1. Você escolhe a ferramenta e a forma de pagamento (PIX ou USDT).\n"
            "2. O pagamento é identificado em segundos de forma 100% autônoma.\n"
            "3. O robô gera e entrega o seu link ou chave oficial diretamente neste chat!\n\n"
            "🔒 *Segurança:* Sem necessidade de senhas ou dados sensíveis."
        )
        keyboard = [[InlineKeyboardButton("⬅️ Voltar ao Cardápio", callback_data="menu_principal")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
        
    if data.startswith("prod_"):
        pid = data.replace("prod_", "")
        p = PRODUCTS.get(pid)
        if not p:
            await query.message.reply_text("Produto não encontrado.")
            return
            
        text = (
            f"*{p['name']}*\n\n"
            f"{p['description']}\n\n"
            f"💵 *Valores:* R$ {p['price_brl']:.2f} ou `${p['price_usd']:.2f} USDT`\n\n"
            f"Escolha como deseja pagar:"
        )
        
        keyboard = [
            [
                InlineKeyboardButton(f"🟢 Pagar via PIX (R$ {p['price_brl']:.2f})", callback_data=f"pay_pix_{pid}"),
            ],
            [
                InlineKeyboardButton(f"💎 Pagar com Cripto (${p['price_usd']:.2f} USDT)", callback_data=f"pay_crypto_{pid}"),
            ],
            [
                InlineKeyboardButton("⬅️ Escolher outro produto", callback_data="menu_principal")
            ]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
        
    if data.startswith("pay_crypto_"):
        pid = data.replace("pay_crypto_", "")
        p = PRODUCTS.get(pid)
        order_id = f"ord_{uuid.uuid4().hex[:8]}"
        user = query.from_user
        
        # Criar fatura no CryptoBot
        try:
            invoice = create_crypto_bot_invoice(p["price_usd"], f"Compra de {p['name']}", order_id)
            pay_url = invoice["pay_url"]
            
            # Salvar pedido pendente no banco
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute(
                "INSERT INTO orders (order_id, user_id, username, product_id, payment_method, amount, status, payment_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (order_id, user.id, user.username or "", pid, "crypto", p["price_usd"], "pending", invoice.get("invoice_id"))
            )
            conn.commit()
            conn.close()
            
            text = (
                f"🧾 *Fatura Cripto Gerada!*\n\n"
                f"Produto: *{p['name']}*\n"
                f"Valor: *${p['price_usd']:.2f} USDT*\n\n"
                f"Clique no botão abaixo para pagar via *@CryptoBot* com seu saldo no Telegram ou via Binance/MetaMask:"
            )
            
            keyboard = [
                [InlineKeyboardButton("💳 Pagar Agora com CryptoBot", url=pay_url)],
                [InlineKeyboardButton("🔄 Já paguei (Verificar)", callback_data=f"check_{order_id}")],
                [InlineKeyboardButton("⬅️ Cancelar", callback_data="menu_principal")]
            ]
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Erro ao gerar fatura cripto: {e}")
            await query.message.reply_text("Ocorreu um erro temporário ao gerar o pagamento. Tente novamente.")
            return

    if data.startswith("pay_pix_"):
        pid = data.replace("pay_pix_", "")
        p = PRODUCTS.get(pid)
        order_id = f"ord_{uuid.uuid4().hex[:8]}"
        user = query.from_user
        
        # Gerar PIX via Pixget
        try:
            pix_data = create_pixget_invoice(p["price_brl"], f"Compra {p['name']}", order_id)
            copy_paste = pix_data["pix_copy_paste"]
            
            # Salvar pedido no banco
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute(
                "INSERT INTO orders (order_id, user_id, username, product_id, payment_method, amount, status, payment_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (order_id, user.id, user.username or "", pid, "pix", p["price_brl"], "pending", pix_data.get("txid"))
            )
            conn.commit()
            conn.close()
            
            text = (
                f"🧾 *Pedido PIX Gerado!*\n\n"
                f"Produto: *{p['name']}*\n"
                f"Valor: *R$ {p['price_brl']:.2f}*\n\n"
                f"Copie o código PIX abaixo e pague no app do seu banco:\n\n"
                f"`{copy_paste}`\n\n"
                f"⚡ *A aprovação é imediata via Pixget.* Assim que pagar, o produto será liberado aqui automaticamente."
            )
            
            keyboard = [
                [InlineKeyboardButton("🔄 Já paguei (Checar Status)", callback_data=f"check_{order_id}")],
                [InlineKeyboardButton("⬅️ Cancelar", callback_data="menu_principal")]
            ]
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Erro PIX: {e}")
            await query.message.reply_text("Erro ao gerar PIX. Tente novamente.")

    if data.startswith("check_"):
        order_id = data.replace("check_", "")
        # Checagem de status
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT status, product_id, delivered_item FROM orders WHERE order_id = ?", (order_id,))
        row = c.fetchone()
        conn.close()
        
        if row and row[0] == "paid":
            pid = row[1]
            p = PRODUCTS.get(pid)
            inst = p["instructions"].format(item=row[2])
            await query.message.reply_text(f"🎉 *Pagamento Confirmado!*\n\n{inst}", parse_mode="Markdown")
        else:
            await query.answer("Ainda não identificamos o seu pagamento. Aguarde alguns instantes...", show_alert=True)

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("TELEGRAM_BOT_TOKEN não configurado.")
        return
        
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("Bot Store rodando com sucesso...")
    app.run_polling()

if __name__ == "__main__":
    main()
