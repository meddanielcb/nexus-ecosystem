# RELATÓRIO DE AUDITORIA — ECOSSISTEMA NEXUS (PlayTV + Store + Webhooks + Alertas)

**Data:** 2026-09-15 (UTC) · **VPS alvo:** 93.127.210.111 · **Ambiente de execução da auditoria:** container (host `9ea3d63ff157`, IP `172.20.0.3`)
**Escopo:** `/opt/data/nexus_playtv_bot`, `/opt/data/digital_store_bot`, `/opt/data/scripts`
**Método:** leitura integral do código, inspeção direta dos SQLite (via `sqlite3` Python), testes empíricos HTTP contra o webhook em `127.0.0.1:8099`, testes de import reais no venv `/opt/hermes/.venv`, reprodução de queries/parses com dados reais do banco, análise de logs em runtime.
**Ressalva de concorrência:** `run_playtv.py` foi modificado às **02:25:06** durante esta auditoria (mtime), indicando sessão de desenvolvimento ativa. Todos os achados abaixo foram confirmados contra o estado dos arquivos no momento da leitura.

---

## 1. VEREDITO EXECUTIVO

**OPERÁVEL COM RESSALVAS CRÍTICAS — NÃO OPERAR EM ESCALA.**

A camada de **segurança de pagamento** melhorou de forma mensurável (BlockBee agora rejeita 401 sem assinatura; PixGet valida HMAC e é idempotente). Porém **três falhas confirmadas hoje continuam ativas e atingem o cliente final**: (a) a entrega "Ativar Smart TV" quebra por coluna inexistente, (b) o funil de lembretes/renovação está 100% morto por formato de data, (c) após 3 testes/24h o sistema entrega credenciais **falsas** silenciosamente.

| Área | Nota | Estado |
|---|---|---|
| Segurança de webhook (BlockBee/PixGet) | 8/10 | ✅ Corrigido e testado (401/HMAC/idempotência) |
| Segurança de webhook (CryptoBot) | 2/10 | ❌ Sem autenticação — bypass confirmado ao vivo |
| Integridade de entrega IPTV (MasterX) | 6/10 | ⚠️ API real funciona, mas fallback entrega acesso falso |
| Fulfillment Nexus Tools (loja) | 1/10 | ❌ 100% mock (links `uuid4`) |
| Consistência de dados / schema | 3/10 | ❌ Schema em código ≠ schema em produção (drift) |
| Resiliência / 24-7 | 6/10 | ⚠️ Supervisor + locks OK; sem alerta de crash-loop |
| Funil de conversão (lembretes) | 1/10 |  Quebrado por formato de data (2.499 erros de log) |
| Infra / DNS / TLS | 3/10 | ❌ Domínios de entrega NXDOMAIN; webhook PIX real não comprovado |

---

## 2. O QUE ESTÁ 100% TESTADO E FUNCIONAL (com evidência)

| # | Item | Evidência |
|---|---|---|
| F1 | **Supervisor 24/7** rodando e orquestrando os 3 serviços | `ps`: PID 33597 (supervisor) → 33604 (`webhook_server`), 33605 (`run_store`), 59341 (`run_playtv`). `supervisor.log` com histórico de auto-restart. |
| F2 | **Trava de instância única do supervisor** | Teste real: 2ª importação → `Supervisor já está rodando em outro processo. Encerrando esta instância.` |
| F3 | **BlockBee rejeita webhook sem assinatura (P0-1 corrigido)** | `POST /api/webhooks/blockbee?order_id=ord_2bde688b` sem `x-ca-signature` → **HTTP 401 `unauthorized`** (02:24:45). Log: `BlockBee Rejeitado: header x-ca-signature ausente`. O exploit do relatório de 12/09 não funciona mais. |
| F4 | **PixGet valida HMAC-SHA256** | Assinatura inválida → 401. Assinatura válida (secret real do `/opt/data/.env`) → **200 `{"received": true}`** (02:25:01). |
| F5 | **Idempotência de webhook PixGet** | Replay do mesmo `X-Pixget-Delivery` → **200 `{"received": true, "status": "already_processed"}`**. |
| F6 | **APScheduler / JobQueue instalado e ativo** | `apscheduler 3.11.3`, `telegram 22.8`. Log do job `push_trial_reminders` executando a cada 60s. O `PTBUserWarning: No JobQueue` foi eliminado. |
| F7 | **Todos os 13 módulos importam sem erro** (import real, não só `py_compile`) | PlayTV: `db, services, masterx_api, tv_vision_ocr, ibo_injector, notifier, pdf_generator, make_vip_card, make_vip_html, run_playtv` → todos OK. Store: `db, services, notifier, i18n, webhook_server, run_store, supervisor` → todos OK. |
| F8 | **Integridade dos SQLite** | `playtv.db` → `integrity_check = ok`; `store.db` → `ok`. |
| F9 | **Colisão de imports resolvida no webhook_server** | `webhook_server.py` L109-117 carrega `playtv/services.py` e `playtv/notifier.py` via `importlib.util.spec_from_file_location`, evitando colisão com `digital_store_bot/services.py`. Testado: o módulo importa e o dispatch `PLAYTV_*` funciona. |
| F10 | **Alerta de venda/resgate de passe avulso agora dispara** | `webhook_server.py` L173-184 (`pack_3_games`) e `run_playtv.py` L202-211 (resgate) chamam `alert_playtv_sale(...)`. Prova de fluxo real no banco: `PLAYTV_6B102044` (pack_3_games, R$14,90, pix, **paid**) + `game_passes` (total 3, restantes 2) + `pass_redemptions` com linha MasterX real (`728163142`/`792556769`). |
| F11 | **Emissão real de linha MasterX funciona** | `pass_redemptions`: usuário `728163142`, senha `792556769`, M3U `http://atmt.space/get.php?...` — emitida pela API, não pelo fallback. Domínios `atmt.space` e `painelmaster.app` resolvem (Cloudflare). |
| F12 | **Sem colisão 409 no estado atual** | Logs históricos tinham 83 (playtv) + 84 (store) ocorrências de `409 Conflict`; **nenhuma** desde os restarts atuais. Uma instância por bot. |

---

## 3. O QUE FOI CORRIGIDO E SUA PROVA

| Correção | Antes | Prova de que está corrigido |
|---|---|---|
| Assinatura RSA obrigatória no BlockBee | Webhook forjado marcava pedido como `paid` | 401 sem header; 401 com assinatura inválida (`test_fake_exploit`) |
| HMAC PixGet + idempotência | Sem validação robusta | 401 inválida / 200 válida / replay `already_processed` |
| `JobQueue` (APScheduler) | `No JobQueue set up` — lembretes nunca rodavam | Job rodando a cada 60s no log |
| Instância única via UNIX-socket lock | 2 cópias por bot → `409 Conflict` em loop | 1 PID por serviço; lock do supervisor testado |
| Colisão de import `services`/`notifier` | `ModuleNotFoundError`/módulo errado carregado | `importlib` por caminho absoluto; imports OK |
| Alerta de passe avulso | Sem alerta de venda/resgate | Alertas adicionados nos 2 pontos; venda real registrada |
| `import time` + query `delivered_item` no PlayTV | `NameError: name 'time' is not defined` (L182); `no such column: delivered_item` (L419) | Arquivo atual tem `import time` (L7) e **não** referencia `delivered_item` no PlayTV (`grep` = vazio) |

---

## 4. FALHAS RESIDUAIS CONFIRMADAS AO VIVO (corrigir antes de operar)

### P0-1 — `ORDER BY id DESC` sobre `orders` quebra a "Ativar Smart TV" e o OCR
`orders` (playtv) **não tem coluna `id`** (PK = `order_id`). Mas:
- `run_playtv.py` **L493** (`auto_activate_tv`) e **L1295** (`photo_handler`) fazem `SELECT ... FROM orders ... ORDER BY id DESC`.
- **Reproduzido:** `sqlite3.OperationalError: no such column: id`.
- Log real: `run_playtv.py line 419 ... no such column: delivered_item` e, na versão atual, a mesma classe de erro em `ORDER BY id`.
- **Impacto:** cliente com plano pago (mensal/trimestral/anual) ou teste grátis, **sem passe resgatado**, clica "Ativar Minha TV" → exceção → nenhuma resposta (não há error handler: 88× `No error handlers are registered`). É o fluxo de maior valor do produto.
- **Correção:** `ORDER BY created_at DESC` (ou adicionar coluna `id`).

### P0-2 — Formato de data mata TODO o funil de lembretes
- **Gravação:** `masterx_api.py` L67 e `services.py` L144 gravam `expires_at` como `"%d/%m/%Y às %H:%M"` (ex.: `13/09/2026 às 01:26`).
- **Leitura:** `run_playtv.py` L1091, L1125, L1158 parseiam com `"%Y-%m-%d %H:%M:%S"`.
- **Reproduzido** com dados reais: `ValueError: time data '15/09/2026 às 08:16' does not match format '%Y-%m-%d %H:%M:%S'`.
- **Prova de volume:** **2.499** ocorrências de `Erro parse date reminder` + 9 de `Erro parse date order reminder` no `run_playtv.log`.
- **Impacto:** lembretes de 30min, aviso de teste expirado, avisos de renovação (3 dias / 1 dia / corte) **nunca são enviados**. Todo o funil de reconversão pós-teste está morto.
- **Correção:** normalizar `expires_at` para ISO 8601 em todos os pontos de gravação (ou parser tolerante a ambos os formatos).

### P0-3 — Filtro de IP do MasterX não é contornado → entrega de credenciais FALSAS
- `masterx_api.py` L24-30 envia `X-Forwarded-For`, `Client-IP`, `X-Real-IP` com IP pseudoaleatório para burlar o limite de 3 testes/24h.
- **O spoofing NÃO funciona.** Log real: `HTTP 409 - {"error":"TRIAL_ALREADY_USED","message":"Este cliente ja utilizou um teste recentemente (ip)...","field":"ip","found":3,"limit":3}`.
- Após o 3º teste do dia (IP único da VPS), `services.generate_iptv_access` cai no fallback (`except`) e gera credenciais **inexistentes** com prefixo `trial_`.
- **Prova no banco:** `free_trials.iptv_username = 'trial_6f0b25'` — teste entregue sem linha real no painel.
- **Impacto:** o cliente recebe acesso que não conecta; sem qualquer sinalização de erro ao usuário.
- **Correção:** obter créditos/API sem limitação de IP (ou rotacionar IP de saída); **nunca** entregar credenciais de fallback — falhar de forma visível para o suporte.

### P0-4 — Domínios de entrega inexistentes (NXDOMAIN)
Verificado agora via DNS:
- `player.nexusplay.tv` → **NXDOMAIN** (usado em `run_playtv L281` e `webhook_server L214` — botão "Assistir Agora")
- `cdn.nexusplay.tv` → **NXDOMAIN** (fallback da rota `/vip/`)
- `cdn-nexus.playtv.live` → **NXDOMAIN**
- `api.pixget.com.br` → **NXDOMAIN**

**Impacto:** botões "Assistir Agora no Navegador" entregues ao cliente levam a domínio morto.

---

### P1-5 — Rota `/vip/<qualquer-coisa>` serve credenciais hardcoded com HTTP 200
**Testado ao vivo:** `GET /vip/NOPE` → **200** e o HTML contém `nexus_vip`, `pass2026` e `cdn.nexusplay.tv`.
`webhook_server.py` L303: fallback `dns="http://cdn.nexusplay.tv:8080", user="nexus_vip", pw="pass2026"` é renderizado quando o pedido não existe. Qualquer string serve uma página VIP com credenciais padrão.
**Correção:** retornar 404 quando o pedido não existir.

### P1-6 — Webhook CryptoBot sem nenhuma autenticação (bypass confirmado)
**Testado ao vivo:** `POST /webhook/cryptobot {"update_type":"invoice_paid","payload":{"payload":"ord_2bde688b"}}` → **HTTP 200** e o pedido foi marcado como `paid` (updated_at = 02:24:45, exatamente o instante do POST), disparando entrega.
> **Nota de auditoria:** o pedido de teste `ord_2bde688b` (produto inexistente `api_openai_120`) foi usado como prova de conceito e **já foi revertido para `pending`** com `delivered_item=NULL`.
`webhook_server.py` L426-440 não valida assinatura/IP/segredo.
**Correção:** validar assinatura do CryptoBot (ou segredo no path) e rejeitar 401.

### P1-7 — Schema drift: `init_db()` não recria o banco real
Teste: `db.init_db()` (PlayTV) em banco limpo vs. banco de produção:
- **Tabelas ausentes no código:** `game_passes`, `pass_redemptions`, `coupons`
- **Colunas ausentes em `orders` (código):** `m3u_url`, `expires_at`, `reminded_3d`, `reminded_1d`, `reminded_expired`

`db.py` (PlayTV) usa apenas `CREATE TABLE IF NOT EXISTS` e **não** contém as colunas/tabelas que `run_playtv.py`, `redeem_game_pass`, `my_access`, `auto_activate_tv` e `coupon_admin_command` consomem. Em redeploy, restauração ou DR, o sistema sobe com `no such table`/`no such column`. Não há migrações versionadas e **não há repositório Git** nos diretórios.
**Correção:** script de migração idempotente (ALTER/CREATE) versionado + backup dos DBs.

### P1-8 — `import sys` ausente → a trava de instância única está quebrada (por acidente funciona)
- `run_playtv.py` **L1406** e `run_store.py` **L544** chamam `sys.exit(0)` no `except` do lock, mas **nenhum dos dois importa `sys`** (`grep "import sys"` = vazio).
- Resultado: uma 2ª instância levanta `NameError` em vez de encerrar limpo. O 409 só não ocorre porque o processo morre antes do `run_polling` — comportamento frágil e não intencional.
- **Correção:** `import sys` em ambos.

### P1-9 — Fulfillment da Nexus Tools é 100% mock
`digital_store_bot/services.py` L156-168 (`purchase_on_demand_adapter`) retorna links gerados com `uuid4()` para Gemini, CapCut, Canva, Telegram Premium e Discord Nitro. Não há chamada a fornecedor/painel. O cliente paga e recebe link falso.

### P1-10 — O webhook PIX real nunca foi comprovado
`webhook_server.log` **não contém nenhum** `POST /api/webhooks/pixget` com 200 legítimo (apenas 401 de teste). A única venda real (`PLAYTV_6B102044`, R$14,90) foi confirmada pelo **polling in-bot** (`check_order_` → `deliver_playtv_order_async` direto), não pelo webhook. Dentro do container, portas **80/443 estão fechadas**; `nexus.pixget.io` resolve para 93.127.210.111 mas a terminação TLS é inverificável daqui. **Risco:** se o cliente não clicar em "Já paguei", a entrega depende do webhook — que não há evidência de funcionar.

---

## 5. RISCOS SECUNDÁRIOS (P2)

- **Reinícios silenciosos do `run_playtv`:** 8 restarts entre 01:26 e 02:22 (`exit code: 0`). O supervisor trata `0, 1, -15, -9, None` como "normal" e **não alerta** → crash-loop silencioso é possível. Restart (L94) sem backoff.
- **Entrega não atômica:** `webhook_server.py` L45-60 faz `SELECT status` → `UPDATE`, sem `UPDATE ... WHERE status!='paid'` + `rowcount`. Entrega dupla sob concorrência (webhook + polling simultâneos).
- **Idempotência só em memória:** `PROCESSED_DELIVERIES` (L30) é um `set` perdido no restart; replay reprocessa efeitos colaterais (alertas, envios).
- **`HEAD` → 501:** `HEAD /api/webhooks/pixget` retorna `501 Unsupported method` (monitoramento externo/UptimeRobot falharia).
- **Botão "Copiar Endereço" não copia:** `copy_addr_<order_id>` cai no `action == "addr"`, não casa com `dns/user/pass` e devolve a mensagem genérica "Código copiado".
- **Valores inconsistentes:** `amount` grava `final_amount` (com fee) no BlockBee do store, USD no PlayTV, e alerta formata como R$ quando `method=="pix"`.
- **Produtos órfãos no `store.db`:** pedidos apontam para `api_openai_120`, `api_openai_20`, `api_deepseek`, `spotify_12m`, que não existem em `products.json`.
- **Tokens/segredos hardcoded no código:** `run_playtv.py` L40; `webhook_server.py` L34, L63, L366, L413, L494; `run_store.py` L547; `notifier.py` (ambos) L12; `services.py` (PlayTV) L11/L14; `masterx_api.py` L9; `services.py` (store) L78 (`BLOCKBEE_API_KEY` real como default). O `/opt/data/.env` já contém todos — remover os defaults.
- **Logs sem rotação:** `run_playtv.log` 3,4 MB e `run_store.log` 2,6 MB.
- **Sem repositório Git / versionamento** dos bots.
- **IPs de scanner** acessando 8099 (`/wp-login.php`, `/.well-known/...`) — o servidor responde 404 para tudo; sem rate-limit/WAF.

---

## 6. PONTOS CEGOS RESIDUAIS (não verificáveis neste ambiente)

1. **Terminação TLS / reverse proxy público** em `nexus.pixget.io` (Caddy/Cloudflare Tunnel) — portas 80/443 fechadas no container.
2. **URLs de callback efetivamente cadastradas** nos painéis PixGet e BlockBee.
3. **Contrato real da API PixGet** (`/api/v1/checkout` vs. `/v1/charges`) e o secret HMAC configurado do lado do provedor.
4. **Comportamento sob carga/concorrência** (não houve teste de carga).
5. **Estado do `run_playtv.py` após a edição de 02:25:06** — re-verificar os itens P0-1/P0-2 após congelamento do código.
6. **Créditos/limite da conta MasterX** e o limite real de 3 testes/24h por IP.

---

## 7. CHECKLIST DE TESTES DE PONTA A PONTA

| # | Teste | Status | Observação |
|---|---|---|---|
| 1 | Supervisor sobe e mantém 3 serviços | ✅ PASSA | 4 PIDs ativos |
| 2 | Trava de instância única do supervisor | ✅ PASSA | 2ª instância encerra |
| 3 | Trava de instância única dos bots (`sys`) | ❌ FALHA | `NameError` (P1-8) |
| 4 | Webhook BlockBee sem assinatura → 401 | ✅ PASSA | Testado |
| 5 | Webhook PixGet assinatura inválida → 401 | ✅ PASSA | Testado |
| 6 | Webhook PixGet assinatura válida → 200 | ✅ PASSA | Secret do `.env` |
| 7 | Idempotência de webhook (replay) | ✅ PASSA | `already_processed` |
| 8 | Webhook CryptoBot autenticado | ❌ FALHA | Sem auth (P1-6) |
| 9 | JobQueue/lembretes executam | ⚠️ PARCIAL | Job roda, mas parse falha (P0-2) |
| 10 | `/vip/<inexistente>` → 404 | ❌ FALHA | Retorna 200 com creds padrão (P1-5) |
| 11 | Emissão de linha MasterX (trial) | ⚠️ PARCIAL | Funciona até 3/24h; depois fallback falso (P0-3) |
| 12 | Emissão de linha MasterX (paga) | ✅ PASSA | Linha real no `pass_redemptions` |
| 13 | "Ativar Smart TV" (cliente com passe) | ✅ PASSA | Via `pass_redemptions` |
| 14 | "Ativar Smart TV" (cliente com plano pago) | ❌ FALHA | `ORDER BY id` (P0-1) |
| 15 | OCR de foto da TV (`photo_handler`) |  FALHA | Mesmo `ORDER BY id` (P0-1) |
| 16 | Venda PIX PlayTV → entrega | ⚠️ PARCIAL | Entregue via polling, não via webhook (P1-10) |
| 17 | Alerta de venda de passe avulso (`@Alerta_nexusbot`) | ✅ PASSA | Código + venda real |
| 18 | Alerta de resgate de passe | ✅ PASSA | Código + log |
| 19 | Renovação automática (3d/1d/corte) | ❌ FALHA | Parse de data (P0-2) |
| 20 | Botão "Copiar Endereço" copia o endereço | ❌ FALHA | Ação não implementada |
| 21 | Fulfillment real dos produtos da loja | ❌ FALHA | 100% mock (P1-9) |
| 22 | Recriação do banco do zero (`init_db`) | ❌ FALHA | 3 tabelas + 5 colunas ausentes (P1-7) |
| 23 | Integridade SQLite | ✅ PASSA | `integrity_check = ok` |
| 24 | Import de todos os módulos | ✅ PASSA | 13/13 OK |
| 25 | Domínios de entrega resolvem | ❌ FALHA | 3 NXDOMAIN (P0-4) |

**Resumo do checklist: 11 ✅ · 3 ⚠️ · 11 ❌**

---

## 8. AÇÃO RECOMENDADA (ordem de prioridade)

1. **Corrigir `ORDER BY id DESC` → `created_at DESC`** em `run_playtv.py` L493 e L1295 (P0-1). Impacto imediato no fluxo de maior valor.
2. **Normalizar `expires_at` para ISO 8601** nos pontos de gravação (`masterx_api.py` L67, `services.py` L144) — reativa todo o funil (P0-2). Considerar migração dos registros existentes.
3. **Remover o fallback de credenciais falsas** do PlayTV e tratar a falha do MasterX de forma visível (P0-3); resolver o limite de 3 testes/24h por IP.
4. **Implementar autenticação no webhook CryptoBot** (P1-6).
5. **`/vip/` → 404 para pedido inexistente** (P1-5) e trocar os domínios mortos nos botões de acesso (P0-4).
6. **`import sys`** em `run_playtv.py` e `run_store.py` (P1-8).
7. **Migração de schema idempotente e versionada** + backup automático dos DBs (P1-7).
8. **Tornar a entrega atômica** (`UPDATE ... WHERE status!='paid'` + `rowcount`) e persistir idempotência em tabela SQLite.
9. **Rotacionar todos os tokens/segredos** e remover os defaults hardcoded do código.
10. **Garantir/validar o wire real do webhook PixGet** (TLS persistente, URL fixa no provedor) e monitorar com `GET` (não `HEAD`).
11. Fazer **backoff + alerta** no supervisor para qualquer restart (mesmo `exit code: 0`) e habilitar rotação de logs.
12. Só então **integrar fornecedores reais** para a loja (P1-9).

---

## 9. ANEXO — EVIDÊNCIAS BRUTAS

```
# Processos ativos
33597 supervisor.py   33604 webhook_server.py   33605 run_store.py   59341 run_playtv.py   (1 instância cada)

# Testes HTTP ao vivo (127.0.0.1:8099)
GET  /vip/NOPE                                  -> 200  (contém nexus_vip, pass2026, cdn.nexusplay.tv)
GET  /vip/THIS_ORDER_DOES_NOT_EXIST             -> 200
POST /api/webhooks/pixget  (sig inválida)       -> 401 {"error":"Invalid HMAC signature"}
POST /api/webhooks/pixget  (sig válida .env)    -> 200 {"received": true}
POST /api/webhooks/pixget  (replay)             -> 200 {"received": true,"status":"already_processed"}
POST /api/webhooks/blockbee?order_id=...        -> 401 unauthorized
POST /webhook/cryptobot    (sem auth)           -> 200 OK   [marcou pedido como paid -> revertido]
HEAD /api/webhooks/pixget                       -> 501

# Reproduções em dados reais
sqlite3 OperationalError: no such column: id        (orders: PK=order_id, sem coluna id)
ValueError: time data '15/09/2026 às 08:16' does not match format '%Y-%m-%d %H:%M:%S'
init_db() em DB limpo -> faltam tabelas ['coupons','game_passes','pass_redemptions']
                      -> orders sem ['m3u_url','expires_at','reminded_3d','reminded_1d','reminded_expired']
integrity_check: playtv=ok  store=ok

# DNS (hoje)
nexus.pixget.io -> 93.127.210.111 | atmt.space/painelmaster.app -> Cloudflare | pixget.app -> 34.111.179.208
player.nexusplay.tv / cdn.nexusplay.tv / cdn-nexus.playtv.live / api.pixget.com.br -> NXDOMAIN

# Logs (contagens)
run_playtv.log : 2499 'Erro parse date reminder' | 88 'No error handlers are registered'
                 2 'NameError: name time is not defined' | 2 'MasterX HTTP 409 TRIAL_ALREADY_USED'
                 83 '409 Conflict' (histórico) | 1 'no such column: delivered_item' | 1 'database is locked'
run_store.log  : 84 '409 Conflict' (histórico) | 85 'No error handlers'
webhook_server.log: 283 'OSError: Address already in use' (histórico) | 2 'No module named make_vip_html'
supervisor.log : 8 restarts de run_playtv (01:26→02:22), todos 'exit code: 0'

# Bancos
playtv.db : orders=2 (PLAYTV_6B102044 pack_3_games paid R$14,90 pix; PASS_671901048_... paid)
            game_passes=1 (total 3, restantes 2) | pass_redemptions=1 (linha real 728163142)
            free_trials=1 (iptv_username='trial_6f0b25' <- FALLBACK falso) | coupons=1 (TESTE10) | users=1
store.db  : orders=5 (2 paid, 3 pending; 4 product_ids órfãos) | inventory=0 | users=0
```