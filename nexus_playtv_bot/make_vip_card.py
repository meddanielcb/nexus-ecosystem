import os
import qrcode
from PIL import Image, ImageDraw, ImageFont

def create_vip_onboarding_card(
    output_path: str,
    username: str,
    password: str,
    server_url: str,
    m3u_url: str,
    plan_name: str,
    valid_until: str
):
    W, H = 1080, 1920
    # Base dark luxury
    img = Image.new("RGB", (W, H), "#080B10")
    draw = ImageDraw.Draw(img)

    # Gradient background glow
    for y in range(H):
        ratio = y / H
        # Soft subtle dark blue/cyan gradient at top and bottom
        r = int(8 + 12 * (1 - ratio))
        g = int(11 + 20 * (1 - ratio) + 10 * ratio)
        b = int(16 + 35 * (1 - ratio) + 20 * ratio)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Font handling
    def get_font(size, bold=False):
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
        for p in font_paths:
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    font_title = get_font(42, bold=True)
    font_subtitle = get_font(26, bold=False)
    font_section = get_font(28, bold=True)
    font_label = get_font(22, bold=True)
    font_val = get_font(28, bold=True)
    font_body = get_font(22, bold=False)
    font_small = get_font(18, bold=False)
    font_btn = get_font(24, bold=True)

    # 1. Header Banner
    banner_path = "/opt/data/nexus_playtv_bot/assets/nexus_playtv_banner.png"
    if os.path.exists(banner_path):
        banner = Image.open(banner_path).convert("RGB")
        # Resize preserving ratio to width 1080
        bw, bh = banner.size
        target_h = int(bh * (W / bw))
        banner = banner.resize((W, target_h), Image.LANCZOS)
        # Crop to 400px height with top focus
        banner_crop = banner.crop((0, 0, W, 400))
        img.paste(banner_crop, (0, 0))
        
        # Vignette fade over banner bottom
        for i in range(120):
            alpha = int(255 * (i / 120))
            draw.line([(0, 280 + i), (W, 280 + i)], fill=(8, 11, 16))

    curr_y = 390

    # Brand Title Header
    draw.text((W//2, curr_y), "NEXUS PLAYTV • VIP PASS", font=font_title, fill="#00E5FF", anchor="mm")
    curr_y += 45
    draw.text((W//2, curr_y), f"Plano: {plan_name} • Ativação Imediata", font=font_subtitle, fill="#E6EDF3", anchor="mm")
    curr_y += 50

    # 2. Hero Card: QR CODE "ZERO DIGITAÇÃO" (1-CLIQUE NO CELULAR)
    # Background card
    card1_top = curr_y
    card1_h = 420
    draw.rounded_rectangle([40, card1_top, W - 40, card1_top + card1_h], radius=24, fill="#121820", outline="#00E5FF", width=2)
    
    # Generate QR Code pointing to web player auto-login
    web_login_url = f"https://player.nexusplay.tv/?user={username}&pass={password}"
    qr = qrcode.QRCode(box_size=7, border=2)
    qr.add_data(web_login_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#000000", back_color="#FFFFFF").convert("RGB")
    qw, qh = qr_img.size

    # Paste QR Code on the right side of Card 1
    qr_x = W - 40 - qw - 30
    qr_y = card1_top + (card1_h - qh) // 2 + 10
    img.paste(qr_img, (qr_x, qr_y))

    # Text inside Card 1 (Left side)
    tx = 70
    ty = card1_top + 35
    draw.text((tx, ty), "⚡ ASSISTA AGORA NO CELULAR / PC", font=font_section, fill="#00E5FF")
    ty += 40
    draw.text((tx, ty), "ZERO DIGITAÇÃO DE SENHAS", font=font_label, fill="#E024C3")
    ty += 40
    draw.text((tx, ty), "1. Aponte a câmera do celular para o QR Code\n2. O WebPlayer abre conectado na hora\n3. Futebol ao vivo, filmes e séries em 4K", font=font_body, fill="#E6EDF3")
    ty += 95
    # Big Button look
    draw.rounded_rectangle([tx, ty, tx + 420, ty + 55], radius=12, fill="#00E5FF")
    draw.text((tx + 210, ty + 27), "▶ ASSISTIR NO NAVEGADOR", font=font_btn, fill="#080B10", anchor="mm")

    curr_y = card1_top + card1_h + 30

    # 3. Card 2: Credenciais & Códigos Rápidos (Smart TV)
    card2_top = curr_y
    card2_h = 430
    draw.rounded_rectangle([40, card2_top, W - 40, card2_top + card2_h], radius=24, fill="#121820", outline="#21262D", width=2)

    c2_x = 70
    c2_y = card2_top + 30
    draw.text((c2_x, c2_y), "📺 DADOS DE ACESSO PARA SMART TV", font=font_section, fill="#FFFFFF")
    draw.text((W - 70, c2_y), "STATUS: ATIVO", font=font_label, fill="#2EA043", anchor="ra")
    c2_y += 50

    # Fields grid
    fields = [
        ("DNS / SERVIDOR:", server_url),
        ("USUÁRIO:", username),
        ("SENHA:", password),
        ("VALIDADE ATÉ:", valid_until)
    ]

    for label, val in fields:
        draw.text((c2_x, c2_y), label, font=font_label, fill="#8B949E")
        c2_y += 30
        draw.rounded_rectangle([c2_x, c2_y, W - 70, c2_y + 48], radius=10, fill="#182230", outline="#30363D", width=1)
        draw.text((c2_x + 20, c2_y + 24), val, font=font_val, fill="#00E5FF", anchor="lm")
        c2_y += 65

    curr_y = card2_top + card2_h + 30

    # 4. Card 3: Downloader Codes (Apenas 1 número no controle remoto)
    card3_top = curr_y
    card3_h = 440
    draw.rounded_rectangle([40, card3_top, W - 40, card3_top + card3_h], radius=24, fill="#121820", outline="#21262D", width=2)

    c3_x = 70
    c3_y = card3_top + 30
    draw.text((c3_x, c3_y), "🚀 INSTALAÇÃO RÁPIDA (CÓDIGOS DOWNLOADER)", font=font_section, fill="#FFFFFF")
    c3_y += 45
    draw.text((c3_x, c3_y), "No controle da TV Box ou Firestick, digite apenas o código numérico:", font=font_body, fill="#8B949E")
    c3_y += 50

    # App boxes
    apps = [
        ("TiviMate Pro (Recomendado)", "CÓDIGO: 49812", "#00E5FF"),
        ("XCIPTV Player", "CÓDIGO: 82341", "#E024C3"),
        ("IBO Player (Samsung / LG)", "Device ID via Suporte", "#2EA043")
    ]

    for app_name, code_txt, tag_color in apps:
        draw.rounded_rectangle([c3_x, c3_y, W - 70, c3_y + 70], radius=12, fill="#182230", outline=tag_color, width=1)
        draw.text((c3_x + 20, c3_y + 35), app_name, font=font_label, fill="#FFFFFF", anchor="lm")
        draw.rounded_rectangle([W - 70 - 260, c3_y + 12, W - 85, c3_y + 58], radius=8, fill=tag_color)
        draw.text((W - 70 - 130, c3_y + 35), code_txt, font=font_btn, fill="#080B10" if tag_color != "#080B10" else "#FFFFFF", anchor="mm")
        c3_y += 85

    # Footer Help
    curr_y = card3_top + card3_h + 30
    draw.text((W//2, curr_y), "Dúvidas ou ajuda na TV? Toque no botão 'Suporte VIP' no Telegram.", font=font_small, fill="#8B949E", anchor="mm")

    img.save(output_path, "PNG", quality=95)
    print(f"VIP Onboarding Card gerado: {output_path}")

if __name__ == "__main__":
    create_vip_onboarding_card(
        "/opt/data/nexus_playtv_bot/assets/card_onboarding_vip.png",
        username="nexus_vip_7894",
        password="[REDACTED]",
        server_url="http://cdn.nexusplay.tv:8080",
        m3u_url="http://cdn.nexusplay.tv:8080/get.php?username=nexus_vip_7894&password=play_pass_2026&type=m3u_plus",
        plan_name="Pass Final de Semana 48h",
        valid_until="14/09/2026 às 21:00"
    )
