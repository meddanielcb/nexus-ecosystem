# NEXUS PLAYTV — PLANO DIRETOR E ROADMAP EXECUTIVO DAS PRÓXIMAS ETAPAS
**Data:** 16 de Setembro de 2026  
**Status:** Em Execução / Coordenação de Agentes  
**Domínio Oficial:** `nexusplay.tv` (Fallback: `nexusplaytv.com`)  
**Infraestrutura Alvo:** VPS Njalla Offshore (Suécia / Ceph Cluster)  
**Branch Git:** `coord/agents`

---

## 🎯 VISÃO GERAL DO PRODUTO & DIFERENCIAIS COMPETITIVOS

O ecossistema **Nexus PlayTV** está sendo estruturado para ser uma operação autônoma, anônima e de altíssima conversão e retenção, operando em quatro pilares integrados:
1. **Landing Page Oficial de Conversão Cinematográfica (`nexusplay.tv`):** Visual Dark Theme de alto padrão (estilo IPTVX.app), com quebra total de objeções, comparador visual de economia e checkout direto.
2. **Web App / PWA Utilitário de Bolso (`nexusplay.tv/app`):** Guia esportivo diário para retenção, jogos do dia com horários e brasões oficiais, alertas por push notification e central de renovação.
3. **WebPlayer Oficial Personalizado (`play.nexusplay.tv`):** Reprodução instantânea de canais e VODs no navegador do celular, computador e Smart TV sem necessidade de instalar aplicativos de terceiros.
4. **Backend Autônomo & Helpdesk Omnichannel:** Ativação instantânea por IA via foto da tela da Smart TV (Nexus Vision AI™), entrega atômica pós-PIX/Cripto e suporte privado via Telegram/WhatsApp.

---

## 🗺️ MATRIZ DAS ETAPAS EXECUTIVAS

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ FASE 1: PROVISIONAMENTO & BLINDAGEM OFFSHORE (VPS NJALLA)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ • Ativação do nó no cluster Ceph Njalla (status: pending -> active)         │
│ • Hardening Linux (UFW, fail2ban, SSH Ed25519, non-root user)               │
│ • Configuração DNS Njalla: nexusplay.tv, play.nexusplay.tv, api.nexusplay.tv│
│ • Emissão de certificados SSL curinga/Let's Encrypt                         │
│ • Sanitização de segredos em .env restrito (chmod 600)                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ FASE 2: LANDING PAGE & CHECKOUT AUTÔNOMO (NEXUSPLAY.TV)                     │
├─────────────────────────────────────────────────────────────────────────────┤
│ • Aplicação do design cinematográfico definitivo (Dark Glassmorphism)       │
│ • Bloco de destaque Nexus Vision AI™ (Ativação Smart TV por Foto)           │
│ • Seletor de Telas (1, 2 e 3 telas) com Tabela Oficial de Planos:           │
│   - Pass Avulso 3 Jogos: R$ 14,90                                           │
│   - Mensal: R$ 31,90 / Trimestral: R$ 79,90                                 │
│   - Semestral: R$ 149,90 / Anual VIP: R$ 249,90 (R$ 20,82/mês)              │
│ • Modal de Checkout integrado (PIX DePix/Pixget + Cripto BlockBee)          │
│ • Virada imediata para Cartão VIP Web com dados copiáveis e PDF             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ FASE 3: O PWA UTILITÁRIO & FUNIL DE RETENÇÃO (NEXUSPLAY.TV/APP)             │
├─────────────────────────────────────────────────────────────────────────────┤
│ • Regra de Ouro do Teste Grátis: Instalação obrigatória do PWA              │
│ • Micro-serviço coletor de Jogos do Dia (Futebol, Basquete, Lutas, F1)      │
│ • Integração com TheSportsDB API para download e exibição de brasões reais  │
│ • Mapeamento do canal exato de transmissão no Nexus (Premiere, ESPN, etc.)  │
│ • Módulo "Meus Esportes Favoritos" com Push Notifications de aviso de jogo  │
│ • Banner de renovação com 1 clique antes do vencimento                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ FASE 4: WEBPLAYER EXCLUSIVO NEXUS (PLAY.NEXUSPLAY.TV)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│ • Deploy da stack Next.js 16 + React 19 + HLS.js (Streamly core)            │
│ • Personalização visual completa: Logo Nexus, paleta escura ciano/neon      │
│ • Integração direta com a API Xtream Codes MasterX (http://atmt.space)      │
│ • Smart TV Pairing via PIN de 6 dígitos e QR Code                           │
│ • Proxy interno de mídia (elimina bloqueios CORS e traffic shaping)         │
│ • Contador de tempo e gatilho de compra embutido para testes grátis         │
│ • [PROJETO MONETIZAÇÃO & RETENÇÃO - BACKLOG]:                               │
│   - Guia "Jogos de Hoje" com sintonia direta em 1 clique (brasões/horários) │
│   - Espaços para Publicidade/Patrocínio (Pre-roll buffer, banners rodapé)   │
│   - Botão de Suporte IA / Atendimento direto via WhatsApp integrado          │
│   - Urgência de renovação/upgrade para contas de teste grátis               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ FASE 5: MIGRAÇÃO DEFINITIVA & VIRADA DE TRÁFEGO (ZERO DOWNTIME)             │
├─────────────────────────────────────────────────────────────────────────────┤
│ • Migração do banco de dados SQLite (playtv.db) em WAL mode                 │
│ • Teste de ponta a ponta: Webhook PIX, Webhook Cripto e Ativação OCR        │
│ • Atualização da URL de webhook no Pixget para https://nexusplay.tv         │
│ • Desativação do servidor legado da Hostinger com privacidade total         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ DETALHAMENTO DAS ESPECIFICAÇÕES TÉCNICAS

### 1. PWA Esportivo & Funil do Teste Grátis
* **Gatilho de Entrada:** O botão "🎁 Solicitar Teste Grátis (4 Horas)" na Landing Page abre o fluxo do PWA.
* **Mecânica PWA:** O evento `beforeinstallprompt` captura a intenção; a emissão da linha no MasterX (`is_trial=1`) só é disparada após o evento `appinstalled` confirmar a presença do app no dispositivo do usuário.
* **Scraper de Jogos:** Script agendado na VPS em Python (assíncrono) que consome o feed diário de transmissões nacionais e internacionais e reconcilia com a lista de canais do MasterX.
* **Cache de Brasões:** Armazenamento local dos escudos vetorizados/PNG transparentes para carregamento instantâneo offline.

### 2. WebPlayer Offshore (`play.nexusplay.tv`)
* **Framework:** Next.js 16 / Node.js 22 LTS encapsulado em Docker Compose.
* **CORS & HLS Proxy:** Reverse proxy local em Nginx repassando streams `.m3u8` e `.ts` com headers otimizados (`X-Accel-Buffering: no`).
* **Segurança:** Sem armazenamento de senhas em texto puro nos cookies; sessões assinadas com `STREAM_SESSION_SECRET` (AES-256-GCM).

### 3. Engine de Monetização, AdTech & Mídia Proprietária (VALE OURO)
* **Pre-Roll de Carregamento Inteligente (Buffer Monetizado):**
  - Nos 2 a 3 segundos naturais de handshake/buffer inicial do stream HLS, exibição de vinheta/banner em alta resolução de 5s.
  - Anunciantes de alto valor: iGaming/Casas de Apostas (Bet365, Blaze, etc. via RevShare/CPA), infoprodutos e ecossistema proprietário (Nutra, Pixget).
* **Overlay L-Band Não-Intrusivo (Rodapé do Guia/Menu):**
  - Banner discreto no terço inferior da tela exibido durante a navegação pelo catálogo de canais com CTA rastreável via link de afiliado.
* **Espaço Patrocinado no Guia de Jogos do Dia:**
  - "Jogos de Hoje — Oferecimento [Nome do Patrocinador]" com destaque do logo no topo do card.
* **Atendimento & Suporte IA Integrado:**
  - Botão flutuante discreto com suporte direto ao WhatsApp com IA e escalonamento humano.

### 4. Blindagem de Dados & Regra de Ouro Financeira
* **Privacidade 1337 LLC:** Nenhum cabeçalho HTTP ou resposta de API conterá menções a IPs residenciais, nomes pessoais ou chaves não-oficiais.
* **Aprovações Financeiras:** Nenhuma nova contratação ou débito na Wallet Njalla ocorre sem prévia confirmação e validação do proprietário (Daniel).

---

## 📋 CHECKLIST DE PRONTIDÃO PARA A VPS NJALLA

- [ ] Status do servidor `4WHBZIDCU5JO5EJ4GHTGYZNZ5KLRDMD3` alterado para `active`
- [ ] Conexão SSH via chave Ed25519 validada
- [ ] Instalação de Docker, Docker Compose, Nginx, Certbot e Python 3.12
- [ ] Apontamento dos registros DNS A na API da Njalla para os subdomínios
- [ ] Clone do repositório `nexus-ecosystem` e injeção do arquivo `.env` seguro
- [ ] Inicialização dos serviços via Supervisor/Systemd
- [ ] Testes de emissão e auditoria final
