"""
Roteador unico de ativacao de Smart TV.

Recebe o resultado do OCR (MAC, Device Key, app, dominio visto na tela) e
escolhe automaticamente o backend correto de injecao de playlist:

  - funplays.app   -> API FunPlays        (MAC + Chave do dispositivo)
  - iptv.app / siptv / my.iptv.app -> portal Smart IPTV (somente MAC)
  - iboplayer.com  -> API IBO Player      (MAC + Device Key)
  - ibotv.pro      -> app de credito pre-pago (nao suportado)

Quando o aplicativo nao e identificado, os backends sao tentados em sequencia.
"""
import logging

logger = logging.getLogger("tv_activator")

APP_NAMES = {
    "funplays": "FunPlays",
    "siptv": "Smart IPTV (SIPTV)",
    "ibo": "IBO Player",
    "ibopro": "IBO PRO TV",
    "smartone": "SmartOne IPTV",
    "vizzion": "Vizzion Play",
}


def detect_app(site: str, app_name: str) -> str:
    site = (site or "").lower().strip()
    app_name = (app_name or "").lower()

    # Chave interna de backend ja resolvida anteriormente (ex: sessao em andamento)
    if site in APP_NAMES:
        return site

    if "vizzion" in site or "vizzion" in app_name:
        return "vizzion"
    if "funplays" in site:
        return "funplays"
    if "ibotv" in site or "iboprotv" in site or "pro tv" in app_name:
        return "ibopro"
    if "iboplayer" in site or "iboiiptv" in site or "ibo player" in app_name or app_name == "ibo":
        return "ibo"
    if "iptv.app" in site or "siptv" in site or "ss-iptv" in site:
        return "siptv"
    if "one" in app_name:
        return "smartone"
    return "unknown"


def activate_tv(mac: str, key: str, playlist_url: str, site: str = "", app_name: str = "",
                playlist_name: str = "Nexus PlayTV VIP") -> dict:
    """
    Executa a ativacao no backend adequado.
    Retorna {"success": bool, "message": str, "app": str, "app_label": str}
    """
    app = detect_app(site, app_name)
    logger.info(f"[TV-ACTIVATOR] app detectado={app} mac={mac} key={'sim' if key else 'nao'}")

    def _label(a):
        return APP_NAMES.get(a, a)

    # App de credito pre-pago: nao ha injecao possivel
    if app == "ibopro":
        return {
            "success": False,
            "app": app,
            "app_label": _label(app),
            "message": "Este aplicativo (IBO PRO TV) exige codigo de ativacao pago no site ibotv.pro "
                       "e nao aceita injecao de lista. Instale outro player."
        }

    # Vizzion Play: aplicativo com login por Usuario e Senha na aba USER
    if app == "vizzion":
        return {
            "success": False,
            "app": app,
            "app_label": _label(app),
            "message": "O *Vizzion Play* no Android utiliza login direto por Usuário e Senha!\n\n"
                       "👉 Na tela do app, selecione a aba **USER** e digite o seu Usuário e Senha fornecidos no seu plano/teste. "
                       "A grade de canais e filmes conecta na hora sem precisar de ativação web."
        }

    # 1. Backend identificado com certeza
    if app == "funplays":
        from funplays_injector import inject_playlist_funplays
        res = inject_playlist_funplays(mac, key, playlist_url, playlist_name)
        res.update({"app": app, "app_label": _label(app)})
        return res

    if app == "siptv":
        from siptv_injector import inject_playlist_siptv
        res = inject_playlist_siptv(mac, playlist_url)
        res.update({"app": app, "app_label": _label(app)})
        return res

    if app == "ibo":
        from ibo_injector import activate_smart_tv_ibo
        res = activate_smart_tv_ibo(mac, key, playlist_name, playlist_url)
        res.update({"app": app, "app_label": _label(app)})
        return res

    # 2. App desconhecido: tenta os backends na ordem mais provavel
    tentativas = []
    if key:
        tentativas.append(("funplays", lambda: __import__("funplays_injector").inject_playlist_funplays(mac, key, playlist_url, playlist_name)))
        tentativas.append(("ibo", lambda: __import__("ibo_injector").activate_smart_tv_ibo(mac, key, playlist_name, playlist_url)))
    tentativas.append(("siptv", lambda: __import__("siptv_injector").inject_playlist_siptv(mac, playlist_url)))

    ultimo_erro = "Nenhum backend conseguiu ativar este aplicativo"
    for nome, fn in tentativas:
        try:
            res = fn()
        except Exception as e:
            logger.warning(f"[TV-ACTIVATOR] backend {nome} levantou excecao: {e}")
            ultimo_erro = str(e)
            continue

        if res.get("success"):
            res.update({"app": nome, "app_label": _label(nome), "auto_detect": True})
            logger.info(f"[TV-ACTIVATOR] sucesso via backend {nome}")
            return res
        ultimo_erro = res.get("message") or ultimo_erro
        logger.info(f"[TV-ACTIVATOR] backend {nome} falhou: {ultimo_erro}")

    return {
        "success": False,
        "app": "unknown",
        "app_label": "Aplicativo nao identificado",
        "message": ultimo_erro,
    }


if __name__ == "__main__":
    import json
    import sys
    m = sys.argv[1] if len(sys.argv) > 1 else "00:00:00:00:00:00"
    k = sys.argv[2] if len(sys.argv) > 2 else ""
    u = sys.argv[3] if len(sys.argv) > 3 else "http://example.com/list.m3u"
    s = sys.argv[4] if len(sys.argv) > 4 else ""
    print(json.dumps(activate_tv(m, k, u, site=s), ensure_ascii=False, indent=2))
