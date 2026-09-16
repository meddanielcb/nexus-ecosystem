import os
import qrcode
import base64
from io import BytesIO

from partner_apps import (
    MASTERX_DOWNLOADER_CODE,
    PARTNER_APPS_CODE,
    PORTAL_URL,
    SERVER_DNS_PRIMARY,
    SERVER_DNS_ALT,
)

def generate_interactive_html(output_path, username, password, server_url, m3u_url, plan_name, valid_until):
    # Gerar QR Code em Base64
    qr = qrcode.QRCode(box_size=6, border=1)
    web_login_url = f"{PORTAL_URL}/?user={username}&pass={password}"
    qr.add_data(web_login_url)
    qr.make(fit=True)
    buf = BytesIO()
    qr.make_image(fill_color="#000000", back_color="#FFFFFF").save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Nexus PlayTV • VIP Access</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
  body {{ background: #080B10; color: #FFFFFF; display: flex; justify-content: center; padding: 16px; min-height: 100vh; }}
  .container {{ width: 100%; max-width: 480px; background: #0D1117; border: 1px solid #21262D; border-radius: 20px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.8); }}
  .banner {{ width: 100%; height: 180px; object-fit: cover; display: block; }}
  .header {{ padding: 20px; text-align: center; border-bottom: 1px solid #161B22; }}
  .header h1 {{ font-size: 22px; color: #00E5FF; letter-spacing: 1px; font-weight: 800; }}
  .header p {{ font-size: 13px; color: #8B949E; margin-top: 4px; }}
  .section {{ padding: 16px 20px; border-bottom: 1px solid #161B22; }}
  
  /* BOTAO PLAY 1 CLIQUE */
  .btn-play {{ display: flex; align-items: center; justify-content: center; width: 100%; padding: 16px; background: linear-gradient(135deg, #00E5FF, #0088FF); color: #080B10; font-size: 16px; font-weight: 800; border-radius: 14px; text-decoration: none; border: none; cursor: pointer; box-shadow: 0 4px 15px rgba(0,229,255,0.4); margin-bottom: 12px; }}
  .btn-play:active {{ transform: scale(0.98); }}

  /* CARTOES DE COPIA */
  .field-box {{ background: #161B22; border: 1px solid #30363D; border-radius: 12px; padding: 12px 14px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }}
  .field-info {{ overflow: hidden; margin-right: 10px; }}
  .field-label {{ font-size: 11px; color: #8B949E; text-transform: uppercase; font-weight: 700; }}
  .field-val {{ font-size: 14px; color: #00E5FF; font-family: monospace; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .btn-copy {{ background: #21262D; color: #E6EDF3; border: 1px solid #30363D; padding: 8px 14px; border-radius: 8px; font-size: 12px; font-weight: 700; cursor: pointer; display: flex; align-items: center; gap: 4px; flex-shrink: 0; }}
  .btn-copy:active {{ background: #00E5FF; color: #080B10; }}

  /* COPIA AUTOMATICA FEEDBACK */
  .toast {{ position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: #2EA043; color: #fff; padding: 10px 20px; border-radius: 30px; font-size: 13px; font-weight: bold; opacity: 0; transition: opacity 0.3s; pointer-events: none; z-index: 1000; }}
  .toast.show {{ opacity: 1; }}

  /* APPS */
  .app-pill {{ display: flex; justify-content: space-between; align-items: center; background: #161B22; border: 1px solid #21262D; padding: 10px 14px; border-radius: 10px; margin-bottom: 8px; font-size: 13px; }}
  .app-code {{ background: #00E5FF; color: #080B10; padding: 4px 8px; border-radius: 6px; font-family: monospace; font-weight: 800; font-size: 12px; }}
</style>
</head>
<body>

<div class="container">
  <img src="/opt/data/nexus_playtv_bot/assets/nexus_playtv_banner.png" class="banner" alt="Nexus PlayTV">
  <div class="header">
    <h1>NEXUS PLAYTV • ACESSO VIP</h1>
    <p>Plano: <b>{plan_name}</b> • Validade: {valid_until}</p>
  </div>

  <!-- DADOS COM COPIAR COM 1 TOQUE -->
  <div class="section">
    <div style="font-size: 13px; font-weight: bold; color: #E6EDF3; margin-bottom: 12px;">📺 CONFIGURAR NA SMART TV OU NO SEU PLAYER FAVORITO:</div>
    
    <div class="field-box">
      <div class="field-info">
        <div class="field-label">Servidor / DNS</div>
        <div class="field-val" id="dns_val">{server_url}</div>
      </div>
      <button class="btn-copy" onclick="copyText('{server_url}', 'Servidor')">📋 Copiar</button>
    </div>

    <div class="field-box">
      <div class="field-info">
        <div class="field-label">Usuário</div>
        <div class="field-val" id="user_val">{username}</div>
      </div>
      <button class="btn-copy" onclick="copyText('{username}', 'Usuário')">📋 Copiar</button>
    </div>

    <div class="field-box">
      <div class="field-info">
        <div class="field-label">Senha</div>
        <div class="field-val" id="pass_val">{password}</div>
      </div>
      <button class="btn-copy" onclick="copyText('{password}', 'Senha')">📋 Copiar</button>
    </div>

    <div class="field-box">
      <div class="field-info">
        <div class="field-label">Lista M3U Completa</div>
        <div class="field-val" id="m3u_val">{m3u_url}</div>
      </div>
      <button class="btn-copy" onclick="copyText('{m3u_url}', 'Lista M3U')">📋 Copiar</button>
    </div>
  </div>

  <!-- COMO INSTALAR NOS PRINCIPAIS APARELHOS -->
  <div class="section">
    <div style="font-size: 13px; font-weight: bold; color: #E6EDF3; margin-bottom: 10px;">📱 COMO ASSISTIR NOS SEUS APARELHOS:</div>
    <div class="app-pill">
      <span>Smart TV Samsung ou LG</span>
      <span class="app-code">FUNPLAYS / MAGIC PLAY</span>
    </div>
    <p style="font-size: 11px; color: #8B949E; margin-bottom: 8px;">Instale o app na loja da TV, clique em <b>Ativar na Smart TV</b> no Telegram e mande a foto da tela.</p>

    <div class="app-pill">
      <span>Android TV / TV Box / Fire Stick</span>
      <span class="app-code">DOWNLOADER: 3054398</span>
    </div>
    <p style="font-size: 11px; color: #8B949E; margin-bottom: 8px;">Abra o app <b>Downloader</b>, digite o código <b>3054398</b> e instale o player direto.</p>

    <div class="app-pill">
      <span>Celular Android ou iPhone</span>
      <span class="app-code">PLAY STORE / APP STORE</span>
    </div>
    <p style="font-size: 11px; color: #8B949E; margin-bottom: 8px;">Baixe <b>IPTV Smarters Pro</b> ou <b>XCIPTV</b> e entre com Servidor, Usuário e Senha acima.</p>

    <div style="font-size: 12px; color: #8B949E; margin-top: 12px; line-height: 1.7;">
      Servidores oficiais: <b style="color:#00E5FF;">{SERVER_DNS_PRIMARY}</b> (principal) e
      <b style="color:#00E5FF;">{SERVER_DNS_ALT}</b> (alternativo)
    </div>
  </div>
</div>

<div id="toast" class="toast">Copiado para a área de transferência!</div>

<script>
function copyText(txt, name) {{
  navigator.clipboard.writeText(txt).then(() => {{
    const toast = document.getElementById('toast');
    toast.innerText = name + ' copiado!';
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 2000);
  }}).catch(() => {{
    prompt('Copie o texto:', txt);
  }});
}}
</script>

</body>
</html>"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("HTML Interativo gerado:", output_path)

if __name__ == "__main__":
    generate_interactive_html(
        "/opt/data/nexus_playtv_bot/assets/acesso_vip.html",
        username="nexus_vip_7894",
        password="play_pass_2026",
        server_url="http://cdn.nexusplay.tv:8080",
        m3u_url="http://cdn.nexusplay.tv:8080/get.php?username=nexus_vip_7894&password=play_pass_2026&type=m3u_plus",
        plan_name="Pass Final de Semana 48h",
        valid_until="14/09/2026 às 21:00"
    )
