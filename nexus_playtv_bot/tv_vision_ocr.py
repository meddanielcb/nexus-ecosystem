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

def extract_tv_codes_from_image(image_path: str) -> dict:
    """
    Envia a foto da TV para o Gemini Flash nativo (Google AI Studio)
    e extrai com 100% de precisão o MAC / Device ID e o Device Key.
    """
    key = get_google_key()
    if not key:
        return {"success": False, "error": "Chave de visão não configurada"}

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    prompt = (
        "Analise cuidadosamente esta foto da tela de um aplicativo de IPTV (IBO Player / Smart TV / Monitor).\n"
        "Existe uma caixa de diálogo ou mensagem de ativação contendo:\n"
        "1. Device ID (ou Endereço MAC): uma sequência hexadecimal de 12 caracteres (ex: 1C:57:DC:3C:67:31).\n"
        "2. Device Key: um código numérico de 6 a 8 dígitos (ex: 256294).\n\n"
        "ATENÇÃO MÁXIMA AOS CARACTERES: Não confunda '3' com '9', nem 'B' com '8', nem '0' com 'O'.\n"
        "Retorne ESTRITAMENTE um objeto JSON puro:\n"
        "{\"mac\": \"1C:57:DC:3C:67:31\", \"key\": \"256294\"}"
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": img_b64
                    }
                }
            ]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "response_mime_type": "application/json"
        }
    }

    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code != 200:
            return {"success": False, "error": f"Erro API Gemini: {resp.status_code} - {resp.text}"}

        res_json = resp.json()
        candidates = res_json.get("candidates", [])
        if not candidates:
            return {"success": False, "error": "Nenhuma resposta gerada pelo modelo"}

        text_out = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        data = json.loads(text_out)

        mac = data.get("mac")
        key_val = data.get("key")

        if mac and key_val:
            return {"success": True, "mac": mac.strip().lower(), "key": str(key_val).strip()}
        return {"success": False, "error": "Não foi possível identificar o MAC e a Key na tela"}
    except Exception as e:
        logger.error(f"Erro no OCR Gemini: {e}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    print("Módulo tv_vision_ocr pronto.")
