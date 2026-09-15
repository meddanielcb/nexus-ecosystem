import os
import json
import time
import base64
import requests
import fitz # PyMuPDF para renderizar SVG para PNG

CONFIG_FILE = "/opt/data/nexus_playtv_bot/config_keys.json"

def get_2captcha_key():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f).get("twocaptcha_api_key", "")
        except Exception:
            pass
    return os.getenv("TWOCAPTCHA_API_KEY", "")

def solve_captcha_image(png_bytes: bytes, api_key: str) -> str:
    """Envia o PNG para o 2Captcha e aguarda a resposta resolvida"""
    b64_img = base64.b64encode(png_bytes).decode("utf-8")
    
    # 1. Enviar imagem
    in_url = "https://2captcha.com/in.php"
    payload = {
        "key": api_key,
        "method": "base64",
        "body": b64_img,
        "json": 1,
        "regsense": 1, # Case sensitive se aplicável
        "numeric": 0,
        "min_len": 2,
        "max_len": 6
    }
    resp = requests.post(in_url, data=payload, timeout=15).json()
    if resp.get("status") != 1:
        raise ValueError(f"2Captcha In Error: {resp.get('request')}")
    
    req_id = resp["request"]
    
    # 2. Polling do resultado (geralmente 3 a 8 segundos)
    res_url = f"https://2captcha.com/res.php?key={api_key}&action=get&id={req_id}&json=1"
    for _ in range(15):
        time.sleep(3)
        r = requests.get(res_url, timeout=10).json()
        if r.get("status") == 1:
            return r.get("request", "").strip().upper()
        if r.get("request") != "CAPCHA_NOT_READY":
            raise ValueError(f"2Captcha Res Error: {r.get('request')}")
            
    raise TimeoutError("2Captcha timeout esperando resposta")

def activate_smart_tv_ibo(mac_address: str, device_key: str, playlist_name: str, playlist_url: str) -> dict:
    """
    Fluxo 100% autônomo com auto-retry de captcha (até 3 tentativas):
    1. Obtém SVG de captcha fresco do IBO Player
    2. Converte SVG -> PNG alta resolução
    3. Resolve via 2Captcha
    4. Realiza login autenticado (POST /frontend/device/login)
    5. Injeta playlist M3U com payload oficial (POST /frontend/device/savePlaylist)
    """
    api_key = get_2captcha_key()
    if not api_key:
        return {"success": False, "message": "Chave 2Captcha não configurada"}

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json",
        "X-Client-Origin": "https://iboplayer.com",
        "Origin": "https://iboplayer.com",
        "Referer": "https://iboplayer.com/device/playlists"
    }

    # Normalizar MAC
    mac = mac_address.strip().lower()
    key = device_key.strip()

    s = requests.Session()
    jwt_token = None
    login_data = {}

    for attempt in range(1, 4):
        try:
            cap_resp = s.get("https://iboplayer.com/frontend/captcha/generate", headers=headers, timeout=10).json()
            captcha_token = cap_resp.get("token")
            svg_content = cap_resp.get("svg")
            if not captcha_token or not svg_content:
                continue

            doc = fitz.open(stream=svg_content.encode("utf-8"), filetype="svg")
            pix = doc[0].get_pixmap(dpi=150)
            png_bytes = pix.tobytes("png")

            captcha_text = solve_captcha_image(png_bytes, api_key)

            login_body = {
                "mac_address": mac,
                "device_key": key,
                "captcha": captcha_text.strip().upper(),
                "token": captcha_token
            }

            login_res = s.post("https://iboplayer.com/frontend/device/login", json=login_body, headers=headers, timeout=15)
            login_data = login_res.json()

            if login_res.status_code == 200 and login_data.get("token"):
                jwt_token = login_data["token"]
                break
            else:
                logger.warning(f"[IBO Login] Tentativa {attempt}/3 falhou: {login_data.get('message')}")
        except Exception as e_att:
            logger.warning(f"[IBO Login] Exceção na tentativa {attempt}/3: {e_att}")

    if not jwt_token:
        msg = login_data.get("message") or "MAC ou Device Key incorretos na TV"
        return {"success": False, "message": msg}

    # Passo 4: Salvar Playlist M3U diretamente na TV (Payload oficial do IBO Player)
    auth_headers = dict(headers)
    auth_headers["Authorization"] = f"Bearer {jwt_token}"

    playlist_body = {
        "current_playlist_url_id": -1,
        "playlist_url": playlist_url,
        "playlist_name": playlist_name or "Nexus PlayTV VIP",
        "username": "",
        "password": "",
        "playlist_type": "general",
        "protect": "false",
        "xml_url": "",
        "pin": ""
    }

    save_res = s.post("https://iboplayer.com/frontend/device/savePlaylist", json=playlist_body, headers=auth_headers, timeout=15)
    save_data = save_res.json()

    # Validar resposta do IBO: {"status": "error"} vs {"status": "success"}
    if save_data.get("status") == "error" or not save_data.get("status"):
        msg = save_data.get("message") or "O IBO Player recusou salvar a lista M3U. Verifique se o Device ID/Key pertencem ao app oficial IBO Player."
        return {"success": False, "message": msg, "details": save_data}

    return {
        "success": True,
        "message": "Playlist ativada com sucesso na Smart TV!",
        "details": save_data
    }
