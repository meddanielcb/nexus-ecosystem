import os
import sys
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import fitz # PyMuPDF

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from partner_apps import PARTNER_APPS_CODE, MASTERX_DOWNLOADER_CODE, MASTERX_APK_URL, SERVER_DNS_ALT

def generate_playtv_vip_dossier(pdf_path: str, username: str, password: str, server_url: str, m3u_url: str, plan_name: str, valid_until: str):
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Cores de luxo: Dark Tech (Fundo quase preto, Ciano e Magenta)
    DARK_BG = colors.HexColor("#0D1117")
    DARK_CARD = colors.HexColor("#161B22")
    CYAN = colors.HexColor("#00E5FF")
    MAGENTA = colors.HexColor("#E024C3")
    TEXT_WHITE = colors.HexColor("#FFFFFF")
    TEXT_MUTED = colors.HexColor("#8B949E")
    BORDER_COLOR = colors.HexColor("#30363D")
    GREEN_SUCCESS = colors.HexColor("#2EA043")

    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=CYAN,
        alignment=1 # Center
    )

    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=TEXT_WHITE,
        alignment=1
    )

    h2_style = ParagraphStyle(
        'H2Style',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=CYAN,
        spaceBefore=10,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14,
        textColor=TEXT_WHITE
    )

    code_label = ParagraphStyle(
        'CodeLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        textColor=CYAN
    )

    code_val = ParagraphStyle(
        'CodeVal',
        parent=styles['Normal'],
        fontName='Courier-Bold',
        fontSize=11,
        leading=14,
        textColor=TEXT_WHITE
    )

    elements = []

    # 1. HEADER / LOGO & IDENTIDADE
    banner_img = "/opt/data/nexus_playtv_bot/assets/nexus_playtv_banner.png"
    if os.path.exists(banner_img):
        # Banner no topo (largura total 523pt, altura ~130pt)
        elements.append(Image(banner_img, width=523, height=135))
        elements.append(Spacer(1, 10))

    elements.append(Paragraph("GUIA VIP DE ATIVAÇÃO IMEDIATA", title_style))
    elements.append(Paragraph("Seu passaporte definitivo para +25.000 Canais 4K, Esportes Ao Vivo e Streaming", subtitle_style))
    elements.append(Spacer(1, 12))

    # 2. CARTÃO DE CREDENCIAIS (O QUE ELE MAIS PRECISA)
    cred_data = [
        [
            Paragraph("<b>STATUS:</b> <font color='#2EA043'>ATIVO & LIBERADO</font>", code_label),
            Paragraph(f"<b>PLANO:</b> {plan_name}", code_label)
        ],
        [
            Paragraph("<b>DNS / SERVIDOR (HOST):</b>", code_label),
            Paragraph(f"<code>{server_url}</code><br/>"
                      f"<font size=7 color='#8B949E'>Alternativo: {SERVER_DNS_ALT}</font>", code_val)
        ],
        [
            Paragraph("<b>USUÁRIO:</b>", code_label),
            Paragraph(f"<code>{username}</code>", code_val)
        ],
        [
            Paragraph("<b>SENHA:</b>", code_label),
            Paragraph(f"<code>{password}</code>", code_val)
        ],
        [
            Paragraph("<b>VALIDADE:</b>", code_label),
            Paragraph(f"<b>{valid_until}</b>", code_val)
        ],
        [
            Paragraph("<b>LINK M3U DIRETO:</b>", code_label),
            Paragraph(f"<font size=7.5><code>{m3u_url}</code></font>", code_val)
        ]
    ]

    t_cred = Table(cred_data, colWidths=[150, 360])
    t_cred.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), DARK_CARD),
        ('BOX', (0,0), (-1,-1), 1.5, CYAN),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    elements.append(t_cred)
    elements.append(Spacer(1, 14))

    # 3. ATALHO ZERO CONFIGURAÇÃO: ASSISTA AGORA NO NAVEGADOR
    web_data = [
        [
            Paragraph("⚡ <b>OPÇÃO 1: ASSISTA AGORA NO CELULAR OU PC (ZERO CONFIGURAÇÃO)</b>", ParagraphStyle('W1', fontName='Helvetica-Bold', fontSize=10.5, textColor=CYAN)),
        ],
        [
            Paragraph(
                "Não quer instalar nada agora? Você pode assistir <b>imediatamente</b> no Google Chrome, Safari ou Edge:<br/>"
                "1. Acesse o WebPlayer Oficial: <b><code>http://painelmaster.app/portal</code></b><br/>"
                "2. Digite o Usuário e Senha do seu cartão acima.<br/>"
                "3. Pronto! Grade completa de futebol ao vivo, filmes e séries rodando em 5 segundos.",
                body_style
            )
        ]
    ]
    t_web = Table(web_data, colWidths=[510])
    t_web.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#1A2333")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#1F6FEB")),
        ('TOPPADDING', (0,0), (-1,-1), 7),
        ('BOTTOMPADDING', (0,0), (-1,-1), 7),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    elements.append(t_web)
    elements.append(Spacer(1, 14))

    # 4. INSTALAÇÃO NA SMART TV (GUIA VISUAL PASSO A PASSO)
    elements.append(Paragraph("📺 <b>OPÇÃO 2: INSTALAÇÃO NA SMART TV OU TV BOX (PASSO A PASSO)</b>", h2_style))

    guide_data = [
        [
            Paragraph("<b>SEU APARELHO</b>", code_label),
            Paragraph("<b>APLICATIVO RECOMENDADO</b>", code_label),
            Paragraph("<b>COMO CONFIGURAR EM 3 PASSOS RÁPIDOS</b>", code_label)
        ],
        [
            Paragraph("<b>Smart TV Samsung</b><br/>(Tizen)", body_style),
            Paragraph("<b>Magic PLAY</b><br/>Lazer Play · EPIC PLAY<br/>FunPlays · IBO Player", body_style),
            Paragraph(
                "1. Abra a loja da TV Samsung e instale um dos apps parceiros.<br/>"
                "2. Se o app pedir o <b>Código Parceiro</b>, use o código que aparece na própria tela.<br/>"
                "3. Ou mande uma foto da tela no bot que ativamos a lista automaticamente!",
                body_style
            )
        ],
        [
            Paragraph("<b>Smart TV LG</b><br/>(webOS)", body_style),
            Paragraph("<b>Magic PLAY</b><br/>Lazer Play · Super Play<br/>FunPlays · IBO Player", body_style),
            Paragraph(
                "1. Abra a LG Content Store e baixe um dos apps parceiros.<br/>"
                "2. Se o app pedir o <b>Código Parceiro</b>, use o código que aparece na própria tela.<br/>"
                "3. Servidor: <b>atmt.space</b> — depois use Usuário e Senha do cartão acima.",
                body_style
            )
        ],
        [
            Paragraph("<b>Fire Stick / TV Box</b><br/>(Android TV)", body_style),
            Paragraph("<b>MASTERX</b> (Play Store)<br/>ou XCIPTV / Vizzion Play", body_style),
            Paragraph(
                "1. Na Play Store instale o <b>MASTERX</b>. Alternativa via <b>Downloader</b>:<br/>"
                f"   código <b>{MASTERX_DOWNLOADER_CODE}</b> ({MASTERX_APK_URL}).<br/>"
                f"2. Se pedir o <b>Código Parceiro</b>, digite <b>{PARTNER_APPS_CODE}</b> (código do app MASTERX).<br/>"
                "3. Use o Servidor, Usuário e Senha do cartão acima. A lista carrega em 5 segundos.",
                body_style
            )
        ],
        [
            Paragraph("<b>iPhone / iPad / Apple TV</b>", body_style),
            Paragraph("<b>VU Player Pro</b><br/>ou Smarters Player", body_style),
            Paragraph(
                "1. Baixe o <b>VU Player Pro</b> grátis na App Store.<br/>"
                "2. Selecione <i>Add Your Playlist (via Xtream Codes)</i>.<br/>"
                "3. Servidor: <b>atmt.space</b> — use o Usuário e Senha do cartão acima.",
                body_style
            )
        ],
        [
            Paragraph("<b>Windows / Mac</b>", body_style),
            Paragraph("<b>IPTV Smarters</b><br/>ou WebPlayer", body_style),
            Paragraph(
                "1. Windows: baixe o instalador oficial <b>painelmaster.app/uploads/smarters-pc.exe</b>.<br/>"
                "2. Ou abra o WebPlayer no navegador: <b>painelmaster.app/portal</b>.<br/>"
                "3. Entre com Servidor, Usuário e Senha do cartão acima.",
                body_style
            )
        ]
    ]

    t_guide = Table(guide_data, colWidths=[110, 110, 290])
    t_guide.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#21262D")),
        ('BACKGROUND', (0,1), (-1,-1), DARK_CARD),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(t_guide)
    elements.append(Spacer(1, 14))

    # 5. CONTROLE REMOTO & SUPORTE
    footer_text = (
        "<b>🛡️ Garantia Anti-Travamento:</b> Nossos servidores operam com CDN P2P Híbrida. Se sua internet oscilar, o player reconecta automaticamente sem travar o jogo.<br/>"
        "<b>💬 Assistente IA 24h no Telegram:</b> Teve qualquer dificuldade para configurar o controle ou a TV? Chame o suporte no <b>@Nexus_playtvbot</b> — nosso assistente responde na hora com fotos da sua TV!"
    )
    t_footer = Table([[Paragraph(footer_text, ParagraphStyle('FT', fontName='Helvetica', fontSize=8.5, leading=12, textColor=TEXT_MUTED))]], colWidths=[510])
    t_footer.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(t_footer)

    doc.build(elements)
    print(f"PDF VIP gerado com sucesso em: {pdf_path}")

if __name__ == "__main__":
    test_pdf = "/opt/data/nexus_playtv_bot/assets/manual_vip_exemplo.pdf"
    generate_playtv_vip_dossier(
        pdf_path=test_pdf,
        username="nexus_vip_7894",
        password="play_pass_2026",
        server_url="http://atmt.space",
        m3u_url="http://atmt.space/get.php?username=nexus_vip_7894&password=play_pass_2026&type=m3u_plus&output=ts",
        plan_name="Pass Final de Semana 48h (Full HD / 4K)",
        valid_until="15/09/2026 às 21:00 (Horário de Brasília)"
    )
