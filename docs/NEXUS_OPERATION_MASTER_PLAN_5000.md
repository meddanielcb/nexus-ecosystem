# 🚀 NEXUS PLAYTV — PLANO OPERACIONAL MESTRE & ROADMAP (META: 5.000 ASSINANTES)

**Status:** Planejamento Executivo Consolidado  
**Data:** 18 de Setembro de 2026  
**Meta Ano 1:** 5.000 Assinantes Ativos  
**Margem Operacional Líquida:** > 92%  

---

## 📊 1. A Matemática do Negócio & Metas Financeiras

| Métrica | Valor Unitário / Projeção | Total Mensal (5.000 clientes) | Total Anual |
| :--- | :--- | :--- | :--- |
| **Ticket Médio Ponderado** | ~R$ 31,90 / mês | **R$ 159.500,00** | **R$ 1.914.000,00** |
| **Custo de Upstream (Créditos)** | R$ 2,00 / cliente | R$ 10.000,00 | R$ 120.000,00 |
| **Infraestrutura VPS (Njalla + SP Edge)** | Fixa | ~R$ 500,00 | ~R$ 6.000,00 |
| **Custos de Gateway (PixGet)** | ~1.5% | ~R$ 2.400,00 | ~R$ 28.800,00 |
| **Lucro Líquido Estimado** | **> 92%** | **~R$ 146.600,00 / mês** | **~R$ 1.759.200,00 / ano** |

### Canais de Aquisição para Atingir a Meta:
* **60% (3.000 clientes):** Venda direta (WhatsApp via Evolution API, Bot Telegram, Web Landing Page).
* **25% (1.250 clientes):** Rede B2B de Revendedores Independentes em lotes de atacado.
* **15% (750 clientes):** Mecânica Viral MGM (*Indique & Ganhe* com CAC de R$ 2,00).

---

## 🎯 2. Grade de Preços Oficial & Posicionamento

* **⚽ Pass 3 Jogos (4h cada):** **R$ 14,90** *(Custo: R$ 0,00 via Trial API — Margem: 100%)*
* **📺 Mensal (1 Tela):** **R$ 31,90** *(Custo: R$ 2,00 — Margem: R$ 29,90)*
* **➕ Tela Adicional (Upsell):** **+R$ 10,90** / tela *(Sala, Quarto, Celular)*
* **🔥 Trimestral (1 Tela):** **R$ 79,90** *(R$ 26,63/mês)*
* **⭐ Semestral (1 Tela):** **R$ 139,90** *(R$ 23,31/mês)*
* **👑 Anual Família VIP (2 Telas):** **R$ 229,90** *(R$ 19,15/mês)*

---

## 🛠️ 3. Mapa de Pendências por Ordem de Prioridade

### PRIORIDADE 1: PWA & Atalho Inteligente para Smart TV
* **Complexidade:** Baixa | **Prazo:** 1 dia | **Impacto:** Zero atrito no acesso do cliente.
* **Tarefas:**
  1. `manifest.json` e Service Worker para cache offline do shell.
  2. Modal de orientação na TV (Tizen/webOS): *"Adicione a Nexus aos favoritos ou à tela inicial da sua TV"*.
  3. Suporte ao prompt nativo de instalação no Chrome/Safari mobile e desktop.

---

### PRIORIDADE 2: WhatsApp Autônomo com Evolution API na VPS
* **Complexidade:** Média | **Prazo:** 1 a 2 dias | **Impacto:** Canal com mais de 70% da conversão no Brasil.
* **Tarefas:**
  1. Container Docker leve da Evolution API na VPS Njalla (`45.158.116.180`).
  2. Pareamento do chip/número comercial via QR Code.
  3. Bot Python autônomo com fluxo de:
     * Apresentação da grade e planos.
     * Geração instantânea de Pix via PixGet.
     * Confirmação via webhook e entrega atômica em < 3 segundos.
     * Ativação por foto da Smart TV via OCR Vision (IBO Player, SmartOne, etc.).
     * Régua de retenção e renovação automática (D-3, D-1, D-0).

---

### PRIORIDADE 3: E-mail Transacional & Fallback de Entrega (Resend / SMTP)
* **Complexidade:** Baixa | **Prazo:** Meio dia | **Impacto:** Redundância e segurança pós-venda.
* **Tarefas:**
  1. Envio automatizado do **Dossiê VIP Nexus PlayTV** após confirmação do Pix.
  2. Contém: link direto autenticado, credenciais, código para Downloader e manual em PDF.
  3. Previne suporte caso o cliente feche a tela ou perca a conversa no WhatsApp.

---

### PRIORIDADE 4: Checkout Web PixGet + Mecânica Viral MGM (Indique & Ganhe)
* **Complexidade:** Média | **Prazo:** 1 a 2 dias | **Impacto:** Crescimento orgânico com CAC de R$ 2,00.
* **Tarefas:**
  1. Landing Page moderna, dark, servida em HTTPS direto pela VPS.
  2. Formulário de checkout simples integrado à API PixGet (HMAC-SHA256).
  3. **Loop Viral MGM:**
     * *"Indique 1 amigo: quando ele assinar qualquer plano, você ganha 30 dias de graça na sua conta!"*
     * Custo para a empresa: exatamente **R$ 2,00** por mês concedido.
     * Tracking por links parametrizados (`ref=...`).

---

### PRIORIDADE 5: Nó de Retransmissão Edge VPS em São Paulo (Anti-Lag & Baixa Latência)
* **Complexidade:** Média | **Prazo:** 2 dias | **Impacto:** Latência de 10-20ms nos jogos ao vivo de pico.
* **Tarefas:**
  1. Instalar VPS leve em São Paulo (Hostinger/Contabo/Equinix).
  2. Configurar túnel privado WireGuard permanente entre a VPS Suécia (origem) e a VPS SP (borda).
  3. Servidor de borda em SP como proxy/cache de vídeo sem dados sensíveis de clientes ou banco de dados.

---

### PRIORIDADE 6: Módulo B2B & Painel de Revenda Automático (Reseller)
* **Complexidade:** Média | **Prazo:** 2 a 3 dias | **Impacto:** Atacado e escala em blocos de centenas de clientes.
* **Tarefas:**
  1. Planos de atacado: 10 créditos (R$ 150), 25 créditos (R$ 300), 50 créditos (R$ 500).
  2. Automação via API do upstream para criar revendedores e transferir créditos após Pix.
  3. Revendedores locais assumem o atendimento na ponta, multiplicando a base sem sobrecarga operacional.

---

### PRIORIDADE 7: APK Nativo Dedicado Nexus PlayTV (Android TV / Fire Stick)
* **Complexidade:** Média-Alta | **Prazo:** 3 a 5 dias | **Impacto:** Experiência nativa em TV Boxes.
* **Tarefas:**
  1. APK WebWrapper com Chromium acelerado por GPU e suporte HEVC/AV1.
  2. Encurtador de código numérico para o app Downloader (AFTVnews) — ex: código `XXXXX` instala o app em 10 segundos.
  3. Auto-boot opcional ao ligar a TV Box.

---

### PRIORIDADE 8: O Nexus Play Stick (Hardware Físico Plug & Play)
* **Complexidade:** Alta (Dependente do protótipo) | **Prazo:** 15 a 25 dias | **Impacto:** Ecossistema de hardware estilo BTV / RedPlay.
* **Status:**
  * Protótipo Amlogic 2GB/16GB com controle BT Voice encomendado no AliExpress rumo a Balneário Camboriú.
* **Próximas etapas:**
  1. Flash da ROM proprietária com inicialização imediata no WebPlayer Beta cinematográfico.
  2. Blindagem de privacidade:
     * **Varejo:** Dropshipping direto da fábrica de Shenzhen para o cliente (sem remetente no BR, zero CPF/CNPJ).
     * **Atacado:** Venda de caixas fechadas para revendedores no Brasil/Paraguai via USDT.

---

## 📅 4. Cronograma de Execução (Próximos 7 Dias)

* **Dia 1:** PWA na Web + Service Worker + Modal de Atalho para Smart TV (Tizen/webOS).
* **Dia 2:** Subir a Evolution API na VPS + Fluxo do bot de vendas e Pix no WhatsApp.
* **Dia 3:** E-mail transacional (Resend/SMTP) + Landing Page web de vendas.
* **Dia 4:** Mecânica do Indique & Ganhe (MGM) com crédito automático por indicação.
* **Dia 5:** Túnel WireGuard e nó Edge de São Paulo (anti-lag).
* **Dia 6:** Automação de planos de revenda B2B.
* **Dia 7:** Build e teste do APK com código do Downloader.
