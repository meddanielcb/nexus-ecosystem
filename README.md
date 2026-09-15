# 📺 Nexus PlayTV — Sistema Autônomo de Vendas e Streaming IPTV/P2P

> **Status da Plataforma:** Produção 100% Blindada e Operacional (Auditoria Setembro/2026 Concluída)  
> **Bot Oficial Telegram:** `@Nexus_playtvbot`  
> **Canal de Alertas:** `@Alerta_nexusbot` (Telemetria do Administrador)  
> **Host da VPS:** `93.127.210.111` (Hostinger Ubuntu / Docker / Caddy)  
> **Repositório Git:** `https://github.com/meddanielcb/nexus-ecosystem` (Branch: `coord/agents`)

---

## 🎯 Visão Geral do Projeto
O **Nexus PlayTV** é uma infraestrutura de comércio eletrônico conversacional e concierge automatizado voltado para streaming IPTV/P2P anti-bloqueio.
Ele opera de forma **100% autônoma**, eliminando intervenção humana para cobrança, provisionamento de acessos no servidor de streaming e suporte para ativação em Smart TVs.

### Capacidades Chave:
1. **Checkout PIX Nativo Automático:** Integração oficial com a API da **PixGet** (`pixget.app`) com validação direta de CPF na Receita Federal, emissão de QR Code dinâmico, verificação HMAC-SHA256 e polling fallback em tempo real.
2. **Cripto Direta:** Integração com **BlockBee** com validação estrita de assinaturas criptográficas RSA. (CryptoBot eliminado por segurança).
3. **Emissão Oficial MasterX (XUI.ONE / StreamCore):** Provisionamento instantâneo via API REST (`http://painelmaster.app/api.php`) no servidor de streaming oficial `http://atmt.space`.
4. **Pack de Passes de Jogos (Futebol / Lutas):** Modelo de negócio sob demanda — o cliente adquire um saldo de ativações (ex: 3 passes de 4 horas por R$ 14,90) e debita quando quiser no dia do jogo.
5. **Concierge Smart TV com Visão Computacional (OCR):** O cliente envia uma foto da tela da Smart TV (Samsung, LG, etc.) com o aplicativo IBO Player aberto. O robô utiliza a **Google Gemini Vision API** para extrair o `Device ID (MAC)` e a `Device Key`, e injeta a lista M3U automaticamente via API de nuvem do IBO Player, resolvendo o desafio SVG via **2Captcha**.
6. **Dossiê VIP em PDF & Cartão Web:** Geração de manual interativo gerado dinamicamente com as credenciais reais do usuário e WebPlayer oficial.
7. **Supervisor e Auto-Cura 24/7:** Supervisor de processos com trava única de instância (UNIX socket), reconexão e scripts de watchdog.

---

## 🛠️ Arquitetura de Pastas e Módulos

```
nexus-ecosystem/
├── nexus_playtv_bot/               # Código principal do Bot PlayTV
│   ├── run_playtv.py               # Orquestrador do bot Telegram, menus, callbacks e handlers
│   ├── masterx_api.py              # Cliente da API MasterX/StreamCore (linhas pagas e testes)
│   ├── services.py                 # Integração Pixget, BlockBee, instâncias e rotas
│   ├── tv_vision_ocr.py            # Extração de MAC e Device Key por foto via Gemini Vision
│   ├── ibo_injector.py             # Injeção automática na nuvem IBO Player com bypass 2Captcha
│   ├── notifier.py                 # Telemetria para o bot de alerta (@Alerta_nexusbot)
│   ├── pdf_generator.py            # Gerador de manual VIP em PDF com ReportLab
│   ├── make_vip_html.py            # Renderizador do portal web VIP interativo
│   ├── db.py                       # Schema versionado (v2) com migrações idempotentes
│   ├── products_playtv.json        # Grade oficial de planos, passes, preços e descrições
│   └── migrate_dates.py            # Normalizador de datas para ISO 8601
│
├── digital_store_bot/              # Servidor receptor de Webhooks e Supervisor
│   ├── webhook_server.py           # HTTP Server (Porta 8099) para webhooks PixGet, BlockBee e rotas /vip/
│   ├── supervisor.py               # Supervisor 24/7 de processos (PlayTV, Webhooks, etc.)
│   └── notifier.py                 # Notificador de vendas para o Telegram do Daniel
│
├── scripts/                        # Utilitários de infraestrutura e resiliência
│   ├── migrate_and_verify_db.py    # Validação automatizada de integridade dos bancos SQLite
│   ├── backup_nexus_dbs.sh         # Backup rotativo diário dos SQLite (retenção 7 dias)
│   ├── rotate_logs.sh              # Rotação e truncamento de logs volumosos (>5MB)
│   └── watchdog_nexus.sh           # Watchdog de processos para o Cron
│
└── docs/                           # Documentações e relatórios de auditoria
    ├── NEXUS_AUDIT_REPORT_2026-09-15.md  # Relatório completo da auditoria rigorosa
    └── HANDOFF_FORNECEDOR_IPTV.md        # Especificações do fornecedor IPTV MasterX
```

---

## 🔒 Variáveis de Ambiente Necessárias (`/opt/data/.env`)
Nunca versionar chaves reais no Git. Certifique-se de que o arquivo `/opt/data/.env` na VPS contenha:

```env
# Telegram Bots
PLAYTV_BOT_TOKEN="[REDACTED]"          # @Nexus_playtvbot
ALERTA_BOT_TOKEN="[REDACTED]"          # @Alerta_nexusbot
ADMIN_CHAT_ID="671901048"              # ID Telegram do Daniel

# PixGet Gateway
PIXGET_API_KEY="[REDACTED]"
PIXGET_SECRET_KEY="[REDACTED]"         # HMAC-SHA256 signature secret

# MasterX IPTV Provider
MASTERX_API_URL="http://painelmaster.app/api.php"
MASTERX_API_KEY="[REDACTED]"
MASTERX_SERVER_DNS="http://atmt.space"
MASTERX_PORTAL_URL="http://painelmaster.app/portal"

# Cripto e Automação
BLOCKBEE_API_KEY="[REDACTED]"
TWOCAPTCHA_API_KEY="[REDACTED]"
GEMINI_API_KEY="[REDACTED]"            # Google Vision OCR
```

---

## 🚀 Como Executar e Manter

### 1. Iniciar ou Reiniciar o Sistema Completo
O sistema é orquestrado pelo `supervisor.py` e vigiado pelo cron via `watchdog_nexus.sh`:
```bash
# Executar migrações de banco (se houver alterações no schema)
/opt/hermes/.venv/bin/python3 /opt/data/scripts/migrate_and_verify_db.py

# Iniciar o Supervisor em background (ele sobe o webhook e os bots automaticamente)
nohup /opt/hermes/.venv/bin/python3 /opt/data/digital_store_bot/supervisor.py > /opt/data/digital_store_bot/logs/supervisor.log 2>&1 &
```

### 2. Verificar Logs e Saúde dos Serviços
```bash
# Status dos processos ativos
ps aux | grep -E "run_playtv|webhook_server|supervisor"

# Testar saúde do webhook local
curl -I http://127.0.0.1:8099/api/webhooks/pixget

# Testar rota VIP protegida (deve retornar 404 para ID inexistente)
curl -s http://127.0.0.1:8099/vip/TESTE_INEXISTENTE
```

---

## 📈 Roadmap & Próximos Passos Planejados

Qualquer agente ou desenvolvedor que assumir o projeto deve seguir esta priorização estratégica:

### 1. Landing Page de Vendas Web (Canal de Venda Direta)
- **Objetivo:** Criar um canal de vendas para tráfego pago (Meta Ads / Google Ads) sem exigir que o cliente tenha o app do Telegram instalado.
- **Estrutura:** Single Page ultrarrápida, dark mode (paleta Preto `#0a0b0e` + Ciano `#00f2fe`), servida pelo Caddy.
- **Checkout:** Formulário simples (Nome, WhatsApp, CPF) que chama a API da PixGet na VPS e exibe o QR Code Pix na tela. Após confirmação, desbloqueia o WebPlayer e as credenciais.

### 2. WhatsApp Próprio Autônomo (Evolution API na VPS)
- **Objetivo:** Terceiro canal de vendas nativo no WhatsApp.
- **Implementação:** Subir um container leve da **Evolution API** via Docker na VPS (`93.127.210.111`).
- **Automação:** Conectar o número de atendimento via QR Code e criar o bot em Python consumindo os mesmos serviços de `services.py` e `tv_vision_ocr.py` (venda via Pix e ativação de Smart TV por foto recebida no WhatsApp).

### 3. Modelo B2B: Revenda de Painel / Créditos MasterX
- **Objetivo:** Monetização em atacado.
- **Implementação:** Criar planos de revenda no bot (ex: 10 créditos por R$ 150, 25 créditos por R$ 300).
- **Automação MasterX:** Usar os endpoints `/api.php?action=reseller&sub=create` e `/api.php?action=reseller&sub=credits` para criar sub-revendedores automaticamente assim que o pagamento PIX for confirmado.

### 4. Integração de E-mail Transacional (Fallback de Entrega)
- **Objetivo:** Enviar o dossiê VIP em PDF gerado dinamicamente para o e-mail do cliente (via Resend ou SMTP) garantindo que ele não perca o acesso caso feche o Telegram ou o navegador.
