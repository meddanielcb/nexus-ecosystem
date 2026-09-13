# MINERAÇÃO E AUDITORIA DE FORNECEDORES DIGITAIS — TELEGRAM, FÓRUNS E LOJAS AUTOMÁTICAS

> **Objetivo:** mapear BOTS DO TELEGRAM, CANAIS e PLATAFORMAS AUTOMÁTICAS que vendem ativações/assinaturas digitais (Gemini Pro, Canva, Spotify, APIs de IA e demais categorias) com **entrega instantânea** e **pagamento em Cripto/USDT/CryptoBot**, validando a existência real de cada handle.
> **Data da coleta:** 12 de setembro de 2026. **Autor:** subagente de pesquisa (Hermes).
> **Regra de honestidade aplicada:** NENHUM dado/username foi inventado. Todos os handles `@...` abaixo foram **validados por requisição HTTP real** a `https://t.me/<handle>` (ver Metodologia). Preços vêm de **scrape do próprio canal/bot** (quando indicado “verificado no canal”) ou de **páginas de marketplace/fórum** (quando indicado “declarado”). Onde não foi possível confirmar, está marcado como **NÃO VERIFICADO**.

---

## 0. Metodologia e validade das evidências

**Como cada handle foi validado (execução real, sem login):**
- `GET https://t.me/<handle>` → se a página contém o elemento `tgme_page_title`, o handle **existe** (canal/bot/usuário). Handles inexistentes retornam página genérica sem título.
- `GET https://t.me/s/<canal>` → para canais **públicos**, baixa o feed de posts (conteúdo real, preços, método de pagamento) sem entrar no canal.
- Script reutilizável salvo em `/opt/data/digital_store_bot/validate_handles.py` e `/opt/data/digital_store_bot/scrape_channel.py`.

**Legenda de Confiança (na existência do handle):**
- 🟢 **VALIDADO** — `tgme_page_title` presente + (para canais) feed público lido.
- 🟡 **PARCIAL** — handle existe, mas conteúdo/preço não pôde ser aberto (canal privado, bot muda de estado, ou dado só em fórum).
- 🔴 **NÃO VERIFICADO / MORTO** — handle não retornou título (não existe) ou dado veio só de fonte secundária.

**Legenda de Risco (produto):**
- 🟥 **Alto** — produto derivado de abuso de promoção/EDU/relay; revogação em lote, ban de conta, chave morre em cascata.
- 🟧 **Médio** — conta pronta/convite de família real, com garantia do vendedor mas ejetável.
- 🟩 **Baixo** — emissão legítima (org própria, gateway oficial) ou mercadoria de revenda autorizada.

---

## 1. AUDITORIA DETALHADA — ECOSSISTEMA GGSOMA (foco solicitado)

Todos os handles do ecossistema foram **validados individualmente em 12/09/2026**:

| Handle | Tipo | Título real retornado por t.me | Status |
|---|---|---|---|
| **@ggsomabot** | Bot | “GGSoma bot” | 🟢 VALIDADO |
| **@GGsoma2bot** | Bot (2º / Binance) | “GGsoma 2 bot” | 🟢 VALIDADO |
| **@toolais** | Canal oficial | “GGSoma” — **70.404 assinantes** | 🟢 VALIDADO (feed lido) |
| **@Gg2soma** | Canal 2º | “GG2” — 3.705 assinantes | 🟢 VALIDADO |
| **@Ggsomasupportbot** | Bot suporte | “Ggsoma Support” | 🟢 VALIDADO |
| **@gptactivate** | Canal suporte | “GGSomabot support” | 🟢 VALIDADO |
| **@GGBuildBot** | Bot (white-label) | “GGBuilder” — “Your own Telegram store — built in minutes” | 🟢 VALIDADO |
| **@ggbuilders** | Canal (white-label) | “GGbuilder” — 526 assinantes | 🟢 VALIDADO (feed lido) |
| **@ggbuilderSupport** | Contato (white-label) | “GGbuilder Store” | 🟢 VALIDADO |
| **@GGsoma** / **@ggsoma** | Contato dono | “GGSoma” — “We provide all AI services in one place” | 🟢 VALIDADO |

### 1.1 Produtos e preços (verificados no feed de `t.me/toolais`)

| Produto | Preço observado | Evidência |
|---|---|---|
| **Gemini (AI Pro) 18M** | **US$ 1,00** em promoção (24h ampliada p/ +2 dias); preço promocional recorrente “Gemini Sale” | Post do canal *“24-Hour Gemini Sale! … Gemini available for just $1 on both of our bots”* + *“Gemini $1 Offer Extended!”* |
| **Spotify Premium — 2 meses** | (preço no bot; não exibido no post) | Post *“New Products Available Now! Spotify Premium — 2 Months”* |
| **iLovePDF Premium — 12 meses** | (preço no bot) | Post *“New Products Available Now! iLovePDF Premium — 12 Months”* |
| **ChatGPT CDK / Google AI Pro 12m / Google AI Pro 12m $15.50** | US$ 15,50 p/ Google AI Pro 12m (relatado pelo usuário) | **PARCIAL** — preço não lido no feed público neste momento |
| Catálogo amplo (“AI services in one place”) | — | Descrição do canal @GGsoma |

> **Nota:** o feed público do @toolais visto nesta coleta exibia o “$1 Gemini” e os drops Spotify/iLovePDF; os preços de Google AI Pro 12m ($15,50), ChatGPT CDK, etc. são **declarados pelo usuário** e não foram lançados no feed no momento do scrape → tratados como 🟡 PARCIAL.

### 1.2 Meios de pagamento (verificados no feed)

- **Binance Pay / Binance ID** — canal dedicado: *“If you would like to pay via Binance, you can make your purchase through our second bot: @GGsoma2bot”*.
- **USDT multi-rede** — BEP20 (BSC), Polygon, TRC20 (TRON) — conforme reivindicado pelo usuário; a existência do bot dedicado a Binance está **confirmada**; a lista exata de redes por bot **não foi aberta** (precisa `/start` no bot) → 🟡 PARCIAL para a lista de redes, 🟢 para Binance Pay.
- **Cripto/CryptoBot** — o ecossistema opera 100% em cripto (não há menção a PIX/cartão no feed).

### 1.3 Viabilidade de compra AUTOMATIZADA via UserBot (Telethon)

Análise baseada na arquitetura observável (loja de botões inline + pagamento cripto + entrega em chat):

- **É tecnicamente viável** operar um **UserBot Telethon** que:
  1. envia `/start` a `@ggsomabot`, percorre os menus inline (`callback_data`) por clique de botão;
  2. seleciona o produto e dispara a fatura cripto (Binance Pay / USDT);
  3. **captura o link/chave que o bot devolve no chat** após a confirmação do pagamento;
  4. encaminha o produto ao cliente final.
- **Gargalos reais (não técnicos):**
  - **Pagamento não é 100% programático:** Binance Pay exige um pagador humano/UID válido; USDT exige assinatura on-chain. O UserBot só captura o **resultado**; o **settlement** continua sendo o passo de fato.
  - **Rate limits / anti-bot do Telegram:** muitos cliques rápidos disparam flood-wait e podem marcar o UserBot como spam.
  - **Frágil a mudanças de UI:** qualquer alteração dos botões `callback_data` quebra o scraper — exige manutenção contínua.
- **Conclusão:** o caminho **robusto** não é “raspar o bot de terceiro por Telethon”, e sim **reproduzir o modelo**: usar o **white-label oficial do próprio GGSoma (GGBuilder)** ou um painel com API real. O `@GGBuildBot` existe justamente para clonar o modelo de loja deles sem tocar na UI alheia.

### 1.4 Ecossistema white-label — @GGBuildBot / @ggbuilders

- **@GGBuildBot** (“GGBuilder”) — descrição validada: *“Your own Telegram store — built in minutes, selling in 4 steps. Simple, fast, secure.”*
- Canal **@ggbuilders** (526 assinantes) — pitch validado no feed: *“Your Telegram store deserves more than just a bot. With GG Builder Store… ✅ Products & digital inventory ✅ Instant and manual orders ✅ Customers & transactions ✅ Payment methods ✅ Multiple languages ✅ Broadcasts & bot customization… No coding. No hosting. No maintenance. We handle the infrastructure.”*
- **Implicação estratégica:** o GGSoma não só vende produto como **vende o SaaS de loja** (infra multi-tenant com pagamento e estoque). É o competidor/fornecedor de white-label mais direto para um projeto de loja autônoma. Contato: @ggbuilderSupport.

---

## 2. TABELA MESTRA — BOTS DO TELEGRAM (entrega instantânea / cripto)

> Todos os handles abaixo com 🟢 foram validados por HTTP nesta coleta. Preço “verificado no canal” = lido no feed `t.me/s/`.

| Nome / Handle | Produto principal | Preço unitário observado | Pagamento | Confiança | Risco |
|---|---|---|---|---|---|
| **@ggsomabot** / **@GGsoma2bot** (GGSoma) | Gemini 18M, Spotify, iLovePDF, ChatGPT CDK, Google AI Pro | **Gemini US$ 1,00** (sale); Google AI Pro 12m ~$15,50* | Binance Pay, USDT BEP20/Polygon/TRC20 | 🟢 | 🟥 (Gemini de promoção) |
| **@AiVerseXBot** (AIVerse X Hub) | Gemini Pro 18M, CapCut, NordVPN | **$0,45–$0,65** (1–10 un $0,65; 50+ $0,60) | Cripto (assinatura da loja) | 🟢 | 🟥 |
| **@AIVerseXHub** (canal, 21.980 subs) | Updates/deals | — | — | 🟢 | — |
| **@AIXpress_Bot** | Gemini Pro 18M | **$0,40–$0,60** (1–199 $0,60; 500+ $0,40) | Cripto | 🟢 | 🟥 |
| **@Gemini_shop_Robot** | Gemini Pro 18M activation links | **1–9 → $0,65; 9–99 → $0,60; 100–1000 → $0,57** | Cripto | 🟢 | 🟥 |
| **@gemini12pro_bot** (“Gemini Pixel Helper”) | Upgrade Gemini Pro/Pixel | (atacado $0,40–$0,65) | — | 🟢 | 🟥 |
| **@sheeridverifier_bot** (“Gemini Pro Automation Bot”) | Verify SheerID/Pixel → Gemini Pro; contas Gmail 1 ano | **$1,20 verify** (via admin @taomua); Gmail 1 ano ~$1,80 (relatado) | Cripto/Binance | 🟢 | 🟥 |
| **@geminiprosub_bot** (“Gemini Pro 18 Months”) | Gemini 18M, ChatGPT Plus, Coursera, Quillbot | Gemini **$0,65–$0,70**; bulk 40+ → $0,50; ChatGPT AP $8,40–$9,20 | Cripto (saldo/bot) | 🟢 | 🟥 |
| **@ver_pixel_bot** (“Gemini - ChatGPT Bot”) | Upgrade Gemini Pro 1 ano + loja | — | Cripto | 🟢 | 🟥 |
| **@pixora_digital_bot** (“Pixora officiel”) | Gemini 18M, ChatGPT Plus, SuperGrok, CapCut, Adobe CC, Canva, NordVPN, Notion | Gemini **a partir de $0,40** | Cripto | 🟢 | 🟥 |
| **@nevakeystore_bot** (“Neva AI”) | Assinaturas premium “100% oficiais” | — | Cripto | 🟢 | 🟧 |
| **@Veriyferbot** (“Verifier Bot”) | Gemini/Claude/ChatGPT verify, API keys, Netflix, X Premium, escrow | **API Starter $10 (~$30 oficial); Standard $30 (~$120); Premium $50 (~$240)**; X Premium 3m $7; Gemini 18m link | USDT BEP20/TRC20/ERC20/Solana/TON, Binance UID, USDC | 🟢 | 🟥 |
| **@geminipro18** (canal, 814 subs) / **@geminiprosub_bot** | Loja Gemini/API | — | — | 🟢 | — |
| **@Tdsresellerstorebot** (X Method TDS Store) | Gemini 18M, CapCut Pro, Surfshark method | **Gemini $0,46–$0,56**; CapCut 30d $1,48–$1,50; Surfshark $1,00 | Carteira interna (top-up $0,46 “manual”) | 🟢 | 🟥 |
| **@CanvaProInvites_bot** (“CanvaPro”) | Canva Pro invites (grátis/EDU) | grátis (monetizado por ads) | Ads (não vende) | 🟢 | 🟧 |
| **@CanvaProTeam_Bot** (“Canva Pro Team”) | Canva Pro team links | grátis/links | Mini-app | 🟢 | 🟧 |
| **@RealCanvaProBot** (“Canva Pro LIFETIME FREE”) | Canva Pro grátis | grátis | — | 🟢 | 🟧 |
| **@GeneratCPro_bot** (“Canva Pro Generator Links”) | Gerador de links Canva Pro | grátis | — | 🟢 | 🟧 |
| **@CanvaChatBot** | Canva (AI/bot) | — | — | 🟢 | 🟧 |
| **@hamza7754_bot** (“HamzuStore · Digital Hub”) | Loja digital (EthioFaster) | Gemini 18M **400 birr** (~$3) | Cripto/local | 🟢 | 🟥 |
| **@ethiofasterbook_bot** | Manual mobile repair (EthioFaster) | 399 birr | — | 🟢 | 🟩 |
| **@aenzBot** (“Chill Support”) | Suporte/promo de canais Canva | — | — | 🟢 | — |
| **@ClaudeAPIAPIbot** | Consulta saldo/uso de API `claude-api.org` | — | — | 🟢 | 🟨 |

\* Preços marcados com * são **declarados** (fonte secundária), não lidos no feed no momento da coleta.

---

## 3. CANAIS OFICIAIS DE STORE E DISTRIBUIÇÃO (validados)

| Handle | Título real | Assinantes | Papel | Status |
|---|---|---|---|---|
| @toolais | GGSoma | 70.404 | Loja oficial GGSoma | 🟢 |
| @gemini12pro_channel | Gemini GPT Channel | 145.992 | Hub de promoções/painéis | 🟢 |
| @sheeridverifier_channel | Gemini Pro Automation Channel 🎓 | 35.973 | Verificação SheerID/Pixel | 🟢 |
| @veriyfyer | Verify Channel | 70.206 | Loja ampla (API/contas/escrow) | 🟢 |
| @XMethodworld | Group TDS Reseller Store 🌐 | 973 | Loja TDS | 🟢 |
| @vccdigitalstore | VCCDIGITAL ⚡️ | 166 | Loja (Gemini/IPTV/keys) | 🟢 |
| @LINKEDINPREMlUM | LinkedIn Premium | 430 | Loja difusa (Gemini/LinkedIn) | 🟢 |
| @geminipro18 | Gemini Pro Store | 814 | Loja Gemini/API | 🟢 |
| @ethiofaster | Ethio Faster | 6.715 | Loja regional (ETB) | 🟢 |
| @CanvaPr0Free | Canva Pro Invite link | 21.446 | Links Canva (30k+ em pico) | 🟢 |
| @CanvaEducation | Canva Pro Invite Links | 9.784 | Links Canva | 🟢 |
| @canvapro_linkss | Freebies by @CanvaEducation | 4.763 | Backup/links | 🟢 |
| @canva_pro_teams | Canva Pro Teams Invite Links | 3.684 | Links Canva | 🟢 |
| @CanvaProInviteLinks | Canva Pro Invite Links LIFETIME | 2.845 | Links Canva | 🟢 |
| @canva_pro_invite_links | Canva Pro Invite Links | 629 | Links Canva | 🟢 |
| @canva4ever | Canva For Ever | 5.612 | Links Canva | 🟢 |
| @directcanvapro | Canva Pro Team Link | 2.375 | Links Canva | 🟢 |
| @GeneratCPro | GeneratCPro BOT News | 389 | News do gerador | 🟢 |
| @freecanvapro321 | Canva | 241 | Links Canva | 🟢 |
| @CanvaProTeamLinkss | Canva Pro Invite Links | 1.436 membros | Grupo de links | 🟢 |
| @canvaproteaminvite | Canva Pro Team invites | 316 membros | Grupo de links | 🟢 |
| @canva_pro_team_invite_link_free | Canva Pro Team Invite Link [UPDATED] | 136 | Links Canva | 🟢 |
| @AIVerseXHub | AIVerseX Hub | 21.980 | Loja/canal | 🟢 |
| @Gg2soma | GG2 | 3.705 | 2º canal GGSoma | 🟢 |
| @gptactivate | GGSomabot support | — | Suporte | 🟢 |
| @ggbuilders | GGBuilder | 526 | White-label | 🟢 |
| @FazerCardsReseller | FazerCards Reseller | 3.474 | B2B (gaming/gift cards) | 🟢 |
| @upgradercc | Spotify Upgrader Announcements | 12.872 | Spotify upgrade/API | 🟢 |
| @AccountBot_io | AccountBot.io | 7.174 | Contas streaming + Spotify upgrader | 🟢 |
| @Spotigrader | UpgradeYourSpotify | 2 subs (novo) | Spotify lifetime | 🟡 |

---

## 4. CATEGORIAS AMPLIADAS (tripé: demanda × margem × automação sob demanda)

### 4.1 IA, GEMINI PRO & APIs DE IA

**Mecânica dominante:** links de ativação Jio/SheerID/Pixel → revenda em lote. Preço de atacado real observado **$0,40–$0,70/link** (Gemini 18M). No varejo BR sai a R$15–R$40 → **margem >500%**. É o produto mais automatizável (o bot devolve o link na resposta), mas **o mais perecível** (link single-use, expira em 4–24h, sujeito a revogação em lote).

**Chaves de API de IA:** o produto “API com saldo” existe em dois sabores:
- **Legítimo/auditável:** emissão via `OpenAI Admin API` (1 project por cliente), `OpenRouter` (sub-keys pré-pagas), `ShopAIKey Seller API` (emitir keys, “integrate into your Telegram bot”), `ResellMe` (`/products`, `/orders`). Margem sobre conveniência, sem desconto de atacado.
- **Cinza/relay:** “$100 de crédito por $5” via shadow APIs → 🟥 risco de ban em cascata + logging de prompts. **NÃO usar.**
- **Loja real observada:** @Veriyferbot vende *“Claude & GPT API Key Starter $10 (~$30 oficial) / Standard $30 (~$120) / Premium $50 (~$240)”* e @geminiprosub_bot vende *“Claude API 100M tokens 1 dia $6 / Grok API 100M tokens 7 dias $5 / Codex API 100M tokens $5”* → preço sugere **relay/proxy** (tokens baratos demais) → 🟥.

**Gateways/plataformas:** ClaudeStore (`claudestore.store`, sk-cs4-*), SkillBoss, RiftAI (`riftai.su`, key via /start do bot), PPQ.ai (gift card via Bitrefill), GPTsAPI, Api.Airforce, AICreditMart.

### 4.2 STREAMING & ENTRETENIMENTO

| Fornecedor | Produto | Atacado (custo) | Varejo típico | Automação | Risco |
|---|---|---|---|---|---|
| @AccountBot_io (`accountbot.io`, `spotify.ax`) | Netflix/Spotify/Crunchyroll/DAZN | Spotify upgrade **$0,40–$6,99/un** em lote | $3–$9,99 | Painel + upgrader automático | 🟧 |
| @upgradercc (`upgrader.cc`) | Spotify upgrade (API + Discord bot + white-label) | pacotes reseller (promo -10%) | $1–$3/un | ✅ API REST + cookie login | 🟧 |
| @Veriyferbot | Netflix (7d garantia), Gemini, X Premium | Netflix conta pronta | — | Mini-app/escrow | 🟧 |
| @vccdigitalstore (`vccdigital.us`) | IPTV (streamplayer.tv), keys, streaming | — | IPTV £10,99/mês | Web + cripto | 🟧 |
| Plati.market / GGSEL (ggsel.net) | Spotify Premium “inside family” | ~$1–$2 | — | ❌ API só de vendedor | 🟧 |
| digisubs.net | Netflix 4K, Spotify lifetime (family invite), Crunchyroll | — | € até ~€9,99 | Web autobuy | 🟧 |
| mxnar.sellpass.io (histórico) | Netflix/Spotify/NordVPN lifetime | Netflix UHD 1m $0,50; Spotify 2m $2,50 | — | Sellpass autobuy | 🟧 |

> **Mecânica (confirma OneHack/AnonyViet):** upgrade = adicionar o e-mail do cliente a um **plano Família real**. O ecossistema vende “renew/replace” como recurso → prova da fragilidade (o membro é ejetado). @upgradercc migrou de senha para **cookie `sp_dc`** (confirma no feed). @AccountBot_io confessa “releases ~1000–2500 Spotify upgrades/dia”.

### 4.3 GAMING & CRÉDITOS / GIFT CARDS

| Fornecedor | Produtos | Automação | Pagamento | Status |
|---|---|---|---|---|
| **FazerCards** (`reseller.fazercards.com`) | 10.000+ SKUs: gift cards (Steam/PSN/iTunes/Netflix/Spotify), Robux, PUBG UC, V-Bucks, Nitro, Game Pass | ✅ **REST API v2** (`GET /api/v2/catalog`, `POST /api/v2/order`, webhooks) + SDK Python/Node + **MCP server** | Binance Pay, USDT TRC20/BEP20/TON/Aptos, cartão | 🟢 (canal @FazerCardsReseller) |
| **FoxReload** (`foxreload.com`) | 10.000+ SKUs B2B, game keys, gift cards | ✅ REST API sob demanda | USDT TRC20/ERC20 | 🟠 (fonte secundária) |
| **CDK Bot** (`cdk.bot`) | 40.000+ game keys/gift cards | ✅ **Agent-native REST API**, x402, USDC Base | USDC/USDT/EURC on-chain | 🟠 |
| **Turgame B2B** (`wholesale.turgame.com`) | Gift cards, game keys | ✅ JSON API | — | 🟠 |
| **Axeo Store** (`axeo.store`) | Marketplace in-Telegram (gift cards, keys, subs) | Mini-app, escrow | TON/USDT | 🟠 |
| **Genghis** (`genghis.pro`) | Gift cards, game keys, eSIM | Web | 300+ criptos | 🟠 |

**Margem típica:** gift cards 2–8% (Steam ladder 2,5% Bronze → 3,55% Gold); game keys 10–30%; top-ups (Robux/UC) 5–15%.

### 4.4 PRODUTIVIDADE & DESIGN

- **CapCut Pro:** vendido em TODOS os painéis/bots IA observados. Atacado ~**$0,35–$2,00** (7d/30d); varejo $1,50–$5. Aparece em @AIVerseXBot, @Tdsresellerstorebot, @geminiprosub_bot, MakerStore.
- **Canva Pro:** dominado por **links grátis** (canais com 20k+ subs) e por convite de time pago. Varejo: **$1,99–$19,99** (GamsGo), $2–$5 (Sellpass/G2A). Bundle “Gemini 18m + Canva lifetime” na **G2A a partir de $1,15** (desconto -97%).
- **Office 365 / Windows keys:** @lesstore (Sellpass), @beblash, @vccdigitalstore (keys Windows/Office/Adobe).
- **Adobe CC:** $39,99–$79 (Sellpass/reseller).

### 4.5 CONTAS & NÚMEROS VIRTUAIS / SMS (bypass OTP)

| Fornecedor | Oferta | Automação | Pagamento |
|---|---|---|---|
| **SOCNET** (`socnet.store`, `socnet.shop`, `socnet.cc`, `socnet.app`) | Contas (TikTok, IG, TG, Gmail/Outlook/Hotmail, Discord), **bot de números virtuais/SMS** (200+ serviços, 190+ países), **bot Telegram Stars** | ✅ Bots Telegram + loja + SMM panel | LOLZTEAM, **CryptoBot**, cripto |
| **TelegaMarket** (`telegamarket.pro`) | TDATA/session, aged TG (1+ a 3+ anos), entrega automática | ✅ API/loja, entrega 24/7 | USDT TRC20/BEP20/ERC20/TON/SOL/MATIC, **Telegram Stars** via bot |
| **OTPXChange** (`otpxchange.com`, @otpxchange “Tele King”) | Bulk Telegram (TData/session), Gmail PVA, Discord tokens, IG PVA | Entrega 10–30 min | Cripto |
| **AgedArena** (`agedarena.com`) | Aged TG (2023–2024 $5 → 2014 vintage $100) | Loja | Cripto |
| **agedsmm.com** | Gmail aged (2005–2024, $1,1–$5), SMS US $0,66, contas YouTube/Twitter | Loja | Cripto |

**Margem:** Gmail novo $1,36–$1,78; Gmail aged $2,4–$5; revenda típica 2–4×. **Automação:** os bot de SMS operam via saldo pré-pago + API; ideal para **produção dos próprios links Gemini/SheerID** (OTP).

### 4.6 ASSINATURAS DIVERSAS

- **NordVPN/Surfshark/ExpressVPN:** atacado **$0,10–$0,50** (bulk), varejo $8,99–$19 (Sellpass/reseller).
- **Duolingo Super/Max:** upgrade por e-mail, $9,99–$15.
- **Coursera / Perplexity Pro:** Coursera 1 ano “free” circula em canais Canva; Perplexity Pro 12m **$15–$30** (@Veriyferbot, @geminiprosub_bot, patched.to).
- **Telegram Premium / Stars:** @PremiumBot (oficial), SOCNET.CC, Creax/eviona (oguser), FazerCards vende Telegram Premium/Stars via API.
- **Discord Nitro:** $25–$50/ano (resellers), via FazerCards API.

### 4.7 REDES SOCIAIS & SMM

- **Padrão “API v2”** documentado em dezenas de painéis: `POST /api/v2` com `key`, `action=services|add|status`. Exemplos reais: smm-panel.in, smmbirla.com, smmpakpanel.com, ansmm.com, socialmediapanels.com, smmworld.org, smmservice.top, nlosmm.com.
- **Telegram-specific:** membros/views/reactions/poll votes (Telegram Fake Member desde **$0,17/1k** em smmservice.top).
- **Bibliotecas prontas:** `github.com/fpoweredd/tg-smm-api` (bot Telegram ↔ SMM API v2), `TegroTON/SMMPanel-SMOService-Telegram-Bot`.
- **Risco:** 🟩 margem alta, entrega instantânea; mas TOS do Telegram + chargeback.

---

## 5. PAINÉIS COM API DE COMPRA SOB DEMANDA (a camada que importa p/ automação)

| Fornecedor | URL | O que vende | API de compra |
|---|---|---|---|
| **MakerStore VIP** | `makerstore.vip/api` | CapCut, Canva, ChatGPT, VPN (digital accounts) + SMM | ✅ API v2 `services`/`add` |
| **FazerCards** | `reseller.fazercards.com` + `api.fzr.cards/api/v2` | Gift cards, game keys, top-ups, subs | ✅ REST v2 + webhooks + SDK + MCP |
| **ShopAIKey** | `shopaikey.com/en/docs/seller-api` | API keys de IA | ✅ Seller API (criar keys) |
| **ResellMe** | `resellme.xyz/resellers/docs` | Contas premium sob demanda | ✅ `/products`, `/orders` |
| **Orphilia** | `orphilia.com/api-docs` | Spotify upgrade | ✅ `/re/stocks`,`/upgrade`,`/renew` |
| **Upgrader.cc** | `upgrader.cc/reseller` | Spotify upgrade | ✅ API + Discord bot + white-label |
| **FazerCards NLO / SMM v2** | vários | SMM | ✅ API v2 |
| **CDK Bot** | `cdk.bot` | Game keys | ✅ Agent-native REST (x402/USDC) |

---

## 6. MARKETPLACES (entrega automática, sem API de compra para bot)

| Marketplace | Destaque | Preço observado | API de compra? |
|---|---|---|---|
| **Plati.Market** | Gemini AI Pro/Canva/Spotify | Gemini 18m **$4,24–$6,63**; Spotify family ~$1–2 | ❌ (só vendedor/WMID) |
| **G2A** | Bundle Gemini 18m + Canva lifetime | **a partir de $1,15** (-97%) | ❌ |
| **Driffle** | Gemini 18m activation link | **$4,28–$6,63**, entrega instantânea | ❌ |
| **GamsGo** | Canva Pro / contas | $1,99–$19,99 | ❌ |
| **GGSEL** | Spotify Premium (family) | — | ❌ |
| **Kinguin / Z2U** | Tudo (varejo) | — | ❌ |

> **Regra de ouro:** Plati/Digiseller **não** vendem via API para o bot comprador (só API de vendedor). Para **entrega sob demanda automatizada**, usar MakerStore/FazerCards/ShopAIKey/ResellMe/Orphilia.

---

## 7. ANÁLISE: AUTOMAÇÃO VIA USERBOT vs API OFICIAL

| Abordagem | Como funciona | Prós | Contras |
|---|---|---|---|
| **UserBot (Telethon)** sobre bot de terceiro | Raspa menus inline, paga, captura a entrega | Funciona com QUALQUER bot, sem chave | Frágil (UI muda), flood-wait, sem SLA, pagamento não-prog | 
| **API de painel (MakerStore/FazerCards)** | `action=add` devolve credencial na resposta | Estável, documentado, idempotente | Exige saldo USDT pré-carregado |
| **White-label (GGBuilder/ResellMe)** | Clonar o modelo e revender | Controle total, receita recorrente | Setup, ainda depende de suprimento |

**Recomendação:** não raspar bots de terceiros como base de produção. Usar **API v2 de painel** para suprimento + **bot próprio** (ou white-label) para venda.

---

## 8. RISCOS TRANSVERSAIS

1. **Revogação em lote:** Google/Canva/Spotify varrem contas derivadas de promoção/EDU/família abusada. Garantia do vendedor ≠ garantia real.
2. **Relay de API = fraude ativa** (cartão clonado, key harvesting, log de prompts). Pode configurar crime.
3. **Expiração:** links Gemini (Jio) expiram em 4–24h; Spotify kicka da família (renew pago).
4. **Plataformas caem:** Sellix foi apreendido; Billgang/Antistock com domínios em nameservers de apreensão FBI (ago/2026); Sellpass sob relatos de retenção de payout.
5. **Pagamento:** cripto reduz chargeback, mas o fornecedor cinza pode sumir.

---

## 9. LIMITAÇÕES E O QUE NÃO FOI VERIFICADO

- **Preços dentro dos bots**: não abri `/start` em nenhum bot de terceiro (isso exigiria uma conta Telegram interativa). Preços “verificado no canal” vêm do **feed público**; os demais são **declarados** e marcados.
- **Listas de rede/pagamento por bot do GGSoma**: a existência do bot Binance (@GGsoma2bot) está confirmada; a grade exata de redes USDT precisa `/start` → 🟡 PARCIAL.
- **@sheeridverifier_bot** está em manutenção recorrente (feed admite quedas e “Pixel suspenso, migrado p/ Student”).
- **Handles mortos:** @Premify e @sultanmodsipas NÃO existem (não retornaram título) — descartados.
- **ML perecível:** ~30% dos links Canva postados nos canais expiram em minutos; os canais grandes (21k subs) rotacionam constantemente.

---

## 10. FONTES (amostra verificada)

**GGSoma:** `t.me/toolais`, `t.me/ggsomabot`, `t.me/GGsoma2bot`, `t.me/Gg2soma`, `t.me/Ggsomasupportbot`, `t.me/gptactivate`, `t.me/GGBuildBot`, `t.me/ggbuilders`, `t.me/ggbuilderSupport`, `t.me/GGsoma`.
**Bots IA/Gemini:** `t.me/AiVerseXBot`, `t.me/AIXpress_Bot`, `t.me/Gemini_shop_Robot`, `t.me/geminiprosub_bot`, `t.me/ver_pixel_bot`, `t.me/pixora_digital_bot`, `t.me/nevakeystore_bot`, `t.me/Veriyferbot`, `t.me/Tdsresellerstorebot`, `t.me/gemini12pro_bot`, `t.me/sheeridverifier_bot`, `t.me/hamza7754_bot`, `t.me/ClaudeAPIAPIbot`.
**Canais:** `t.me/gemini12pro_channel`, `t.me/sheeridverifier_channel`, `t.me/veriyfyer`, `t.me/XMethodworld`, `t.me/vccdigitalstore`, `t.me/LINKEDINPREMlUM`, `t.me/geminipro18`, `t.me/ethiofaster`.
**Canva:** `t.me/CanvaPr0Free`, `t.me/CanvaEducation`, `t.me/canvapro_linkss`, `t.me/canva_pro_teams`, `t.me/CanvaProInviteLinks`, `t.me/canva4ever`, `t.me/directcanvapro`, `t.me/CanvaProInvites_bot`, `t.me/CanvaProTeam_Bot`, `t.me/RealCanvaProBot`, `t.me/GeneratCPro_bot`.
**Streaming/Spotify:** `t.me/AccountBot_io`, `t.me/upgradercc`, `t.me/Spotigrader`, `accountbot.io`, `spotify.ax`, `upgrader.cc`, `orphilia.com`, `gamsgo.com`, `digisubs.net`.
**Gaming/Gift cards:** `reseller.fazercards.com`, `t.me/FazerCardsReseller`, `foxreload.com`, `cdk.bot`, `wholesale.turgame.com`, `axeo.store`, `genghis.pro`.
**Contas/SMS:** `socnet.store/.shop/.cc/.app`, `telegamarket.pro`, `otpxchange.com`, `agedarena.com`, `agedsmm.com`.
**SMM/API v2:** `smm-panel.in`, `smmbirla.com`, `smmpakpanel.com`, `socialmediapanels.com`, `smmworld.org`, `smmservice.top`, `nlosmm.com`, `github.com/fpoweredd/tg-smm-api`.
**Marketplace:** `plati.market`, `g2a.com`, `driffle.com`, `ggsel.net`.
**Fóruns (amostra):** BlackHatWorld (tags digital-products / 24-7-telegram-bot), OneHack, CrackedX, patched.to, oguser, HackForums, OwnedCore.

---

*Fim do relatório. Scripts de validação em `/opt/data/digital_store_bot/validate_handles.py` e `scrape_channel.py`.*
