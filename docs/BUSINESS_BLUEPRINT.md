# 📘 BUSINESS_BLUEPRINT & MASTER PLAN
### Ecossistema Nexus: Nexus Tools, Nexus PlayTV, Concierge Smart TV e Infraestrutura Autônoma

> **Aviso para Agentes de IA (Claude Code, Hermes, Cursor, etc.):**
> Este documento é o **Guia Mestre de Continuidade Operacional** do ecossistema Nexus. Qualquer agente que assumir a manutenção, evolução ou depuração dos bots e da infraestrutura deve ler este arquivo primeiro. Ele detalha a visão do fundador Daniel (@meddanielcb), as regras estritas de negócios, os handles dos bots, a infraestrutura da VPS e o plano de expansão.

---

## 1. O Fundador & Filosofia de Operação
- **Fundador:** Daniel (@meddanielcb) — médico empreendedor (fundador da clínica Nutra em Balneário Camboriú), especialista em inteligência artificial e investidor crypto.
- **Princípios Operacionais:**
  1. **Qualidade Absoluta > Velocidade:** Sem gambiarras ou soluções paliativas. O código e a UX devem ter padrão de excelência técnica.
  2. **100% Autônomo (Zero Passo Manual):** O fundador odeia intervenção humana no meio da operação. O fluxo — do catálogo ao pagamento PIX/Cripto, ativação de lista/chave e entrega — deve rodar sozinho 24/7.
  3. **Zero Estoque Parado:** Não compramos linhas de IPTV ou contas digitais antecipadamente para evitar consumo de prazo e prejuízo. A ativação no upstream ocorre na confirmação do pagamento.
  4. **Entregas VIP Clicáveis:** O cliente nunca recebe instruções burocráticas ou PDFs estáticos nos quais precise digitar códigos manualmente. Tudo é entregue via Cartão VIP Web interativo com cópia em 1-clique e player embutido.

---

## 2. Mapa Geral de Bots e Telemetria

| Bot / Canal | Handle | Função no Ecossistema |
|---|---|---|
| **Nexus PlayTV** | `@Nexus_playtvbot` | Venda de assinaturas IPTV P2P anti-bloqueio, passes de jogos e concierge Smart TV. |
| **Nexus Tools** | `@botnexustools_bot` | Loja de ferramentas digitais, contas Gemini Pro 5TB, Canva Pro e créditos de API. |
| **Alerta Nexus** | `@Alerta_nexusbot` | Canal privado de telemetria direcionado exclusivamente ao Telegram de Daniel (`ID: 671901048`). |

---

## 3. Infraestrutura & Servidores na VPS

- **Servidor:** Hostinger VPS `srv1323582` (IP `93.127.210.111`, Ubuntu 24.04).
- **Domínio & SSL:** `https://nexus.pixget.io` operando sob proxy reverso **Caddy** com certificado SSL automático Let's Encrypt.
- **Gateway de Pagamento PIX:** **Pixget** (`pixget.app` / `pixget.com.br`) — infraestrutura própria do Daniel na Hostinger (sem Cloudflare, assinatura HMAC-SHA256 e consulta de CPF na Receita Federal).
- **Gateway Cripto:** **BlockBee** (USDT, BTC, LTC, SOL) com assinatura RSA-SHA256.
- **Servidor Master IPTV:** `man77.work` (Porta 80) com credenciais Xtream Codes e grade completa de canais.
- **Portas e Processos Internos:**
  - `webhook_server.py`: Porta interna `8099` (mapeada para `https://nexus.pixget.io`). Trata callbacks de pagamento e gera cartões VIP.
  - `supervisor.py`: Watchdog contínuo que monitora a saúde dos bots a cada 60 segundos e reinicia processos em caso de falha.

---

## 4. O Sistema de Concierge Smart TV (IBO Player + OCR)

Para eliminar a maior barreira de entrada do cliente leigo em Smart TVs (Samsung Tizen e LG webOS):
1. O cliente instala o **IBO Player** na TV e envia uma simples **foto da tela** no chat do `@Nexus_playtvbot`.
2. O `photo_handler` (implementado em `run_playtv.py`) baixa a imagem na VPS, executa **Visão Computacional / OCR** e extrai automaticamente o **Device ID** (MAC) e a **Device Key**.
3. O script `ibo_injector.py` acessa a nuvem do IBO Player (`iboplayer.com`), resolve o captcha matemático em SVG via **2Captcha** (saldo ativo e configurado) e injeta a playlist M3U diretamente na TV do cliente.

---

## 5. Passes Avulsos de Jogos & Futebol (R$ 14,90)

- Para clientes que querem apenas assistir a uma partida específica sem assinar o plano mensal.
- Gerenciado no SQLite (`game_passes`) com código de resgate único de 16 caracteres.
- O cliente digita `/resgatar <codigo>` ou acessa o link VIP direto, liberando o streaming pelo período da rodada.

---

## 6. Diretrizes para Agentes de IA Futuros

1. **Persistência de Sessão no Painel P2Braz (`controle.vip`):**
   - O painel opera sob Cloudflare Turnstile. O login do revendedor `danielcb` gera token JWT com expiração estrita de 60 minutos (`exp - iat = 3600s`).
   - Para ligar a criação automática de linhas oficiais no endpoint `/users` ou `/trial_users`, o agente deve utilizar o **Scrapling + Patchright** já instalados na VPS para renovar a sessão ou integrar via módulo de webhook de revendedor.
2. **Adição de Novos Produtos:**
   - Para adicionar produtos no Nexus PlayTV: editar `nexus_playtv_bot/products_playtv.json`.
   - Para adicionar produtos no Nexus Tools: editar `digital_store_bot/products.json` e as traduções em `i18n.py`.
3. **Telemetria Obrigatória:**
   - Toda venda, erro crítico de webhook ou falha de upstream deve obrigatoriamente chamar a função `notify_admin` em `notifier.py` para notificar Daniel no Telegram.
