import logging
import requests

logger = logging.getLogger("funplays_injector")

API_BASE = "https://api.funplays.app/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def inject_playlist_funplays(mac_address: str, device_key: str, playlist_url: str,
                             playlist_name: str = "Nexus PlayTV VIP") -> dict:
    """
    Injeta playlist M3U no aplicativo FunPlays (funplays.app) via API oficial.

    Fluxo verificado em producao:
      1. POST /api/login_by_mac  {"mac": ..., "key": ...}  -> JWT
      2. POST /api/playlist      {"name","url","mac"} + Bearer -> playlist gravada na TV
    """
    mac = (mac_address or "").strip().lower()
    key = "".join(ch for ch in str(device_key or "") if ch.isalnum())

    if not mac or not key:
        return {"success": False, "message": "MAC e Chave do dispositivo sao obrigatorios"}

    headers = {"User-Agent": UA, "Content-Type": "application/json"}

    try:
        # 1. Autenticacao por MAC + Device Key
        r_login = requests.post(
            f"{API_BASE}api/login_by_mac",
            json={"mac": mac, "key": key},
            headers=headers,
            timeout=20,
        )
        try:
            login_data = r_login.json()
        except Exception:
            return {"success": False, "message": f"Resposta invalida do servidor FunPlays (HTTP {r_login.status_code})"}

        token = login_data.get("message")
        if not token or login_data.get("error"):
            msg = login_data.get("message") or "MAC ou Chave do dispositivo incorretos"
            if isinstance(msg, str) and msg.count(".") > 2:
                msg = "MAC ou Chave do dispositivo incorretos"
            return {"success": False, "message": msg}

        auth_headers = dict(headers)
        auth_headers["Authorization"] = f"Bearer {token}"

        # 2. Grava a playlist na TV
        r_add = requests.post(
            f"{API_BASE}api/playlist",
            json={"name": playlist_name, "url": playlist_url, "mac": mac},
            headers=auth_headers,
            timeout=25,
        )
        try:
            add_data = r_add.json()
        except Exception:
            return {"success": False, "message": f"Resposta invalida ao gravar playlist (HTTP {r_add.status_code})"}

        if add_data.get("error"):
            return {"success": False, "message": add_data.get("message") or "Falha ao gravar a playlist"}

        playlist = add_data.get("message") or {}
        return {
            "success": True,
            "message": "Playlist gravada com sucesso no FunPlays",
            "playlist_id": playlist.get("id"),
            "details": playlist,
        }

    except requests.exceptions.Timeout:
        return {"success": False, "message": "Tempo esgotado ao conectar no servidor do FunPlays"}
    except Exception as e:
        logger.error(f"Erro na injecao FunPlays: {e}")
        return {"success": False, "message": str(e)}


if __name__ == "__main__":
    import json
    import sys
    mac = sys.argv[1] if len(sys.argv) > 1 else "00:00:00:00:00:00"
    key = sys.argv[2] if len(sys.argv) > 2 else "000000"
    url = sys.argv[3] if len(sys.argv) > 3 else "http://example.com/list.m3u"
    print(json.dumps(inject_playlist_funplays(mac, key, url), ensure_ascii=False, indent=2))
