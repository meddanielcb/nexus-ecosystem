# ⚡ Nexus Ecosystem

Plataforma de e-commerce e automação autônoma para produtos digitais de alta margem e streaming IPTV P2P anti-bloqueio, operando 24/7 na VPS Hostinger.

---

## 🏛️ Arquitetura da Infraestrutura

O ecossistema é composto por dois serviços de front-end no Telegram, um hub de webhooks assíncrono e um supervisor com watchdog automático:

```
                          ┌─────────────────────────────┐
                          │   Hostinger VPS (Ubuntu)    │
                          │        Caddy SSL            │
                          └──────────────┬──────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 │                                               │
                 ▼                                               ▼
     ┌───────────────────────┐                       ┌───────────────────────┐
     │      Nexus Tools      │                       │     Nexus PlayTV      │
     │   (@botnexustools)    │                       │   (@Nexus_playtvbot)  │
     │  Produtos Digitais    │                       │  IPTV P2P Anti-Block  │
     └───────────┬───────────┘                       └───────────┬───────────┘
                 │                                               │
                 └───────────────────────┬───────────────────────┘
                                         │
                                         ▼
                         ┌───────────────────────────────┐
                         │       webhook_server.py       │
                         │   Porta 8099 (Caddy Proxy)    │
                         ├───────────────────────────────┤
                         │ - Checkout PIX (Pixget)       │
                         │ - Cripto (BlockBee)           │
                         │ - Cartões VIP Web Interativos │
                         │ - Ativação IBO Player (OCR)   │
                         └───────────────┬───────────────┘
                                         │
                                         ▼
                         ┌───────────────────────────────┐
                         │         supervisor.py         │
                         │  Watchdog & Auto-Healing 24/7 │
                         └───────────────────────────────┘
```

---

## 📦 Módulos do Sistema

### 1. `nexus_playtv_bot` (Streaming & IPTV VIP)
- **Engine Principal:** `run_playtv.py`
- **Ativação Concierge Smart TV:** Handler com Visão Computacional / OCR (`photo_handler`). O cliente envia uma foto da tela da Smart TV no app IBO Player; o bot lê Device ID e Device Key e injeta a lista diretamente na nuvem via `ibo_injector.py` com resolução de SVG por 2Captcha.
- **Passes de Jogos & Futebol (R$ 14,90):** Banco SQLite `game_passes` para venda avulsa e resgate sob demanda com código de acesso único.
- **Integração Xtream Codes / M3U:** Gerador de credenciais dinâmicas em `services.py` apontando para o servidor master `man77.work`.
- **Manuais de Instalação com Downloaders:** Guias nativos com códigos rápidos de Downloader Fire TV / TV Box (`1941290`, `7877135`, `9007131`, `8627648`).
- **Cartão VIP Web:** Gerador de páginas HTML interativas estilo cyber/dark (`make_vip_html.py`) com player web embutido e cópia de credenciais em 1-clique.

### 2. `digital_store_bot` (Nexus Tools)
- **Engine Principal:** `run_store.py`
- **Catálogo de Alta Margem:** Licenças e contas exclusivas (ChatGPT Plus, Perplexity Pro, Canva Pro, Claude Pro, etc.) em `products.json`.
- **i18n & Multi-idioma:** Motor `i18n.py` com suporte a PT-BR, EN e ES.
- **Integração de Pagamento Duplo:**
  - PIX instantâneo com verificação HMAC-SHA256 via gateway Pixget.
  - Criptomoedas (USDT, BTC, LTC, etc.) via BlockBee com assinatura criptográfica SHA-256.

### 3. `webhook_server.py` & `supervisor.py`
- **Webhooks:** Trata retornos assíncronos de pagamento, dispara notificações de telemetria no Telegram privado e provisiona a entrega imediata ao cliente.
- **Watchdog:** Monitora saúde dos processos a cada 60 segundos com reinicialização automática em caso de crash.

---

## 🔒 Segurança & Compliance
- Chaves de API, senhas e tokens são mantidos em variáveis de ambiente e arquivos de configuração fora do controle de versão.
- Repositório privado exclusivo para o operador `@meddanielcb`.
