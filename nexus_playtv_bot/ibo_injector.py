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
    Fluxo 100% autônomo:
    1. Obtém SVG de captcha fresco do IBO Player
    2. Converte SVG -> PNG
    3. Resolve via 2Captcha
    4. Realiza login autenticado (POST /frontend/device/login)
    5. Injeta playlist M3U (POST /frontend/device/savePlaylist)
    """
    api_key = get_2captcha_key()
    if not api_key:
        return {"success": False, "message": "Chave 2Captcha não configurada"}
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json",
        "X-Client-Origin": "https://iboplayer.com"
    }
    
    # Normalizar MAC
    mac = mac_address.strip().lower()
    key = device_key.strip()
    
    # Passo 1: Pegar Captcha
    try:
        cap_resp = requests.get("https://iboplayer.com/frontend/captcha/generate", headers=headers, timeout=10).json()
        captcha_token = cap_resp.get("token")
        svg_content = cap_resp.get("svg")
        if not captcha_token or not svg_content:
            return {"success": False, "message": "Falha ao obter captcha do servidor IBO"}
            
        # Converte SVG para PNG
        doc = fitz.open(stream=svg_content.encode("utf-8"), filetype="svg")
        pix = doc[0].get_pixmap()
        png_bytes = pix.tobytes("png")
    except Exception as e:
        return {"success": False, "message": f"Erro processando captcha: {e}"}
        
    # Passo 2: Resolver Captcha com 2Captcha
    try:
        captcha_text = solve_captcha_image(png_bytes, api_key)
    except Exception as e:
        return {"success": False, "message": f"Falha no 2Captcha: {e}"}
        
    # Passo 3: Login na API do IBO
    login_body = {
        "mac_address": mac,
        "device_key": key,
        "captcha": captcha_text,
        "token": captcha_token
    }
    
    try:
        login_res = requests.post("https://iboplayer.com/frontend/device/login", json=login_body, headers=headers, timeout=15)
        login_data = login_res.json()
        
        if login_res.status_code != 200 or not login_data.get("token"):
            msg = login_data.get("message") or "MAC ou Device Key incorretos na TV"
            return {"success": False, "message": msg}
            
        jwt_token = login_data["token"]
        device_id = (login_data.get("device") or {}).get("_id")
        
        # Passo 4: Salvar Playlist M3U diretamente na TV
        auth_headers = dict(headers)
        auth_headers["Authorization"] = f"Bearer {jwt_token}"
        
        playlist_body = {
            "device_id": device_id,
            "playlist_name": playlist_name or "Nexus PlayTV VIP",
            "playlist_url": playlist_url,
            "protect": 0
        }
        
        save_res = requests.post("https://iboplayer.com/frontend/device/savePlaylist", json=playlist_body, headers=auth_headers, timeout=15)
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
    except Exception as e:
        return {"success": False, "message": f"Erro de comunicação com IBO Player: {e}"}
