# Manual de Arquitetura & Implementação do Motor de E-commerce Autônomo (Nexus Engine)

Este manual documenta a arquitetura técnica completa, o fluxo de operação e o passo a passo para replicar e implantar esta mesma estrutura de vendas autônoma para **qualquer outro serviço, produto digital, assinatura ou checkout** (ex: Clínica Nutra, canais VIP do CIPHER, créditos de agentes na AgentIA).

---

## 1. Visão Geral da Arquitetura

O sistema é um motor de checkout desacoplado e autônomo (*headless commerce*) construído para operar 24/7 em Linux (VPS), sem dependência de plataformas SaaS de terceiros (como Shopify, Kiwify ou Hotmart) e sem verificação manual de pagamentos.

```
                  ┌─────────────────────────────────────────────────────────┐
                  │                 CLIENTE / TELEGRAM                      │
                  └────────────┬───────────────────────────────▲────────────┘
                               │                               │
                               │ 1. Seleciona Produto          │ 5. Entrega Imediata
                               │    & Método (PIX / Cripto)    │    do Produto / Acesso
                               ▼                               │
                  ┌───────────────────────────────┐            │
                  │    BOT TELEGRAM DE VENDAS     │            │
                  │        (run_store.py)         │            │
                  └───────────────┬───────────────┘            │
                                  │                            │
             ┌────────────────────┴───────────────────┐        │
             ▼                                        ▼        │
   [ Gateway PIX (Pixget) ]               [ Gateway Cripto (BlockBee) ]
   • Cria Cobrança PIX                    • Gera Endereço de Carteira
   • Retorna Copia e Cola + QR Code       • BSC, Solana, Base, Poly, BTC, ETH
             │                                        │
             │ Cliente Paga                           │ Cliente Transfere
             ▼                                        ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │                       INTERNET / BLOCKCHAIN                            │
   └──────────────────────────────┬─────────────────────────────────────────┘
                                  │ Notificação de Pagamento (Webhook HTTP POST)
                                  ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │                          CADDY REVERSE PROXY                           │
   │            (nexus.pixget.io com SSL Automático Let's Encrypt)          │
   └──────────────────────────────┬─────────────────────────────────────────┘
                                  │ Encaminha para Porta Interna 8099
                                  ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │                      SERVIDOR DE WEBHOOKS LOCAL                        │
   │                        (webhook_server.py)                             │
   │  1. Valida Assinatura Criptográfica:                                   │
   │     - PIX: HMAC-SHA256                                                 │
   │     - Cripto: RSA-SHA256 (Chave Pública BlockBee)                      │
   │  2. Garante Idempotência (Evita processar 2x o mesmo pedido)           │
   │  3. Atualiza Pedido no SQLite para status 'paid'                       │
   │  4. Executa Entrega do Produto / Dispara Webhook de Ativação           │
   └──────────────┬───────────────────────────────────────────┬─────────────┘
                  │                                           │
                  ▼                                           ▼
   ┌──────────────────────────────┐          ┌──────────────────────────────┐
   │  DISPARO NO CHAT DO CLIENTE  │          │  BOT DE ALERTA PRIVADO       │
   │   (Mensagem + Botão Menu)    │          │  (@Alerta_nexusbot p/ Daniel)│
   └──────────────────────────────┘          └──────────────────────────────┘
```

---

## 2. Componentes e Estrutura de Arquivos

Para subir uma nova loja ou serviço, a árvore de diretórios padrão é:

```text
/opt/data/<nome_do_projeto>/
├── .env                       # Variáveis de ambiente e segredos de API
├── data/
│   └── store.db               # Banco de dados SQLite (pedidos, usuários, línguas)
├── logs/                      # Logs de execução em tempo real
│   ├── run_store.log
│   ├── webhook_server.log
│   └── supervisor.log
├── blockbee_pubkey.pem        # Chave pública RSA da BlockBee para validar webhooks
├── db.py                      # Conexão SQLite e criação das tabelas
├── products.json              # Catálogo de produtos/serviços e regras de entrega
├── i18n.py                    # Dicionário multilíngue (PT, EN, ES)
├── services.py                # Integração com APIs de pagamento (Pixget, BlockBee, CryptoBot)
├── notifier.py                # Módulo de telemetria e alertas para o Telegram privado
├── webhook_server.py          # Receptor HTTP de confirmações e entregador automático
├── run_store.py               # Bot de vendas e interface do usuário
└── supervisor.py              # Watchdog autônomo que monitora e reinicia processos 24/7
```

---

## 3. Passo a Passo de Implementação para um Novo Serviço

### Passo 1: Modelar o Catálogo (`products.json`)
Cada serviço vendido precisa apenas de um ID, categoria, nomes/descrições nos 3 idiomas, preços em BRL/USD e o modelo de entrega:

```json
{
  "plano_vip_nutra_1m": {
    "category": "assinaturas",
    "name": "Acompanhamento Nutra VIP (Mensal)",
    "description": "Acesso ao grupo fechado de protocolos e suporte clínico.",
    "price_brl": 197.00,
    "price_usd": 38.00,
    "delivery_type": "link_or_code",
    "instructions": "✅ Seu plano foi ativado!\nAcesse seu grupo exclusivo pelo link: {item}"
  },
  "protocolo_gex_cipher": {
    "category": "trading",
    "name": "Setup GEX Pro diário",
    "description": "Canal de alertas institucionais de Gamma Flip.",
    "price_brl": 290.00,
    "price_usd": 55.00,
    "delivery_type": "invite_link",
    "instructions": "🚀 Acesso liberado ao CIPHER VIP:\nConvite de uso único: {item}"
  }
}
```

---

### Passo 2: Configurar o Mecanismo de Entrega (`webhook_server.py`)
A função `deliver_order_async(order_id)` é o ponto central onde o produto é entregue após o pagamento confirmado. Dependendo do serviço, você pode plugar:

1. **Link de Convite de Canal/Grupo VIP do Telegram:**
   ```python
   # Gera um link de convite de uso único com expiração
   invite = requests.post(
       f"https://api.telegram.org/bot{BOT_TOKEN}/createChatInviteLink",
       json={"chat_id": VIP_CHANNEL_ID, "member_limit": 1}
   ).json()
   delivered_item = invite["result"]["invite_link"]
   ```
2. **Entrega de Licença / Chave / E-book:**
   - Pode puxar de um banco de dados de chaves pré-cadastradas ou gerar dinamicamente via script.
3. **Liberação de Cadastro em Webhook Externo:**
   - Fazer um `POST` para sua própria API (ex: plataforma web da Nutra ou AgentIA) ativando a conta do cliente via e-mail ou Telegram ID.

---

### Passo 3: Configurar os Gateways de Pagamento

1. **PIX (Pixget):**
   - No `services.py`, a função `create_pixget_invoice` envia o valor em centavos, descrição e webhook callback URL.
   - Retorna o `pix_code` (copia e cola) e renderiza localmente um QR Code em imagem via biblioteca `qrcode` do Python para enviar no chat.
2. **Cripto Auto-Forwarding (BlockBee):**
   - Consulta taxas de rede em tempo real (`get_network_fee_estimate`).
   - Aplica a **regra de taxa**: taxas $\le$ $0.60$ são absorvidas (preço facial puro); taxas $>$ $0.60$ são discriminadas e somadas.
   - Moedas voláteis (BTC, ETH) **sempre** consultam o endpoint `/convert/?value=X&from=usd` para gerar a fração exata na moeda, sem erros de valor.
3. **Cripto Telegram Wallet (CryptoBot):**
   - Cria invoice via API oficial do `@CryptoBot` e entrega o link direto para o cliente pagar com seu saldo no Telegram em 1 clique.

---

### Passo 4: Configurar o Domínio e SSL via Caddy

No servidor Linux, adicione o bloco no `/etc/caddy/Caddyfile`:

```caddy
nexus.pixget.io {
    reverse_proxy 127.0.0.1:8099
}
```

Execute `caddy reload`. O Caddy gera e renova os certificados SSL da Let's Encrypt automaticamente, garantindo que o webhook responda sempre em HTTPS válido exigido pelos gateways.

---

### Passo 5: Configurar o Watchdog e Auto-Start na VPS

Para que o serviço seja **100% autônomo** e não precise de intervenção manual caso a máquina reinicie ou dê pane:

1. **Supervisor (`supervisor.py`):**
   - Roda como processo pai e monitora a cada 5 segundos se o bot e o servidor de webhooks estão vivos.
   - Se um processo cair, reinicia imediatamente e dispara um aviso para o `@Alerta_nexusbot`.
2. **Auto-Start no Boot da VPS (Hook):**
   - Em `/opt/data/hooks/autostart_<servico>/HOOK.yaml`:
     ```yaml
     name: autostart_nexus_store
     description: Inicia automaticamente no boot do container/gateway
     events:
       - gateway:startup
     ```
   - No `handler.py`, dispara o `supervisor.py` em background sem travar a inicialização da máquina.

---

### Passo 6: Conectar a Telemetria Privada (`notifier.py`)

Crie um bot no `@BotFather` para uso exclusivo seu (como o `@Alerta_nexusbot`) e cadastre seu `chat_id`. 
Cada venda confirmada ou alerta de infraestrutura enviará uma notificação no formato:

```text
💰 NOVA VENDA CONFIRMADA!

📦 Produto: Acompanhamento Nutra VIP (Mensal)
💵 Valor: R$ 197,00
💳 Método: PIX
👤 Cliente: @cliente (ID: 123456789)
🆔 Pedido: ORD_PIX_5521
✅ Entrega sob demanda processada com sucesso.
```

---

## 4. Checklist Rápido para Lançar um Novo Produto

- [ ] Cadastrar o item no `products.json` com nome, descrição, preços e instruções.
- [ ] Adicionar os textos e botões no `i18n.py` (PT, EN e ES).
- [ ] Definir a lógica de entrega dentro de `deliver_order_async` no `webhook_server.py`.
- [ ] Verificar se as carteiras de repasse ou credenciais de gateway estão ativas.
- [ ] Executar o script de auditoria e teste de dry-run para validar consistência dos valores.
- [ ] Reiniciar o `supervisor.py` para carregar o novo catálogo.

---

O manual foi documentado e salvo em `/opt/data/digital_store_bot/MANUAL_IMPLEMENTACAO_SISTEMA.md`. Esse modelo permite subir qualquer novo negócio em poucas horas reaproveitando toda a base testada e validada.