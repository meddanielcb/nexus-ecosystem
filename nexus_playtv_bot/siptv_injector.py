import os
import time
import logging
import requests

logger = logging.getLogger("siptv_injector")

CONFIG_FILE = "/opt/data/nexus_playtv_bot/config_keys.json"
SITE_KEY = "0x4AAAAAAAV669DUfYa30Xic"
PAGE_URL = "https://iptv.app/mylist/"


def get_2captcha_key():
    if os.path.exists(CONFIG_FILE):
        try:
            import json
            with open(CONFIG_FILE) as f:
                data = json.load(f)
                return data.get("twocaptcha_api_key")
        except Exception:
            pass
    return os.getenv("TWOCAPTCHA_API_KEY")


def inject_playlist_siptv(mac_address: str, playlist_url: str) -> dict:
    """
    Injeta playlist M3U diretamente no Smart IPTV (SIPTV / my.iptv.app)
    usando resolução de Cloudflare Turnstile via 2Captcha.
    Compatível com Smart TVs Samsung (Tizen), LG (webOS) e Android.
    """
    api_key = get_2captcha_key()
    if not api_key:
        return {"success": False, "message": "Chave 2Captcha não configurada"}

    mac_clean = mac_address.lower().strip()

    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": PAGE_URL,
            "Origin": "https://iptv.app",
            "X-Requested-With": "XMLHttpRequest"
        })

        # 1. Carregar página inicial para inicializar sessão
        session.get(PAGE_URL, timeout=15)
        session.cookies.set("origin", "valid", domain="iptv.app", path="/")

        # 2. Solicitar resolução do Turnstile ao 2Captcha
        in_url = f"https://2captcha.com/in.php?key={api_key}&method=turnstile&sitekey={SITE_KEY}&pageurl={PAGE_URL}&json=1"
        r1 = requests.get(in_url, timeout=15).json()
        if r1.get("status") != 1:
            return {"success": False, "message": f"Erro 2Captcha in.php: {r1.get('request')}"}

        req_id = r1["request"]

        # 3. Polling do token Turnstile
        token = None
        for _ in range(15):
            time.sleep(4)
            r2 = requests.get(f"https://2captcha.com/res.php?key={api_key}&action=get&id={req_id}&json=1", timeout=10).json()
            if r2.get("status") == 1:
                token = r2["request"]
                break

        if not token:
            return {"success": False, "message": "Tempo limite excedido ao resolver verificação da TV"}

        session.cookies.set("captcha2", "1", domain="iptv.app", path="/")

        # 4. Envio do payload oficial para o backend do Smart IPTV
        payload = {
            "mac": mac_clean,
            "url1": playlist_url,
            "url_count": 1,
            "file_selected": 0,
            "epg_count": 0,
            "plist_order": 0,
            "xtream_explicit": 0,
            "keep": "on",
            "g-recaptcha-token": token,
            "cf-turnstile-response": token
        }

        up_res = session.post("https://iptv.app/scripts/up_file_url.php", data=payload, timeout=20)
        resp_text = up_res.text.strip()

        if "URL added" in resp_text or "saved" in resp_text.lower():
            return {
                "success": True,
                "message": resp_text
            }
        else:
            # Erros típicos: "MAC address is not found!", "MAC address is not activated!", etc.
            clean_msg = resp_text.replace("<br />", "").replace("<br>", "").strip()
            return {
                "success": False,
                "message": clean_msg or "Resposta inesperada do Smart IPTV"
            }

    except Exception as e:
        logger.error(f"Erro na injeção SIPTV: {e}")
        return {"success": False, "message": str(e)}


if __name__ == "__main__":
    import sys
    test_mac = sys.argv[1] if len(sys.argv) > 1 else "04:b9:e3:bc:5c:f0"
    test_url = "http://atmt.space/get.php?username=664142405&password=763378432&type=m3u_plus&output=ts"
    print(f"Testando injecao SIPTV no MAC {test_mac}...")
    res = inject_playlist_siptv(test_mac, test_url)
    print("Resultado:", res)