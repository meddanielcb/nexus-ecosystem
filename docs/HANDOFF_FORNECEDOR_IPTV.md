# HANDOFF TÉCNICO: INTEGRAÇÃO FORNECEDOR IPTV / P2P

> **Status:** Documento técnico de referência e handoff operacional.  
> **Data:** 13/09/2026  
> **Repositório:** `meddanielcb/nexus-ecosystem`  
> **Finalidade:** Mapear rigorosamente o estado real da integração com o painel fornecedor de IPTV/P2P, endpoints verificados, mecanismos de autenticação, regras comerciais comprovadas e pendências em aberto.

---

## 1. Fornecedor e Painel

- **Nome Comercial do Fornecedor / Ecossistema:** CENTRAL / FIVE / P2BRAZ (Ecossistema unificado).
- **URL Atual do Painel Web:** `https://controle.vip/login`
- **Backend API REST:** `https://api.controle.fit/api`
- **DNS / Servidores de Streaming Homologados no Manual Oficial:**
  - `http://man77.work` (Porta 80) — utilizado ativamente no gerador de credenciais do projeto.
  - `http://5ce.me`
  - `http://smart.cms-central.ovh`
  - `http://cdn.5central.me`
  - `http://cms-central.co` (Porta 80)
- **Confirmação do Sistema Utilizado (Central/Five vs P2Braz):**
  - **Sistema Híbrido Unificado:** O painel oficial (`controle.vip`) opera de forma híbrida. Ele atende simultaneamente as linhas **Five/Central (IPTV via Xtream Codes / M3U)** e **P2Braz (Streaming P2P via aplicativo dedicado)** sob a mesma base de revenda e autenticação.
  - No código atual do bot (`run_playtv.py` e `services.py`), a entrega imediata está gerando credenciais no padrão Xtream Codes apontando para o servidor master `http://man77.work`, com suporte ao aplicativo P2Braz documentado nos manuais e códigos de Downloader Fire TV / Android.

---

## 2. Integração: Endpoints e Métodos

A auditoria dos bundles JavaScript de produção do frontend (`https://controle.vip/assets/`) e testes de rede revelaram as rotas da API REST (`https://api.controle.fit/api`).

### 2.1 Autenticação de Operador / Revendedor
- **Método / Rota:** `POST https://api.controle.fit/api/auth/sign-in`
- **Status de Verificação:** **Efetivamente verificado em rede.** Requer validação prévia de Cloudflare Turnstile.
- **Exemplo de Requisição (Dados Fictícios):**
```http
POST /api/auth/sign-in HTTP/1.1
Host: api.controle.fit
Content-Type: application/json
Origin: https://controle.vip

{
  "username": "usuario_revenda_exemplo",
  "password": "senha_forte_exemplo",
  "cf-turnstile-response": "0.abcdef1234567890_token_turnstile_exemplo"
}
```
- **Exemplo de Resposta de Sucesso (Dados Fictícios):**
```json
{
  "token": "TOKEN_JWT_FICTICIO_EXEMPLO",
  "user": {
    "id": 12345,
    "username": "usuario_revenda_exemplo",
    "role": "reseller"
  }
}
```

### 2.2 Criação de Teste Grátis (Trial)
- **Método / Rota Autenticada:** `POST https://api.controle.fit/api/trial_users`
- **Status de Verificação:** Verificado no bundle frontend (`index-tnLNlOks.js`). Requer `Authorization: Bearer <TOKEN>`.
- **Exemplo de Requisição (Dados Fictícios):**
```http
POST /api/trial_users HTTP/1.1
Host: api.controle.fit
Authorization: Bearer <TOKEN_JWT_AQUI>
Content-Type: application/json

{
  "package_id": 101,
  "notes": "Teste solicitado via bot Telegram"
}
```
- **Exemplo de Resposta (Dados Fictícios):**
```json
{
  "success": true,
  "id": 987654,
  "username": "tst_98765",
  "password": "pwd_43210_exemplo",
  "expires_at": "2026-09-13T23:00:00Z"
}
```

- **Rotas de Gestão de Testes pelo Módulo Automático:**
  - `GET https://api.controle.fit/api/trials/settings`: Consulta modo de teste (`auto`, `manual`, `off`), pacote configurado e filtro de WhatsApp.
  - `PUT https://api.controle.fit/api/trials/settings`: Atualiza configurações do robô de testes.
  - `GET https://api.controle.fit/api/trials/requests`: Lista solicitações pendentes de teste.
  - `POST https://api.controle.fit/api/trials/requests/:id/approve`: Aprovação manual de solicitação.
  - `POST https://api.controle.fit/api/trials/requests/:id/reject`: Recusa de solicitação de teste.

### 2.3 Criação de Linha Paga (Cliente Oficial)
- **Método / Rota:** `POST https://api.controle.fit/api/users`
- **Status de Verificação:** Verificado estruturalmente no bundle React do painel. Requer `Authorization: Bearer <TOKEN>`.
- **Exemplo de Requisição (Dados Fictícios):**
```http
POST /api/users HTTP/1.1
Host: api.controle.fit
Authorization: Bearer <TOKEN_JWT_AQUI>
Content-Type: application/json

{
  "username": "cliente_oficial_exemplo",
  "password": "senha_segura_exemplo",
  "package_id": 201,
  "screens": 1,
  "duration_months": 1
}
```
- **Exemplo de Resposta (Dados Fictícios):**
```json
{
  "success": true,
  "user": {
    "id": 112233,
    "username": "cliente_oficial_exemplo",
    "password": "senha_segura_exemplo",
    "status": "1",
    "expires_at": "2026-10-13T20:00:00Z"
  }
}
```

### 2.4 Consulta de Linhas e Status
- **Método / Rota:** `GET https://api.controle.fit/api/users` ou `GET https://api.controle.fit/api/users/:id`
- **Status de Verificação:** Rota base presente nos módulos do painel. Filtros suportados identificados no código:
  - `type`: `trial` (teste) ou `normal` (cliente regular).
  - `status`: `1` (ativo), `0` (bloqueado), `3` (expirado), `4` (não expirado).
  - `expiry`: `today`, `3days`, `7days`, `15days`, `30days`.
- **Exemplo de Requisição (Dados Fictícios):**
```http
GET /api/users?search=cliente_oficial_exemplo HTTP/1.1
Host: api.controle.fit
Authorization: Bearer <TOKEN_JWT_AQUI>
```

### 2.5 Renovação de Linhas
- **Método / Rota:** **Não confirmado** se existe endpoint exclusivo (ex: `POST /api/users/:id/renew`) ou se a renovação é feita via `PUT /api/users/:id` alterando prazo/adicionando meses.
- **Evidência Operacional:** O manual do revendedor indica o tutorial `abrela.me/renovarteste` e `abrela.me/adicionarmeses`. O endpoint REST exato permanece **não confirmado**.

### 2.6 Configuração de Telas Adicionais
- **Método / Rota:** **Não confirmado** via endpoint isolado. No modelo de dados de criação de usuário há o parâmetro de conexões simultâneas (`screens` / conexões híbridas), mas a alteração posterior via API direta permanece **não confirmada**.

---

## 3. Autenticação e Gestão de Sessão

- **Mecanismo:** JSON Web Token (JWT) padrão `Bearer <TOKEN>` no header HTTP `Authorization`.
- **Duração da Sessão:** **Exatamente 60 minutos (3600 segundos)**. Confirmado pela análise matemática do payload JWT (`exp - iat = 3600`).
- **Mecanismo de Renovação:**
  - O backend **não expõe endpoint de refresh token sem desafio**.
  - A renovação autônoma exige novo disparo de login em `POST /api/auth/sign-in` com solução de desafio anti-bot (Cloudflare Turnstile) a cada 50–55 minutos.
- **Onde as Credenciais Estão Configuradas:**
  - As credenciais de revenda residem em variáveis de ambiente da VPS e arquivos locais de configuração protegidos (`.env` e arquivo de configuração de chaves).
  - **Nenhum valor real de senha, token ou chave está versionado no repositório Git.**
- **Nomes das Variáveis de Configuração Recomendadas:**
  - `P2BRAZ_USER`: Identificador do revendedor no painel.
  - `P2BRAZ_PASS`: Senha do revendedor no painel.
  - `P2BRAZ_API_BASE`: `https://api.controle.fit/api`
  - `P2BRAZ_PANEL_URL`: `https://controle.vip`
  - `TWOCAPTCHA_API_KEY`: Chave de API do serviço de resolução de captchas (utilizada no injetor do IBO Player).

---

## 4. Regras Comerciais Confirmadas (Manual Oficial Revenda FIVE / CENTRAL)

As regras abaixo foram extraídas diretamente do documento oficial homologado da fornecedora (`Manual Revenda FIVE _ CENTRAL_.pdf`):

1. **Preços Mínimos Obrigatórios de Venda ao Cliente Final:**
   - **R$ 30,00** para listas CENTRAL / FIVETV (IPTV).
   - **R$ 35,00** para P2BRAZ (P2P).
   - *Penalidade contratual:* É expressamente proibida a venda abaixo do valor de tabela ou em modelo pós-pago. O desrespeito acarreta exclusão do painel da revenda sem reembolso de créditos.
   - *Status do Nexus PlayTV:* 100% conforme (Plano mensal tabelado em **R$ 34,90** e pacotes de múltiplas telas/trimestrais acima de R$ 49,90).

2. **Custo em Créditos por Duração e Telas:**
   - **1 Crédito de Revenda = 1 Mês (30 dias) para 1 Tela.**
   - O consumo de créditos para telas adicionais e durações maiores segue a proporção por tela/mês: **Não confirmado** se há desconto automático em créditos no painel para pacotes anuais via API (o manual cita `abrela.me/adicionarmeses`).

3. **Início da Validade das Linhas Oficiais:**
   - **Imediato no ato da criação no painel.** A contagem regressiva dos 30 dias se inicia no momento em que a linha é gerada no backend do fornecedor.
   - *Regra crítica de engenharia:* **PROIBIDO PRÉ-GERAR LINHAS OFICIAIS.** Nunca criar linhas pagas antecipadamente para formar "estoque". A chamada de criação só deve ser executada após a confirmação do pagamento no webhook.

4. **Limites e Regras de Testes:**
   - O revendedor é responsável por abusos. Proibido vazamento de testes em grupos abertos.
   - O painel disponibiliza configuração de "Teste Responsável":
     - Ligado: 1 teste por número e restrito a contatos do WhatsApp.
     - Desligado: limite de 1 teste por dia por identificador.

5. **Passes Pagos de 4 Horas / Jogos de Futebol (R$ 14,90):**
   - **Autorização do Fornecedor:** **Ausência de autorização / Não existe produto de 4 horas no painel.**
   - *Fato operacional:* O painel do fornecedor não comercializa "crédito fracionado de 4 horas". Para o fornecedor, qualquer linha criada como cliente consome 1 crédito mensal integral (30 dias).
   - *Implementação interna no projeto:* O produto "Passe Futebol VIP" (R$ 14,90) é operado exclusivamente na camada de aplicação do bot (tabela SQLite `game_passes` em `db.py`), controlando o tempo de acesso do cliente na interface sem consumir linhas descartáveis do painel.

---

## 5. Prevenção de Duplicidade (Idempotência e Timeouts)

Quando uma requisição de criação (`POST /api/users` ou `/trial_users`) sofrer timeout de rede (HTTP 408/504 ou corte de conexão):

1. **Protocolo Obrigatório de Consulta Prévia:**
   - Antes de reenviar qualquer nova requisição de criação (o que consumiria um segundo crédito do revendedor), o cliente da API deve executar uma busca de verificação:
     `GET https://api.controle.fit/api/users?search=<username_gerado>`
2. **Identificador Determinístico:**
   - O `username` gerado para a criação deve ser determinístico e amarrado ao ID da transação do checkout (ex: `nx_<order_id>`).
   - Se a consulta retornar o usuário já existente com status ativo, a criação é considerada bem-sucedida e as credenciais são recuperadas sem novo débito de créditos.
3. **Persistência Local de Transação:**
   - O banco de dados local (`orders` no SQLite) deve registrar o status `processing` antes do disparo HTTP.
   - Em caso de falha irreversível, a transação fica marcada para auditoria e dispara alerta no `@Alerta_nexusbot`.

---

## 6. Estado Real da Implementação

### 6.1 O Que Foi Testado com Sucesso Comprovado em Código
1. **Servidor Master IPTV (`http://man77.work`):**
   - Resposta HTTP 200 e validação de autenticação Xtream Codes testada no ambiente.
   - Geração de M3U e dados de conexão em `nexus_playtv_bot/services.py` 100% funcional.
2. **Entrega de Cartões VIP Web Interativos:**
   - `make_vip_html.py` gerando páginas dinâmicas em `https://nexus.pixget.io/vip/<id>` com WebPlayer e cópia rápida de credenciais.
3. **Concierge Smart TV (IBO Player + OCR + 2Captcha):**
   - O fluxo de recebimento de foto da TV (`photo_handler` em `run_playtv.py`), extração de MAC/Key via OCR e injeção remota na API da nuvem do IBO Player (`ibo_injector.py`) com resolução do captcha SVG via 2Captcha foi testado com sucesso.
4. **Infraestrutura de Rede e Webhooks:**
   - Caddy SSL reverso ativo em `nexus.pixget.io`.
   - `webhook_server.py` recebendo notificações de pagamento do Pixget (PIX) e BlockBee (Cripto).
5. **Navegação Evasiva com Scrapling + Patchright:**
   - Bibliotecas instaladas no venv da VPS. Acesso à página de login com simulação indetectável validada.

### 6.2 Falhas e Gargalos que Permanecem em Aberto
1. **Submissão Automatizada do Login no Painel Web (`controle.vip`):**
   - A página de login utiliza **Cloudflare Turnstile** combinado com **React Hook Form**.
   - Em ambiente headless de datacenter (Hostinger), o Turnstile exige verificação interativa dentro de iframe. O botão "Entrar" permanece desabilitado (`disabled="true"`) até que o callback oficial do Turnstile e os eventos de digitação do React sejam acionados em conjunto.
   - Consequência: Não há um daemon em produção renovando o JWT de 60 minutos de forma contínua e autônoma.

### 6.3 O Que São Apenas Propostas (Ainda Não Implementado)
1. **Criação Automática Direta via API REST do P2Braz:**
   - A chamada programática para `POST https://api.controle.fit/api/users` a partir do `webhook_server.py` ainda depende da estabilização da sessão JWT descrita no item anterior.
2. **Integração com Módulo WhatsApp Oficial do Painel:**
   - Proposta de conectar o número de WhatsApp diretamente no painel (`https://controle.vip/settings/whatsapp`) para geração de testes de 3h delegada ao próprio servidor do fornecedor.

### 6.4 Código Fora do Repositório
- Todos os módulos operacionais desenvolvidos (`ibo_injector.py`, `make_vip_html.py`, `photo_handler`, `services.py`, `products_playtv.json`) foram devidamente versionados e integrados à pasta `nexus_playtv_bot/` no repositório `nexus-ecosystem`. Nenhum código funcional ficou isolado fora do Git.
