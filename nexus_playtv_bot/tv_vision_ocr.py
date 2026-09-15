import os
import re
import json
import base64
import requests
import logging

logger = logging.getLogger("tv_ocr")


def get_google_key():
    key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not key and os.path.exists("/opt/data/.env"):
        try:
            with open("/opt/data/.env") as f:
                for line in f:
                    if line.startswith("GOOGLE_API_KEY=") or line.startswith("GEMINI_API_KEY="):
                        key = line.strip().split("=", 1)[1].strip("\"'")
                        if key:
                            break
        except Exception:
            pass
    return key


PROMPT = (
    "Voce recebeu uma imagem enviada por um cliente de IPTV. Ela pode conter:\n"
    "(a) a tela de ativacao de um aplicativo de IPTV na TV, ou\n"
    "(b) um print/screenshot do Telegram que por sua vez contem essa foto da TV.\n\n"
    "Sua tarefa: extrair TODO o texto legivel da tela do aplicativo de IPTV.\n\n"
    "Extraia especificamente, quando existirem:\n"
    "1. mac: o endereco MAC / Device ID da TV (12 caracteres hexadecimais, ex: 04:B9:E3:BE:57:5C).\n"
    "2. key: o Device Key / 'Your Current Code' / codigo de ativacao (numerico ou alfanumerico).\n"
    "3. app_name: o nome do aplicativo exatamente como aparece (ex: 'IBO Player', 'IBO PRO TV').\n"
    "4. site: qualquer dominio/URL citado na tela (ex: ibotv.pro, iboplayer.com, iboiiptv.com).\n"
    "5. screen_text: transcricao completa do texto visivel da tela do app de IPTV.\n\n"
    "ATENCAO MAXIMA AOS CARACTERES: nao confunda '3' com '9', nem 'B' com '8', nem '0' com 'O', "
    "nem '5' com 'S'. Leia letra por letra se necessario.\n\n"
    "Se um campo nao existir na tela, retorne null nele (NAO invente).\n"
    "Retorne ESTRITAMENTE um JSON puro, sem markdown:\n"
    '{"mac": "04:B9:E3:BE:57:5C", "key": null, "app_name": "IBO PRO TV", "site": "ibotv.pro", "screen_text": "..."}'
)

MAC_RE = re.compile(r"\b([0-9A-Fa-f]{2}(?::|-)?){5}[0-9A-Fa-f]{2}\b")


def _normalize_mac(raw):
    if not raw:
        return None
    digits = re.sub(r"[^0-9A-Fa-f]", "", str(raw))
    if len(digits) != 12:
        return None
    return ":".join(digits[i:i + 2] for i in range(0, 12, 2)).lower()


def _fallback_from_text(text):
    """Rede de seguranca: se o modelo nao devolver mac no campo certo, procura no texto."""
    m = MAC_RE.search(text or "")
    return m.group(0) if m else None


def extract_tv_codes_from_image(image_path: str) -> dict:
    """
    Envia a foto da TV para o Gemini Flash (Google AI Studio) e extrai
    MAC / Device Key / app / dominio. Retorna dados PARCIAIS quando existirem
    (ex: MAC presente mas sem Device Key na tela), para o bot poder orientar
    o cliente em vez de apenas dizer 'nao consegui ler'.
    """
    key = get_google_key()
    if not key:
        return {"success": False, "error": "Chave de visao nao configurada"}

    try:
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
    except Exception as e:
        return {"success": False, "error": f"Falha ao ler a imagem: {e}"}

    mime = "image/png" if image_path.lower().endswith(".png") else "image/jpeg"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
    payload = {
        "contents": [{
            "parts": [
                {"text": PROMPT},
                {"inline_data": {"mime_type": mime, "data": img_b64}}
            ]
        }],
        "generationConfig": {
            "temperature": 0.0,
            "response_mime_type": "application/json"
        }
    }

    last_err = None
    for attempt in range(3):
        try:
            resp = requests.post(url, json=payload, timeout=45)
            if resp.status_code != 200:
                last_err = f"Gemini HTTP {resp.status_code}: {resp.text[:200]}"
                continue

            res_json = resp.json()
            candidates = res_json.get("candidates", [])
            if not candidates:
                last_err = "Nenhuma resposta gerada pelo modelo"
                continue

            text_out = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")

            # Limpa cercas de markdown caso o modelo as insira
            clean = text_out.strip()
            clean = re.sub(r"^```(?:json)?", "", clean).strip()
            clean = re.sub(r"```$", "", clean).strip()

            try:
                data = json.loads(clean)
            except Exception:
                # Ultimo recurso: pega o primeiro objeto {...} do texto
                mm = re.search(r"\{.*\}", clean, re.DOTALL)
                data = json.loads(mm.group(0)) if mm else {}

            screen_text = data.get("screen_text") or ""
            raw_mac = data.get("mac") or _fallback_from_text(screen_text)
            mac = _normalize_mac(raw_mac)
            key_val = data.get("key")
            if key_val is not None:
                key_val = str(key_val).strip()
                if key_val.lower() in ("null", "none", "", "n/a", "na"):
                    key_val = None
            if key_val:
                key_val = re.sub(r"[^0-9A-Za-z]", "", key_val)

            app_name = (data.get("app_name") or "").strip() or None
            site = (data.get("site") or "").strip().lower() or None
            if site:
                site = re.sub(r"^https?://", "", site).strip("/ ")
            # Detecta dominio no texto da tela, se o modelo nao informou
            if not site:
                dm = re.search(r"\b((?:[a-z0-9-]+\.)+(?:com|pro|tv|io|net|app|org))\b", (screen_text or "").lower())
                site = dm.group(1) if dm else None

            return {
                "success": bool(mac and key_val),
                "mac": mac,
                "key": key_val,
                "app_name": app_name,
                "site": site,
                "screen_text": screen_text[:1500],
                "raw": clean[:1500],
                "error": None if (mac and key_val) else "Dados incompletos na tela",
            }
        except Exception as e:
            last_err = str(e)
            logger.warning(f"[OCR] tentativa {attempt + 1}/3 falhou: {e}")

    logger.error(f"Erro no OCR Gemini apos 3 tentativas: {last_err}")
    return {"success": False, "error": last_err}


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(json.dumps(extract_tv_codes_from_image(sys.argv[1]), ensure_ascii=False, indent=2))
    else:
        print("Uso: python tv_vision_ocr.py <caminho_da_imagem>")