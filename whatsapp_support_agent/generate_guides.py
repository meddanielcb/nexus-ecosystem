import os
from PIL import Image, ImageDraw, ImageFont

DIR = "/opt/data/nexus_repo/whatsapp_support_agent/guides_media"
os.makedirs(DIR, exist_ok=True)

def create_guide_image(filename, title, subtitle, steps, highlight_box=None):
    w, h = 1080, 1080
    im = Image.new("RGB", (w, h), "#080B10")
    draw = ImageDraw.Draw(im)
    
    # Bordas e Header Dark Neon
    draw.rectangle([(20, 20), (w-20, h-20)], outline="#1C2530", width=4)
    draw.rectangle([(40, 40), (w-40, 160)], fill="#0D1117", outline="#00E5FF", width=2)
    
    # Textos principais
    # Header
    draw.text((w//2, 80), "NEXUS PLAYTV • SUPORTE RÁPIDO", fill="#00E5FF", anchor="mm")
    draw.text((w//2, 125), title.upper(), fill="#FFFFFF", anchor="mm")
    
    # Caixa de instrução central
    draw.rectangle([(40, 200), (w-40, 920)], fill="#111722", outline="#21262D", width=2)
    
    y = 260
    for i, step in enumerate(steps, 1):
        # Bullet ciano/verde
        draw.ellipse([(80, y-10), (120, y+30)], fill="#00E5FF" if i % 2 == 1 else "#39FF88")
        draw.text((100, y+10), str(i), fill="#080B10", anchor="mm")
        
        # Texto do passo
        draw.text((150, y+10), step, fill="#E6EDF3", anchor="lm")
        y += 120
        
    # Caixa de destaque visual
    if highlight_box:
        draw.rectangle([(80, y+20), (w-80, y+180)], fill="#080B10", outline="#39FF88", width=3)
        draw.text((w//2, y+70), "💡 DICA DE OURO:", fill="#39FF88", anchor="mm")
        draw.text((w//2, y+125), highlight_box, fill="#FFFFFF", anchor="mm")
        
    # Rodapé
    draw.text((w//2, 980), "Dúvidas? Envie uma foto da tela da sua TV agora mesmo!", fill="#7C8896", anchor="mm")
    
    out_path = os.path.join(DIR, filename)
    im.save(out_path, "PNG")
    print(f"Guia gerado: {out_path}")

# 1. Guia XCIPTV
create_guide_image(
    "guia_xciptv_login.png",
    "Como Entrar no XCIPTV (Android TV / TV Box / FireStick)",
    "Passo a passo simples sem digitar URL gigante",
    [
        "Abra o app XCIPTV na sua TV ou TV Box",
        "Selecione a opção: Entrar com Código / Xtream API",
        "Campo Código Parceiro: digite 00042",
        "Campo Usuário: digite o usuário do seu Cartão VIP",
        "Campo Senha: digite a sua senha e clique em OK"
    ],
    highlight_box="Não precisa digitar link de servidor! O código 00042 preenche tudo."
)

# 2. Guia IBO Player (Samsung & LG)
create_guide_image(
    "guia_ibo_mac_key.png",
    "Ativação Automática no IBO Player (Samsung e LG)",
    "Como mandar a foto certa para nossa IA ativar",
    [
        "Instale o IBO Player na loja da sua TV",
        "Abra o app e fique na primeira tela inicial",
        "Localize na tela o 'Device MAC' e o 'Device Key'",
        "Tire uma foto bem nítida da tela inteira da sua TV",
        "Envie a foto aqui no WhatsApp que ativamos na hora!"
    ],
    highlight_box="A foto precisa estar nítida para nossa IA não confundir '8' com 'B'!"
)

# 3. Guia WebPlayer
create_guide_image(
    "guia_webplayer.png",
    "WebPlayer Direto no Navegador (PC / Celular / TV)",
    "Assista sem baixar nenhum aplicativo",
    [
        "Abra o navegador e acesse: play.nexusplay.tv",
        "Insira seu Usuário e Senha",
        "Clique no botão verde 'Entrar no WebPlayer'",
        "Escolha Futebol, Filmes ou Séries na barra lateral"
    ],
    highlight_box="Se a TV for antiga ou o app travar, use o WebPlayer pelo navegador!"
)
