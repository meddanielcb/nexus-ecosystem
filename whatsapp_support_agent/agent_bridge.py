import os
import re
import json
import base64
import urllib.request
import logging

logger = logging.getLogger("agent_bridge")

PROMPT_PATH = "/opt/nexus_repo/whatsapp_support_agent/NEXUS_SUPPORT_SYSTEM_PROMPT.md"
MEDIA_DIR = "/opt/nexus_repo/whatsapp_support_agent/guides_media"

# Evolution API
EVOLUTION_URL = os.environ.get("EVOLUTION_URL", "http://127.0.0.1:8080")
EVOLUTION_INSTANCE = "nexus-playtv-1"

# Ler API Key da Evolution API
EVOLUTION_KEY = ""
try:
    with open("/opt/evolution-api/docker-compose.yml") as f:
        for line in f:
            if "AUTHENTICATION_API_KEY=" in line:
                EVOLUTION_KEY = line.split("=")[1].strip()
                break
except Exception:
    pass

def load_system_prompt():
    p = PROMPT_PATH if os.path.exists(PROMPT_PATH) else "/opt/data/nexus_repo/whatsapp_support_agent/NEXUS_SUPPORT_SYSTEM_PROMPT.md"
    try:
        with open(p, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "Você é a Lua, suporte do Nexus PlayTV. Seja breve, empática e despojada."

def send_whatsapp_text(remote_jid: str, text: str):
    clean_number = remote_jid.split("@")[0]
    url = f"{EVOLUTION_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    headers = {"apikey": EVOLUTION_KEY, "Content-Type": "application/json"}
    payload = {
        "number": clean_number,
        "options": {"delay": 1200, "presence": "composing"},
        "textMessage": {"text": text}
    }
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status in [200, 201]
    except Exception as e:
        logger.error(f"Erro ao enviar texto WhatsApp: {e}")
        return False

def send_whatsapp_media(remote_jid: str, image_filename: str, caption: str = ""):
    clean_number = remote_jid.split("@")[0]
    media_path = os.path.join(MEDIA_DIR if os.path.exists(MEDIA_DIR) else "/opt/data/nexus_repo/whatsapp_support_agent/guides_media", image_filename)
    if not os.path.exists(media_path):
        return False
        
    with open(media_path, "rb") as f:
        b64_data = base64.b64encode(f.read()).decode("utf-8")
        
    url = f"{EVOLUTION_URL}/message/sendMedia/{EVOLUTION_INSTANCE}"
    headers = {"apikey": EVOLUTION_KEY, "Content-Type": "application/json"}
    payload = {
        "number": clean_number,
        "options": {"delay": 1200, "presence": "composing"},
        "mediaMessage": {
            "mediatype": "image",
            "caption": caption,
            "media": f"data:image/png;base64,{b64_data}"
        }
    }
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status in [200, 201]
    except Exception as e:
        logger.error(f"Erro ao enviar midia WhatsApp: {e}")
        return False

def process_ai_reply(user_message: str, history: list = None) -> tuple:
    """
    Chama o modelo de IA (OpenRouter/OpenAI) com o prompt da Lua e retorna (resposta_texto, imagem_para_enviar, precisa_transbordo)
    """
    sys_prompt = load_system_prompt()
    
    # Montar mensagens
    messages = [{"role": "system", "content": sys_prompt}]
    if history:
        messages.extend(history[-6:]) # ultimas mensagens para contexto
    messages.append({"role": "user", "content": user_message})
    
    # Chamar OpenRouter / OpenAI
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    url = "https://openrouter.ai/api/v1/chat/completions" if os.getenv("OPENROUTER_API_KEY") else "https://api.openai.com/v1/chat/completions"
    model = "deepseek/deepseek-chat" if os.getenv("OPENROUTER_API_KEY") else "gpt-4o-mini"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    if "openrouter.ai" in url:
        headers["HTTP-Referer"] = "https://nexusplay.tv"
        headers["X-Title"] = "Nexus PlayTV Support"
        
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.6,
        "max_tokens": 250
    }
    
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
            raw_text = data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Erro ao chamar LLM para suporte: {e}")
        return ("Opa, tive uma oscilação aqui na minha conexão. Pode me mandar de novo?", None, False)
        
    # Processar comandos internos
    needs_handoff = "[TRANSBORDO_HUMANO]" in raw_text
    image_match = re.search(r"\[ENVIAR_IMAGEM:\s*([a-zA-Z0-9_\.]+)\]", raw_text)
    image_to_send = image_match.group(1) if image_match else None
    
    # Limpar tags da resposta visivel ao cliente
    clean_text = raw_text.replace("[TRANSBORDO_HUMANO]", "")
    clean_text = re.sub(r"\[ENVIAR_IMAGEM:\s*[a-zA-Z0-9_\.]+\]", "", clean_text).strip()
    
    return clean_text, image_to_send, needs_handoff
