import os
import qrcode
import base64
from io import BytesIO

def generate_interactive_html(output_path, username, password, server_url, m3u_url, plan_name, valid_until):
    # Gerar QR Code em Base64
    qr = qrcode.QRCode(box_size=6, border=1)
    qr.add_data(m3u_url if m3u_url else f"{server_url}/get.php?username={username}&password={password}&type=m3u_plus")
    qr.make(fit=True)
    buf = BytesIO()
    qr.make_image(fill_color="#000000", back_color="#FFFFFF").save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Nexus PlayTV • Cartão VIP</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=Barlow+Condensed:wght@600;700&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #050607; color: #F5F7F4; font-family: 'Space Grotesk', -apple-system, sans-serif; display: flex; justify-content: center; padding: 20px 14px; min-height: 100vh; }}
  .card {{ width: 100%; max-width: 460px; background: #0A0D0E; border: 1px solid #1A2226; border-radius: 20px; overflow: hidden; box-shadow: 0 16px 40px rgba(0,0,0,0.85); }}
  
  /* HEADER COM LOGO OFICIAL */
  .header {{ padding: 28px 24px 22px; text-align: center; background: linear-gradient(180deg, #101614 0%, #0A0D0E 100%); border-bottom: 1px solid #16201B; position: relative; }}
  .logo-box {{ display: inline-flex; align-items: center; gap: 10px; margin-bottom: 14px; }}
  .logo-box svg {{ width: 32px; height: 32px; }}
  .logo-box span {{ font-family: 'Space Grotesk', sans-serif; font-size: 24px; font-weight: 700; letter-spacing: 2px; color: #FFFFFF; }}
  .logo-box small {{ color: #B7FF3C; font-size: 24px; font-weight: 700; margin-left: 2px; }}
  
  .badge {{ display: inline-block; background: rgba(183, 255, 60, 0.12); color: #B7FF3C; border: 1px solid rgba(183, 255, 60, 0.3); font-size: 11px; font-weight: 700; letter-spacing: 1.5px; padding: 5px 12px; border-radius: 20px; text-transform: uppercase; }}
  .plan-info {{ font-size: 14px; color: #8F9E9D; margin-top: 10px; }}
  .plan-info b {{ color: #FFFFFF; }}

  /* SECTIONS */
  .section {{ padding: 20px 22px; border-bottom: 1px solid #141B18; }}
  .sec-title {{ font-size: 12px; font-weight: 700; color: #8F9E9D; letter-spacing: 1.2px; text-transform: uppercase; margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }}
  .sec-title span {{ color: #B7FF3C; }}

  /* CAMPOS DE CREDENCIAIS */
  .field-box {{ background: #0F1517; border: 1px solid #1B2628; border-radius: 12px; padding: 12px 14px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; transition: border-color 0.2s; }}
  .field-box:hover {{ border-color: #B7FF3C50; }}
  .field-info {{ overflow: hidden; margin-right: 12px; }}
  .field-label {{ font-size: 10px; color: #738483; text-transform: uppercase; font-weight: 700; letter-spacing: 0.8px; margin-bottom: 3px; }}
  .field-val {{ font-size: 15px; color: #B7FF3C; font-family: monospace; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  
  .btn-copy {{ background: #162022; color: #FFFFFF; border: 1px solid #283739; padding: 8px 14px; border-radius: 8px; font-size: 12px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 5px; flex-shrink: 0; transition: all 0.15s; }}
  .btn-copy:active {{ background: #B7FF3C; color: #050607; border-color: #B7FF3C; transform: scale(0.96); }}

  /* GUIA DE CONEXÃO SMART TV */
  .tv-guide {{ background: #0D1412; border: 1px solid #1A2E20; border-radius: 12px; padding: 14px; margin-top: 14px; }}
  .tv-guide h4 {{ font-size: 13px; color: #B7FF3C; font-weight: 700; margin-bottom: 6px; }}
  .tv-guide p {{ font-size: 12px; color: #9AB2A2; line-height: 1.5; }}

  /* APPS */
  .app-item {{ display: flex; justify-content: space-between; align-items: center; background: #0F1517; border: 1px solid #182224; padding: 11px 14px; border-radius: 10px; margin-bottom: 8px; }}
  .app-item span {{ font-size: 13px; color: #DDE5E2; font-weight: 500; }}
  .app-badge {{ background: #18261F; color: #B7FF3C; border: 1px solid #B7FF3C40; padding: 4px 10px; border-radius: 6px; font-family: monospace; font-weight: 700; font-size: 11px; letter-spacing: 0.5px; }}

  /* QR CODE */
  .qr-box {{ text-align: center; padding: 22px; }}
  .qr-box img {{ width: 140px; height: 140px; border-radius: 12px; padding: 6px; background: #FFFFFF; border: 2px solid #B7FF3C; }}
  .qr-label {{ font-size: 11px; color: #738483; margin-top: 10px; }}

  /* TOAST */
  .toast {{ position: fixed; bottom: 25px; left: 50%; transform: translateX(-50%); background: #B7FF3C; color: #050607; padding: 11px 22px; border-radius: 30px; font-size: 13px; font-weight: 700; opacity: 0; transition: opacity 0.25s, transform 0.25s; pointer-events: none; z-index: 1000; box-shadow: 0 8px 24px rgba(183,255,60,0.3); }}
  .toast.show {{ opacity: 1; transform: translate(-50%, -5px); }}
</style>
</head>
<body>

<div class="card">
  <div class="header">
    <div class="logo-box">
      <svg viewBox="0 0 34 35" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M4 4L12 8V31L4 27V4Z" fill="#B7FF3C"/>
        <path d="M22 4L30 8V31L22 27V4Z" fill="#B7FF3C"/>
        <path d="M12 8L22 27H16L6 9L12 8Z" fill="#B7FF3C" fill-opacity="0.8"/>
      </svg>
      <span>NEXUS<small>PLAYTV</small></span>
    </div>
    <div><span class="badge">CARTÃO VIP OFICIAL</span></div>
    <div class="plan-info">Plano: <b>{plan_name}</b> • Validade: <b>{valid_until}</b></div>
  </div>

  <!-- CREDENCIAIS EXATAS (TV E APP) -->
  <div class="section">
    <div class="sec-title"><span>01</span> DADOS PARA LOGIN NA SMART TV & APPS</div>

    <div class="field-box">
      <div class="field-info">
        <div class="field-label">CÓDIGO PARCEIRO</div>
        <div class="field-val" id="code_val">00042</div>
      </div>
      <button class="btn-copy" onclick="copyText('00042', 'Código')">📋 Copiar</button>
    </div>

    <div class="field-box">
      <div class="field-info">
        <div class="field-label">USUÁRIO</div>
        <div class="field-val" id="user_val">{username}</div>
      </div>
      <button class="btn-copy" onclick="copyText('{username}', 'Usuário')">📋 Copiar</button>
    </div>

    <div class="field-box">
      <div class="field-info">
        <div class="field-label">SENHA</div>
        <div class="field-val" id="pass_val">{password}</div>
      </div>
      <button class="btn-copy" onclick="copyText('{password}', 'Senha')">📋 Copiar</button>
    </div>

    <div class="field-box">
      <div class="field-info">
        <div class="field-label">SERVIDOR / URL XTREAM CODES</div>
        <div class="field-val" id="dns_val">{server_url}</div>
      </div>
      <button class="btn-copy" onclick="copyText('{server_url}', 'Servidor')">📋 Copiar</button>
    </div>

    <div class="tv-guide">
      <h4>⚡ Dica para Smart TV Samsung / LG:</h4>
      <p>Nos apps como <b>XCIPTV</b> ou parceiros com código, digite <b>00042</b>, seguido de Usuário e Senha. Em apps como <b>FunPlays</b> ou <b>IBO Player</b>, use o Servidor, Usuário e Senha acima ou ative por foto.</p>
    </div>
  </div>

  <!-- APLICATIVOS COMPATÍVEIS -->
  <div class="section">
    <div class="sec-title"><span>02</span> ONDE ASSISTIR</div>
    
    <div class="app-item">
      <span>Smart TV Samsung ou LG</span>
      <span class="app-badge">FUNPLAYS / IBO PLAYER</span>
    </div>

    <div class="app-item">
      <span>Android TV / Fire Stick / TV Box</span>
      <span class="app-badge">DOWNLOADER: 3054398</span>
    </div>

    <div class="app-item">
      <span>Celular Android & iPhone</span>
      <span class="app-badge">IPTV SMARTERS PRO / XCIPTV</span>
    </div>
  </div>

  <!-- QR CODE DE CONEXÃO RÁPIDA -->
  <div class="qr-box">
    <img src="data:image/png;base64,{qr_b64}" alt="QR Code VIP">
    <div class="qr-label">Escaneie com a câmera do celular para carregar a lista completa</div>
  </div>
</div>

<div id="toast" class="toast">Copiado com sucesso!</div>

<script>
function copyText(txt, name) {{
  if (navigator.clipboard && window.isSecureContext) {{
    navigator.clipboard.writeText(txt).then(() => showToast(name + ' copiado!')).catch(() => fallbackCopy(txt, name));
  }} else {{
    fallbackCopy(txt, name);
  }}
}}

function fallbackCopy(txt, name) {{
  const ta = document.createElement('textarea');
  ta.value = txt;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.select();
  try {{
    document.execCommand('copy');
    showToast(name + ' copiado!');
  }} catch(e) {{
    prompt('Copie o texto:', txt);
  }}
  document.body.removeChild(ta);
}}

function showToast(msg) {{
  const toast = document.getElementById('toast');
  toast.innerText = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 2000);
}}
</script>

</body>
</html>"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("HTML Interativo gerado com sucesso:", output_path)

if __name__ == "__main__":
    generate_interactive_html(
        "/opt/data/nexus_repo/nexus_playtv_bot/assets/acesso_vip.html",
        username="nexus_vip_7894",
        password="play_pass_2026",
        server_url="http://atmt.space",
        m3u_url="http://atmt.space/get.php?username=nexus_vip_7894&password=play_pass_2026&type=m3u_plus",
        plan_name="Anual VIP",
        valid_until="17/09/2027"
    )
